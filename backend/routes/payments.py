from datetime import datetime, timezone
import os
import hmac
import hashlib
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status, Request
from pymongo.errors import DuplicateKeyError

from database import db, object_id, serialize_doc
from middleware.auth_guard import require_roles
from models import PaymentConfirmRequest, PaymentOrderRequest
from routes.events import event_is_expired, event_or_404, payment_is_paid
from routes.notifications import create_notification

router = APIRouter(prefix="/api/payments", tags=["payments"])


def payment_details(event: dict) -> dict:
    payment = event.get("payment") if isinstance(event.get("payment"), dict) else {}
    try:
        amount = float(payment.get("amount") or 0)
    except (TypeError, ValueError):
        amount = 0
    return {
        "is_paid": bool(payment.get("is_paid")) and amount > 0,
        "amount": amount,
        "currency": str(payment.get("currency") or "INR").upper(),
        "razorpay_key_id": str(payment.get("razorpay_key_id") or "").strip(),
        "payment_description": str(payment.get("payment_description") or "").strip(),
    }


def ensure_event_open(event: dict) -> None:
    if event.get("status") != "approved":
        raise HTTPException(status_code=400, detail="Registration is open only for approved events")
    if event_is_expired(event):
        raise HTTPException(status_code=400, detail="This event has already taken place")


async def existing_registration(event_id: str, user_id: str) -> dict | None:
    return await db.registrations.find_one({
        "event_id": event_id,
        "user_id": user_id,
        "status": {"$in": ["registered", "attended"]},
    })


async def create_registration(event: dict, event_id: str, user: dict) -> dict:
    existing = await existing_registration(event_id, user["id"])
    if existing:
        return existing
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
        existing = await existing_registration(event_id, user["id"])
        if existing:
            return existing
        raise HTTPException(status_code=409, detail="Could not create a unique ticket. Please try again.")
    await create_notification(
        user["id"],
        "registration_confirmed",
        f"Registered for {event.get('title', 'Event')}!",
        f"Your registration for {event.get('title', 'this event')} is confirmed.",
        event_id,
    )
    return doc


def registration_response(registration: dict) -> dict:
    data = serialize_doc(registration) or {}
    return {
        "registration_id": data.get("registration_id", ""),
        "event_id": data.get("event_id", ""),
        "registered_at": data.get("registered_at"),
    }


@router.post("/create-order")
async def create_payment_order(payload: PaymentOrderRequest, user: dict = Depends(require_roles("student"))):
    event = await event_or_404(payload.event_id)
    ensure_event_open(event)
    payment = payment_details(event)
    if not payment_is_paid(event.get("payment")):
        raise HTTPException(status_code=400, detail="This event does not require payment.")
    if not payment["razorpay_key_id"] or not (
        payment["razorpay_key_id"].startswith("rzp_test_") or payment["razorpay_key_id"].startswith("rzp_live_")
    ):
        raise HTTPException(status_code=400, detail="Organizer Razorpay Key ID is invalid.")
    if await existing_registration(payload.event_id, user["id"]):
        raise HTTPException(status_code=400, detail="You are already registered for this event.")
    return {
        "razorpay_key_id": payment["razorpay_key_id"],
        "amount": int(round(payment["amount"] * 100)),
        "currency": payment["currency"],
        "event_title": event.get("title", ""),
        "event_id": payload.event_id,
        "description": payment["payment_description"] or f"Registration for {event.get('title', 'Event')}",
    }


@router.post("/webhook")
async def payment_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature")
    if not signature:
        raise HTTPException(status_code=400, detail="Missing signature")
    webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET")
    if not webhook_secret:
        raise HTTPException(status_code=500, detail="Webhook secret not configured")
    expected = hmac.new(
        webhook_secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")
    return {"status": "ok"}

@router.post("/confirm")
async def confirm_payment(payload: PaymentConfirmRequest, user: dict = Depends(require_roles("student"))):
    event = await event_or_404(payload.event_id)
    ensure_event_open(event)
    payment = payment_details(event)
    if not payment_is_paid(event.get("payment")):
        raise HTTPException(status_code=400, detail="This event does not require payment.")
    if await existing_registration(payload.event_id, user["id"]):
        raise HTTPException(status_code=400, detail="You are already registered for this event.")
    now = datetime.now(timezone.utc)
    record_id = uuid4().hex
    payment_record = {
        "_id": record_id,
        "id": record_id,
        "registration_id": "",
        "event_id": payload.event_id,
        "user_id": user["id"],
        "razorpay_order_id": payload.razorpay_order_id,
        "razorpay_payment_id": payload.razorpay_payment_id,
        "razorpay_signature": payload.razorpay_signature,
        "sub_event_ids": payload.sub_event_ids,
        "amount": payment["amount"],
        "currency": payment["currency"],
        "status": "paid",
        "created_at": now.isoformat(),
        "paid_at": now.isoformat(),
    }
    await db.payments.insert_one(payment_record)
    registration = await create_registration(event, payload.event_id, user)
    registration_id = registration.get("registration_id", "")
    await db.payments.update_one({"_id": record_id}, {"$set": {"registration_id": registration_id}})
    return {
        "success": True,
        "registration_id": registration_id,
        "registered_at": serialize_doc(registration).get("registered_at"),
        "payment_id": payload.razorpay_payment_id,
        "amount_paid": payment["amount"],
    }


@router.post("/free-register")
async def free_register(payload: PaymentOrderRequest, user: dict = Depends(require_roles("student"))):
    event = await event_or_404(payload.event_id)
    ensure_event_open(event)
    if payment_is_paid(event.get("payment")):
        raise HTTPException(status_code=400, detail="This event requires payment. Use payment flow.")
    registration = await create_registration(event, payload.event_id, user)
    return registration_response(registration)


@router.get("/history")
async def payment_history(user: dict = Depends(require_roles("student"))):
    payments = await db.payments.find({"user_id": user["id"]}).sort("created_at", -1).to_list(length=200)
    event_ids = [payment.get("event_id") for payment in payments if payment.get("event_id")]
    object_ids = []
    for event_id in event_ids:
        try:
            object_ids.append(object_id(event_id))
        except ValueError:
            continue
    events = await db.events.find({"_id": {"$in": object_ids}}).to_list(length=200) if object_ids else []
    event_titles = {str(event["_id"]): event.get("title", "Event") for event in events}
    history = []
    for payment in payments:
        data = serialize_doc(payment) or {}
        data["event_title"] = event_titles.get(payment.get("event_id"), "Event")
        history.append(data)
    return history
