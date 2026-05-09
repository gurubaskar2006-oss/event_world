from datetime import datetime, timezone
import os

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status

from database import db, serialize_doc
from middleware.auth_guard import get_current_user
from models import LoginRequest, UserRegister
from utils.jwt_handler import create_access_token

router = APIRouter(prefix="/api/auth", tags=["auth"])

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "").lower().strip()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")


def hash_password(password: str) -> str:
    if len(password.encode("utf-8")) > 72:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be 72 bytes or shorter")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    if len(password.encode("utf-8")) > 72:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def public_user(user: dict) -> dict:
    data = serialize_doc(user)
    data.pop("password_hash", None)
    data.pop("institution_code", None)
    return data


async def ensure_admin_user(email: str, password: str) -> dict | None:
    if not ADMIN_EMAIL or not ADMIN_PASSWORD:
        return None
    if email != ADMIN_EMAIL or password != ADMIN_PASSWORD:
        return None
    user = await db.users.find_one({"email": email})
    if user:
        return user
    now = datetime.now(timezone.utc)
    doc = {
        "email": email,
        "password_hash": hash_password(password),
        "role": "admin",
        "name": "Admin",
        "college": "",
        "year": "",
        "interests": [],
        "avatar": "",
        "institution_name": "",
        "institution_code": "",
        "created_at": now,
    }
    result = await db.users.insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(payload: UserRegister):
    email = payload.email.lower().strip()
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    now = datetime.now(timezone.utc)
    doc = payload.dict()
    password = doc.pop("password")
    doc["email"] = email
    doc["password_hash"] = hash_password(password)
    doc["created_at"] = now
    result = await db.users.insert_one(doc)
    doc["_id"] = result.inserted_id
    token = create_access_token({"user_id": str(result.inserted_id), "email": doc["email"], "role": doc["role"]})
    return {"token": token, "user": public_user(doc)}


@router.post("/login")
async def login(payload: LoginRequest):
    email = payload.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if not user:
        user = await ensure_admin_user(email, payload.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    if user.get("role") != payload.role:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role does not match this account")
    if not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    token = create_access_token({"user_id": str(user["_id"]), "email": user["email"], "role": user["role"]})
    return {"token": token, "user": public_user(user)}


@router.post("/logout")
async def logout():
    return {"ok": True}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return user
