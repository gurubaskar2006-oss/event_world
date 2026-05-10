import csv
import io
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response
from pymongo import ReturnDocument

from database import db, object_id, serialize_doc, serialize_many
from middleware.auth_guard import require_roles
from models import RejectRequest
from routes.notifications import create_notification

router = APIRouter(prefix="/api/admin", tags=["admin"])


def public_user(user: dict) -> dict:
    data = serialize_doc(user) or {}
    if data.get("id"):
        data["_id"] = data["id"]
    data.pop("password_hash", None)
    data.pop("institution_code", None)
    return data


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


@router.get("/users/stats")
async def user_stats(user: dict = Depends(require_roles("admin"))):
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return {
        "total_users": await db.users.count_documents({}),
        "students": await db.users.count_documents({"role": "student"}),
        "institutions": await db.users.count_documents({"role": "institution"}),
        "banned": await db.users.count_documents({"is_banned": True}),
        "new_today": await db.users.count_documents({"created_at": {"$gte": today}}),
    }


@router.get("/users")
async def list_users(
    role: str | None = None,
    search: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    user: dict = Depends(require_roles("admin")),
):
    query: dict = {}
    if role and role != "all":
        query["role"] = role
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}},
            {"college": {"$regex": search, "$options": "i"}},
            {"institution_name": {"$regex": search, "$options": "i"}},
        ]
    users = await db.users.find(query).sort("created_at", -1).skip(skip).limit(limit).to_list(length=limit)
    return [public_user(item) for item in users]


@router.post("/users/{user_id}/ban")
async def ban_user(user_id: str, payload: dict = Body(...), user: dict = Depends(require_roles("admin"))):
    reason = str(payload.get("reason", "")).strip()
    if not reason:
        raise HTTPException(status_code=400, detail="Ban reason is required")
    if user_id == user["id"]:
        raise HTTPException(status_code=400, detail="You cannot ban your own admin account")
    try:
        result = await db.users.update_one(
            {"_id": object_id(user_id)},
            {"$set": {"is_banned": True, "ban_reason": reason, "banned_at": datetime.now(timezone.utc)}},
        )
    except ValueError:
        result = None
    if not result or result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"success": True, "message": "User banned"}


@router.post("/users/{user_id}/unban")
async def unban_user(user_id: str, user: dict = Depends(require_roles("admin"))):
    try:
        result = await db.users.update_one(
            {"_id": object_id(user_id)},
            {"$set": {"is_banned": False}, "$unset": {"ban_reason": "", "banned_at": ""}},
        )
    except ValueError:
        result = None
    if not result or result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"success": True, "message": "User unbanned"}


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, user: dict = Depends(require_roles("admin"))):
    if user_id == user["id"]:
        raise HTTPException(status_code=400, detail="You cannot delete your own admin account")
    try:
        oid = object_id(user_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="User not found")
    result = await db.users.delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    await db.registrations.delete_many({"user_id": user_id})
    await db.saved_events.delete_many({"user_id": user_id})
    await db.notifications.delete_many({"user_id": user_id})
    return {"success": True, "message": "User deleted"}


@router.get("/analytics")
async def analytics(user: dict = Depends(require_roles("admin"))):
    approved_events = await db.events.find({"status": "approved"}).to_list(length=500)
    event_ids = [str(event["_id"]) for event in approved_events]
    reg_counts = {event_id: 0 for event_id in event_ids}
    save_counts = {event_id: 0 for event_id in event_ids}
    for row in await db.registrations.aggregate([
        {"$match": {"event_id": {"$in": event_ids}}},
        {"$group": {"_id": "$event_id", "count": {"$sum": 1}}},
    ]).to_list(length=500):
        reg_counts[row["_id"]] = row["count"]
    for row in await db.saved_events.aggregate([
        {"$match": {"event_id": {"$in": event_ids}}},
        {"$group": {"_id": "$event_id", "count": {"$sum": 1}}},
    ]).to_list(length=500):
        save_counts[row["_id"]] = row["count"]
    serialized = []
    for event in approved_events:
        event_id = str(event["_id"])
        item = serialize_doc(event)
        item["registration_count"] = max(int(item.get("registration_count") or 0), reg_counts.get(event_id, 0))
        item["save_count"] = save_counts.get(event_id, 0)
        serialized.append(item)
    events_by_type = {}
    for event in approved_events:
        event_type = str(event.get("type") or "workshop").lower()
        events_by_type[event_type] = events_by_type.get(event_type, 0) + 1
    week_start = datetime.now(timezone.utc) - timedelta(days=6)
    registrations_by_day = []
    for offset in range(7):
        day_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=offset)
        day_end = day_start + timedelta(days=1)
        registrations_by_day.append({
            "date": day_start.date().isoformat(),
            "count": await db.registrations.count_documents({"registered_at": {"$gte": day_start, "$lt": day_end}}),
        })
    top_colleges = await db.events.aggregate([
        {"$group": {"_id": "$college", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 5},
    ]).to_list(length=5)
    return {
        "most_registered": sorted(serialized, key=lambda item: item.get("registration_count", 0), reverse=True)[:5],
        "most_saved": sorted(serialized, key=lambda item: item.get("save_count", 0), reverse=True)[:5],
        "events_by_type": events_by_type,
        "registrations_by_day": registrations_by_day,
        "top_colleges": [{"college": row.get("_id") or "Unknown", "count": row["count"]} for row in top_colleges],
    }


@router.post("/announce")
async def announce(payload: dict = Body(...), user: dict = Depends(require_roles("admin"))):
    title = str(payload.get("title", "")).strip()
    message = str(payload.get("message", "")).strip()
    if not title or not message:
        raise HTTPException(status_code=400, detail="Title and message are required")
    students = await db.users.find({"role": "student"}).to_list(length=5000)
    for student in students:
        await create_notification(str(student["_id"]), "announcement", title, message, "")
    return {"sent_to": len(students)}


@router.get("/export/events")
async def export_events(user: dict = Depends(require_roles("admin"))):
    events = await db.events.find({"status": "approved"}).sort("date", 1).to_list(length=5000)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["title", "college", "type", "date", "registrations"])
    for event in events:
        writer.writerow([
            event.get("title", ""),
            event.get("college", ""),
            event.get("type", ""),
            event.get("date", ""),
            event.get("registration_count", 0),
        ])
    return Response(
        buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="events.csv"'},
    )
