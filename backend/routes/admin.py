from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pymongo import ReturnDocument

from database import db, object_id, serialize_doc, serialize_many
from middleware.auth_guard import require_roles
from models import RejectRequest
from routes.notifications import create_notification

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/pending")
async def pending_events(user: dict = Depends(require_roles("admin"))):
    events = await db.events.find({"status": "pending"}).sort("submitted_at", -1).to_list(length=200)
    return serialize_many(events)


@router.get("/events")
async def all_events(user: dict = Depends(require_roles("admin"))):
    events = await db.events.find({}).sort("submitted_at", -1).to_list(length=300)
    return serialize_many(events)


@router.post("/approve/{event_id}")
async def approve_event(event_id: str, user: dict = Depends(require_roles("admin"))):
    try:
        event = await db.events.find_one_and_update(
            {"_id": object_id(event_id)},
            {"$set": {"status": "approved", "approved_at": datetime.now(timezone.utc), "approved_by": user["id"]}},
            return_document=ReturnDocument.AFTER,
        )
    except ValueError:
        event = None
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.get("submitted_by"):
        await create_notification(event["submitted_by"], "event_approved", f"{event['title']} approved", f"Your event {event['title']} has been approved and is now live!", event_id)
    students = await db.users.find({"role": "student"}).to_list(length=1000)
    for student in students:
        await create_notification(str(student["_id"]), "new_event", f"New event: {event['title']}", f"{event['title']} at {event['college']} is now available.", event_id)
    return serialize_doc(event)


@router.post("/reject/{event_id}")
async def reject_event(event_id: str, payload: RejectRequest, user: dict = Depends(require_roles("admin"))):
    try:
        event = await db.events.find_one_and_update(
            {"_id": object_id(event_id)},
            {"$set": {"status": "rejected", "rejected_reason": payload.reason, "rejected_at": datetime.now(timezone.utc), "approved_by": user["id"]}},
            return_document=ReturnDocument.AFTER,
        )
    except ValueError:
        event = None
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.get("submitted_by"):
        await create_notification(event["submitted_by"], "event_rejected", f"{event['title']} was rejected", f"Your event {event['title']} was not approved. Reason: {payload.reason}", event_id)
    return serialize_doc(event)


@router.get("/stats")
async def stats(user: dict = Depends(require_roles("admin"))):
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return {
        "total_users": await db.users.count_documents({}),
        "total_students": await db.users.count_documents({"role": "student"}),
        "total_institutions": await db.users.count_documents({"role": "institution"}),
        "total_events": await db.events.count_documents({}),
        "pending_count": await db.events.count_documents({"status": "pending"}),
        "approved_count": await db.events.count_documents({"status": "approved"}),
        "rejected_count": await db.events.count_documents({"status": "rejected"}),
        "total_registrations": await db.registrations.count_documents({}),
        "new_users_today": await db.users.count_documents({"created_at": {"$gte": today}}),
    }
