from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from database import db, object_id, serialize_doc, serialize_many
from middleware.auth_guard import get_current_user, require_roles
from models import EventIn, EventUpdate
from routes.notifications import create_notification

router = APIRouter(prefix="/api/events", tags=["events"])


def clean_event_payload(payload: dict[str, Any]) -> dict[str, Any]:
    tags = payload.get("tags", [])
    if isinstance(tags, str):
        tags = [tag.strip() for tag in tags.split(",") if tag.strip()]
    payload["tags"] = tags
    payload["type"] = str(payload.get("type") or "workshop").lower()
    poster_url = payload.pop("posterUrl", None) or payload.get("poster_url")
    payload["poster_url"] = poster_url or None
    payload.pop("posterBase64", None)
    return payload


async def event_or_404(event_id: str) -> dict:
    try:
        event = await db.events.find_one({"_id": object_id(event_id)})
    except ValueError:
        event = None
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.get("/registered")
async def registered_events(user: dict = Depends(get_current_user)):
    regs = await db.registrations.find({"user_id": user["id"], "status": "registered"}).to_list(length=200)
    ids = [object_id(item["event_id"]) for item in regs if item.get("event_id")]
    events = await db.events.find({"_id": {"$in": ids}}).to_list(length=200) if ids else []
    return serialize_many(events)


@router.get("/saved")
async def saved_events(user: dict = Depends(get_current_user)):
    saved = await db.saved_events.find({"user_id": user["id"]}).to_list(length=200)
    ids = [object_id(item["event_id"]) for item in saved if item.get("event_id")]
    events = await db.events.find({"_id": {"$in": ids}}).to_list(length=200) if ids else []
    return serialize_many(events)


@router.get("")
async def list_events(
    type: str | None = None,
    search: str | None = None,
    sort: str = "date",
    limit: int = Query(30, ge=1, le=100),
    skip: int = Query(0, ge=0),
):
    query: dict[str, Any] = {"status": "approved"}
    if type and type != "all":
        query["type"] = type.lower()
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"college": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}},
            {"location": {"$regex": search, "$options": "i"}},
            {"tags": {"$regex": search, "$options": "i"}},
        ]
    sort_field = "date"
    sort_direction = 1
    if sort == "popularity":
        sort_field = "registration_count"
        sort_direction = -1
    events = await db.events.find(query).sort(sort_field, sort_direction).skip(skip).limit(limit).to_list(length=limit)
    return serialize_many(events)


@router.get("/{event_id}")
async def get_event(event_id: str):
    event = await event_or_404(event_id)
    if event.get("status") == "approved":
        event = await db.events.find_one_and_update(
            {"_id": event["_id"]},
            {"$inc": {"view_count": 1}},
            return_document=ReturnDocument.AFTER,
        )
    return serialize_doc(event)


@router.post("/submit")
async def submit_event(payload: EventIn, user: dict = Depends(require_roles("institution", "admin"))):
    doc = clean_event_payload(payload.dict())
    now = datetime.now(timezone.utc)
    doc.update({
        "status": "pending",
        "submitted_by": user["id"],
        "submitted_at": now,
        "approved_at": None,
        "approved_by": None,
        "view_count": 0,
        "registration_count": 0,
    })
    result = await db.events.insert_one(doc)
    doc["_id"] = result.inserted_id
    admins = await db.users.find({"role": "admin"}).to_list(length=50)
    for admin in admins:
        await create_notification(str(admin["_id"]), "new_submission", "New event submitted", f"{user.get('name', 'An institution')} submitted {doc['title']} for review.", str(result.inserted_id))
    return serialize_doc(doc)


@router.put("/{event_id}")
async def update_event(event_id: str, payload: EventUpdate, user: dict = Depends(get_current_user)):
    event = await event_or_404(event_id)
    if user["role"] == "institution" and event.get("submitted_by") != user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can edit only your own events")
    if user["role"] not in ("institution", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only institutions or admins can edit events")
    update = {k: v for k, v in payload.dict(exclude_unset=True).items() if v is not None}
    update = clean_event_payload(update)
    result = await db.events.find_one_and_update({"_id": event["_id"]}, {"$set": update}, return_document=ReturnDocument.AFTER)
    return serialize_doc(result)


@router.post("/{event_id}/register")
async def register_for_event(event_id: str, user: dict = Depends(require_roles("student"))):
    event = await event_or_404(event_id)
    if event.get("status") != "approved":
        raise HTTPException(status_code=400, detail="Registration is open only for approved events")
    doc = {"event_id": event_id, "user_id": user["id"], "registered_at": datetime.now(timezone.utc), "status": "registered"}
    try:
        await db.registrations.insert_one(doc)
        await db.events.update_one({"_id": event["_id"]}, {"$inc": {"registration_count": 1}})
    except DuplicateKeyError:
        pass
    await create_notification(user["id"], "registration_confirmed", f"Registered for {event['title']}!", f"Your registration for {event['title']} is confirmed.", event_id)
    return {"ok": True}


@router.post("/{event_id}/save")
async def toggle_save(event_id: str, user: dict = Depends(get_current_user)):
    await event_or_404(event_id)
    existing = await db.saved_events.find_one({"event_id": event_id, "user_id": user["id"]})
    if existing:
        await db.saved_events.delete_one({"_id": existing["_id"]})
        return {"saved": False}
    await db.saved_events.insert_one({"event_id": event_id, "user_id": user["id"], "saved_at": datetime.now(timezone.utc)})
    return {"saved": True}
