import os
from datetime import datetime
from typing import Any

import certifi
from bson import ObjectId
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import PyMongoError

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL", "mongodb+srv://username:password@cluster.mongodb.net/eventworld")
MONGO_DB = os.getenv("MONGO_DB", "eventworld")
MONGO_TIMEOUT_MS = int(os.getenv("MONGO_TIMEOUT_MS", "20000"))

client_options: dict[str, Any] = {"serverSelectionTimeoutMS": MONGO_TIMEOUT_MS}
if MONGO_URL.startswith("mongodb+srv://") or "mongodb.net" in MONGO_URL:
    client_options["tlsCAFile"] = certifi.where()

client = AsyncIOMotorClient(MONGO_URL, **client_options)
db = client[MONGO_DB]


def object_id(value: str) -> ObjectId:
    if not ObjectId.is_valid(value):
        raise ValueError("Invalid object id")
    return ObjectId(value)


def serialize_doc(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    if not doc:
        return None
    output: dict[str, Any] = {}
    for key, value in doc.items():
        if key == "_id":
            output["id"] = str(value)
        elif isinstance(value, ObjectId):
            output[key] = str(value)
        elif isinstance(value, datetime):
            output[key] = value.isoformat()
        elif isinstance(value, list):
            output[key] = [serialize_doc(item) if isinstance(item, dict) else item for item in value]
        else:
            output[key] = value
    return output


def serialize_many(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [serialize_doc(doc) for doc in docs if doc]


async def create_indexes() -> None:
    try:
        await client.admin.command("ping")
        await db.users.create_index("email", unique=True)
        await db.events.create_index([("status", 1), ("date", 1)])
        await db.events.create_index([("title", "text"), ("college", "text"), ("description", "text"), ("tags", "text")])
        await db.registrations.create_index([("event_id", 1), ("user_id", 1)], unique=True)
        await db.registrations.create_index("registration_id", unique=True, sparse=True)
        await db.payments.create_index([("user_id", 1), ("created_at", -1)])
        await db.payments.create_index([("event_id", 1), ("registration_id", 1)])
        await db.payments.create_index("razorpay_payment_id", sparse=True)
        await db.saved_events.create_index([("event_id", 1), ("user_id", 1)], unique=True)
        await db.notifications.create_index([("user_id", 1), ("created_at", -1)])
        print("Connected to MongoDB Atlas")
    except PyMongoError as error:
        print(f"MongoDB is not available yet. API database routes will fail until MONGO_URL is connected. Details: {error}")
