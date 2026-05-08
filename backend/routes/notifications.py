from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from database import db, object_id, serialize_many
from middleware.auth_guard import get_current_user

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


async def create_notification(user_id: str, type: str, title: str, message: str, event_id: str = "") -> None:
    await db.notifications.insert_one({
        "user_id": user_id,
        "type": type,
        "title": title,
        "message": message,
        "event_id": event_id,
        "is_read": False,
        "created_at": datetime.now(timezone.utc),
    })


@router.get("")
async def notifications(user: dict = Depends(get_current_user)):
    cursor = db.notifications.find({"user_id": user["id"]}).sort("created_at", -1)
    return serialize_many(await cursor.to_list(length=80))


@router.post("/read/{notification_id}")
async def mark_read(notification_id: str, user: dict = Depends(get_current_user)):
    try:
        result = await db.notifications.update_one({"_id": object_id(notification_id), "user_id": user["id"]}, {"$set": {"is_read": True}})
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid notification id")
    return {"ok": result.modified_count >= 0}


@router.post("/read-all")
async def mark_all_read(user: dict = Depends(get_current_user)):
    await db.notifications.update_many({"user_id": user["id"]}, {"$set": {"is_read": True}})
    return {"ok": True}
