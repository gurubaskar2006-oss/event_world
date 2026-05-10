import csv
import io
import re
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from database import db, object_id, serialize_doc, serialize_many
from middleware.auth_guard import get_current_user, require_roles
from models import EventIn, EventUpdate
from routes.notifications import create_notification

router = APIRouter(prefix="/api/events", tags=["events"])
ticket_router = APIRouter(prefix="/api/tickets", tags=["tickets"])
stats_router = APIRouter(prefix="/api", tags=["stats"])
institution_router = APIRouter(prefix="/api/institutions", tags=["institutions"])
_stats_cache: dict[str, Any] = {"expires_at": None, "data": None}


def parse_event_date(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    candidates = [
        text,
        text.split("-")[0].strip(),
        text.replace("st", "").replace("nd", "").replace("rd", "").replace("th", ""),
    ]
    formats = ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y"]
    for candidate in candidates:
        for fmt in formats:
            try:
                return datetime.strptime(candidate[:19], fmt)
            except ValueError:
                continue
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
    except ValueError:
        return None


def event_is_expired(event: dict[str, Any]) -> bool:
    if event.get("status") == "expired":
        return True
    target = parse_event_date(event.get("endDate") or event.get("end_date") or event.get("date"))
    if not target:
        return False
    return target.date() < datetime.utcnow().date()


def serialize_event(event: dict[str, Any] | None) -> dict[str, Any] | None:
    data = serialize_doc(event)
    if data is not None:
        data["expired"] = event_is_expired(event or {})
    return data


def serialize_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [serialize_event(event) for event in events if event]


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


async def event_for_registration_access(event_id: str, user: dict) -> dict:
    event = await event_or_404(event_id)
    if user.get("role") == "admin":
        return event
    if user.get("role") == "institution" and event.get("submitted_by") == user.get("id"):
        return event
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can manage registrations only for your own events")


def student_payload(user: dict | None) -> dict:
    user = user or {}
    return {
        "name": user.get("name", ""),
        "email": user.get("email", ""),
        "college": user.get("college", ""),
        "avatar": user.get("avatar", ""),
    }


async def registration_with_student(registration: dict, user_map: dict[str, dict]) -> dict:
    data = serialize_doc(registration)
    data["student"] = student_payload(user_map.get(registration.get("user_id", "")))
    return data


def csv_filename(title: str, date: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", f"{title}_{date}").strip("_").lower() or "event"
    return f"attendees_{slug}.csv"


def object_ids_for_strings(values: list[str]) -> list:
    ids = []
    for value in values:
        try:
            ids.append(object_id(value))
        except ValueError:
            continue
    return ids


@router.get("/registered")
async def registered_events(user: dict = Depends(get_current_user)):
    regs = await db.registrations.find({"user_id": user["id"], "status": {"$in": ["registered", "attended"]}}).to_list(length=200)
    ids = [object_id(item["event_id"]) for item in regs if item.get("event_id")]
    events = await db.events.find({"_id": {"$in": ids}}).to_list(length=200) if ids else []
    return serialize_many(events)


@router.get("/saved")
async def saved_events(user: dict = Depends(get_current_user)):
    saved = await db.saved_events.find({"user_id": user["id"]}).to_list(length=200)
    ids = [object_id(item["event_id"]) for item in saved if item.get("event_id")]
    events = await db.events.find({"_id": {"$in": ids}}).to_list(length=200) if ids else []
    return serialize_many(events)


@router.get("/submitted")
async def submitted_events(user: dict = Depends(require_roles("institution", "admin"))):
    query = {} if user["role"] == "admin" else {"submitted_by": user["id"]}
    events = await db.events.find(query).sort("submitted_at", -1).to_list(length=300)
    return serialize_events(events)


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
    return serialize_events(events)


@stats_router.get("/stats")
async def platform_stats():
    now = datetime.now(timezone.utc)
    if _stats_cache["data"] and _stats_cache["expires_at"] and _stats_cache["expires_at"] > now:
        return _stats_cache["data"]

    year_start = datetime(now.year, 1, 1)
    year_start_aware = datetime(now.year, 1, 1, tzinfo=timezone.utc)
    approved_query = {"status": "approved"}
    active_events = await db.events.count_documents(approved_query)
    colleges_result = await db.events.aggregate([
        {"$match": {"status": "approved", "college": {"$nin": ["", None]}}},
        {"$group": {"_id": "$college"}},
        {"$count": "total"},
    ]).to_list(1)
    colleges_listed = colleges_result[0]["total"] if colleges_result else 0
    students_connected = await db.users.count_documents({"role": "student"})
    events_this_year = await db.events.count_documents({
        "status": "approved",
        "$or": [
            {"submitted_at": {"$gte": year_start}},
            {"submitted_at": {"$gte": year_start_aware}},
            {"submitted_at": {"$gte": year_start.isoformat()}},
        ],
    })
    if events_this_year == 0:
        events_this_year = active_events
    data = {
        "active_events": active_events,
        "colleges_listed": colleges_listed,
        "students_connected": students_connected,
        "events_this_year": events_this_year,
    }
    _stats_cache["data"] = data
    _stats_cache["expires_at"] = datetime.fromtimestamp(now.timestamp() + 60, tz=timezone.utc)
    return data


@router.get("/search")
async def search_events(q: str = Query("", min_length=1), limit: int = Query(30, ge=1, le=100)):
    text_events = await db.events.find({"status": "approved", "$text": {"$search": q}}).limit(limit).to_list(length=limit)
    if text_events:
        return serialize_events(text_events)
    query = {
        "status": "approved",
        "$or": [
            {"title": {"$regex": q, "$options": "i"}},
            {"college": {"$regex": q, "$options": "i"}},
            {"description": {"$regex": q, "$options": "i"}},
            {"type": {"$regex": q, "$options": "i"}},
            {"tags": {"$regex": q, "$options": "i"}},
        ],
    }
    events = await db.events.find(query).sort("date", 1).limit(limit).to_list(length=limit)
    return serialize_events(events)


@router.get("/{event_id}/registrations/count")
async def registration_count(event_id: str):
    count = await db.registrations.count_documents({"event_id": event_id, "status": {"$in": ["registered", "attended"]}})
    return {"event_id": event_id, "count": count}


@router.get("/{event_id}/registrations")
async def event_registrations(
    event_id: str,
    status_filter: str | None = Query(None, alias="status"),
    search: str | None = None,
    user: dict = Depends(require_roles("institution", "admin")),
):
    await event_for_registration_access(event_id, user)
    query: dict[str, Any] = {"event_id": event_id}
    if status_filter and status_filter != "all":
        query["status"] = status_filter
    registrations = await db.registrations.find(query).sort("registered_at", -1).to_list(length=1000)
    user_ids = [item.get("user_id") for item in registrations if item.get("user_id")]
    user_docs = await db.users.find({"_id": {"$in": object_ids_for_strings(user_ids)}}).to_list(length=1000) if user_ids else []
    user_map = {str(item["_id"]): item for item in user_docs}
    rows = [await registration_with_student(item, user_map) for item in registrations]
    if search:
        needle = search.lower().strip()
        rows = [
            row for row in rows
            if needle in " ".join([
                row.get("registration_id", ""),
                row.get("student", {}).get("name", ""),
                row.get("student", {}).get("email", ""),
                row.get("student", {}).get("college", ""),
            ]).lower()
        ]
    total_registered = await db.registrations.count_documents({"event_id": event_id, "status": {"$in": ["registered", "attended"]}})
    total_attended = await db.registrations.count_documents({"event_id": event_id, "status": "attended"})
    total_cancelled = await db.registrations.count_documents({"event_id": event_id, "status": "cancelled"})
    return {
        "total_registered": total_registered,
        "total_attended": total_attended,
        "total_cancelled": total_cancelled,
        "registrations": rows,
    }


@router.get("/{event_id}/registrations/export")
async def export_event_registrations(event_id: str, user: dict = Depends(require_roles("institution", "admin"))):
    event = await event_for_registration_access(event_id, user)
    registrations = await db.registrations.find({"event_id": event_id}).sort("registered_at", -1).to_list(length=5000)
    user_ids = [item.get("user_id") for item in registrations if item.get("user_id")]
    user_docs = await db.users.find({"_id": {"$in": object_ids_for_strings(user_ids)}}).to_list(length=5000) if user_ids else []
    user_map = {str(item["_id"]): item for item in user_docs}
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Registration ID", "Student Name", "Student Email", "Student College", "Registered At", "Status", "Attended At"])
    for registration in registrations:
        student = student_payload(user_map.get(registration.get("user_id", "")))
        data = serialize_doc(registration)
        writer.writerow([
            data.get("registration_id", ""),
            student.get("name", ""),
            student.get("email", ""),
            student.get("college", ""),
            data.get("registered_at", ""),
            data.get("status", ""),
            data.get("attended_at", ""),
        ])
    return Response(
        buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{csv_filename(event.get("title", "event"), event.get("date", ""))}"'},
    )


@router.get("/{event_id}")
async def get_event(event_id: str):
    event = await event_or_404(event_id)
    if event.get("status") == "approved":
        event = await db.events.find_one_and_update(
            {"_id": event["_id"]},
            {"$inc": {"view_count": 1}},
            return_document=ReturnDocument.AFTER,
        )
    return serialize_event(event)


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
    return serialize_event(doc)


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
    return serialize_event(result)


@router.post("/{event_id}/register")
async def register_for_event(event_id: str, user: dict = Depends(require_roles("student"))):
    event = await event_or_404(event_id)
    if event.get("status") != "approved":
        raise HTTPException(status_code=400, detail="Registration is open only for approved events")
    if event_is_expired(event):
        raise HTTPException(status_code=400, detail="This event has already taken place")
    existing = await db.registrations.find_one({"event_id": event_id, "user_id": user["id"], "status": {"$in": ["registered", "attended"]}})
    if existing:
        return {
            "registration_id": existing.get("registration_id", ""),
            "event_id": event_id,
            "registered_at": serialize_doc(existing).get("registered_at"),
        }
    registration_id = f"EW-{event_id[:6].upper()}-{uuid4().hex[:8].upper()}"
    doc = {
        "event_id": event_id,
        "user_id": user["id"],
        "registration_id": registration_id,
        "registered_at": datetime.now(timezone.utc),
        "status": "registered",
    }
    try:
        await db.registrations.insert_one(doc)
        await db.events.update_one({"_id": event["_id"]}, {"$inc": {"registration_count": 1}})
    except DuplicateKeyError:
        existing = await db.registrations.find_one({"event_id": event_id, "user_id": user["id"], "status": {"$in": ["registered", "attended"]}})
        if existing:
            return {
                "registration_id": existing.get("registration_id", ""),
                "event_id": event_id,
                "registered_at": serialize_doc(existing).get("registered_at"),
            }
        raise HTTPException(status_code=409, detail="Could not create a unique ticket. Please try again.")
    await create_notification(user["id"], "registration_confirmed", f"Registered for {event['title']}!", f"Your registration for {event['title']} is confirmed.", event_id)
    return {
        "registration_id": registration_id,
        "event_id": event_id,
        "registered_at": doc["registered_at"].isoformat(),
    }


@router.post("/{event_id}/save")
async def toggle_save(event_id: str, user: dict = Depends(get_current_user)):
    await event_or_404(event_id)
    existing = await db.saved_events.find_one({"event_id": event_id, "user_id": user["id"]})
    if existing:
        await db.saved_events.delete_one({"_id": existing["_id"]})
        return {"saved": False}
    await db.saved_events.insert_one({"event_id": event_id, "user_id": user["id"], "saved_at": datetime.now(timezone.utc)})
    return {"saved": True}


@ticket_router.get("/verify/{registration_id}")
async def verify_ticket(registration_id: str):
    registration = await db.registrations.find_one({"registration_id": registration_id})
    if not registration:
        return {"valid": False, "message": "Invalid ticket", "registration_id": registration_id}

    event = None
    user = None
    try:
        event = await db.events.find_one({"_id": object_id(registration.get("event_id", ""))})
    except ValueError:
        event = None
    try:
        user = await db.users.find_one({"_id": object_id(registration.get("user_id", ""))})
    except ValueError:
        user = None

    if not event or not user:
        return {"valid": False, "message": "Invalid ticket", "registration_id": registration_id}

    return {
        "valid": True,
        "event_title": event.get("title", ""),
        "event_date": event.get("date", ""),
        "event_location": event.get("location", ""),
        "student_name": user.get("name", ""),
        "student_email": user.get("email", ""),
        "student_college": user.get("college", ""),
        "registered_at": serialize_doc(registration).get("registered_at"),
        "status": registration.get("status", "registered"),
        "attended_at": serialize_doc(registration).get("attended_at"),
        "registration_id": registration_id,
    }


@ticket_router.post("/scan/{registration_id}")
async def scan_ticket(registration_id: str, user: dict = Depends(require_roles("institution", "admin"))):
    registration = await db.registrations.find_one({"registration_id": registration_id})
    if not registration:
        return {"valid": False, "reason": "not_found", "message": "Ticket not found"}
    event = None
    try:
        event = await db.events.find_one({"_id": object_id(registration.get("event_id", ""))})
    except ValueError:
        event = None
    if not event:
        return {"valid": False, "reason": "not_found", "message": "Event not found for this ticket"}
    if user.get("role") == "institution" and event.get("submitted_by") != user.get("id"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can scan tickets only for your own events")
    student = None
    try:
        student = await db.users.find_one({"_id": object_id(registration.get("user_id", ""))})
    except ValueError:
        student = None
    student_data = student_payload(student)
    if registration.get("status") == "attended":
        return {
            "valid": False,
            "reason": "already_used",
            "message": "This ticket was already scanned",
            "attended_at": serialize_doc(registration).get("attended_at"),
            "student": student_data,
        }
    if registration.get("status") == "cancelled":
        return {"valid": False, "reason": "cancelled", "message": "This registration was cancelled", "student": student_data}
    now = datetime.now(timezone.utc)
    await db.registrations.update_one(
        {"_id": registration["_id"]},
        {"$set": {"status": "attended", "attended_at": now, "checked_in_by": user["id"]}},
    )
    if registration.get("user_id"):
        await create_notification(
            registration["user_id"],
            "attendance",
            "Attendance Confirmed!",
            f"Your attendance at {event.get('title', 'the event')} has been confirmed. Enjoy the event!",
            registration.get("event_id", ""),
        )
    return {
        "valid": True,
        "message": "Ticket verified successfully",
        "registration_id": registration_id,
        "student": student_data,
        "event": {"title": event.get("title", ""), "date": event.get("date", ""), "location": event.get("location", "")},
        "registered_at": serialize_doc(registration).get("registered_at"),
        "attended_at": now.isoformat(),
    }


@ticket_router.post("/cancel/{registration_id}")
async def cancel_ticket(registration_id: str, user: dict = Depends(require_roles("institution", "admin"))):
    registration = await db.registrations.find_one({"registration_id": registration_id})
    if not registration:
        raise HTTPException(status_code=404, detail="Registration not found")
    event = await event_for_registration_access(registration.get("event_id", ""), user)
    await db.registrations.update_one({"_id": registration["_id"]}, {"$set": {"status": "cancelled", "cancelled_at": datetime.now(timezone.utc)}})
    if registration.get("user_id"):
        await create_notification(
            registration["user_id"],
            "registration_cancelled",
            f"{event.get('title', 'Event')} registration cancelled",
            f"Your registration for {event.get('title', 'this event')} was cancelled by the organizer.",
            registration.get("event_id", ""),
        )
    return {"success": True}


@institution_router.get("/{user_id}/profile")
async def institution_profile(user_id: str):
    try:
        user = await db.users.find_one({"_id": object_id(user_id), "role": "institution"})
    except ValueError:
        user = None
    if not user:
        raise HTTPException(status_code=404, detail="Institution not found")
    approved_events = await db.events.find({"submitted_by": user_id, "status": "approved"}).sort("date", 1).to_list(length=100)
    total_submitted = await db.events.count_documents({"submitted_by": user_id})
    total_approved = await db.events.count_documents({"submitted_by": user_id, "status": "approved"})
    total_rejected = await db.events.count_documents({"submitted_by": user_id, "status": "rejected"})
    return {
        "id": str(user["_id"]),
        "name": user.get("institution_name") or user.get("name", ""),
        "college": user.get("college", ""),
        "email": user.get("email", ""),
        "joined_at": serialize_doc(user).get("created_at"),
        "approved_events": serialize_events(approved_events),
        "total_submitted": total_submitted,
        "total_approved": total_approved,
        "total_rejected": total_rejected,
    }
