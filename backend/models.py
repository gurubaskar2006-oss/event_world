from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, validator
import re

Role = Literal["student", "institution", "admin"]
EventStatus = Literal["pending", "approved", "rejected", "expired"]


class UserRegister(BaseModel):
    email: str
    password: str = Field(min_length=6, max_length=72)
    role: Role
    name: str = Field(min_length=1)
    college: str | None = ""
    year: str | None = ""
    interests: list[str] = []
    avatar: str | None = ""
    institution_name: str | None = ""
    institution_code: str | None = ""

    @validator("email")
    def email_must_look_valid(cls, value: str) -> str:
        if "@" not in value:
            raise ValueError("Use a valid email address")
        return value.lower().strip()

    @validator("password")
    def password_must_fit_bcrypt(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be 72 bytes or shorter")
        if len(value) < 8:
            raise ValueError("Password must be 8+ characters")
        return value

    @validator("name")
    def name_must_be_clean(cls, v: str) -> str:
        if re.search(r'<[^>]+>', v):
            raise ValueError('Invalid characters in name')
        if len(v) > 100:
            raise ValueError('Name too long')
        return v.strip()


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=1, max_length=72)
    role: Role

    @validator("password")
    def password_must_fit_bcrypt(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be 72 bytes or shorter")
        return value


class UserOut(BaseModel):
    id: str
    email: str
    role: Role
    name: str
    college: str | None = ""
    year: str | None = ""
    interests: list[str] = []
    avatar: str | None = ""
    institution_name: str | None = ""
    created_at: str | datetime | None = None
    is_banned: bool = False
    ban_reason: str | None = None
    banned_at: str | datetime | None = None


class PaymentDetails(BaseModel):
    is_paid: bool = False
    amount: float = 0.0
    currency: str = "INR"
    razorpay_key_id: Optional[str] = None
    payment_description: Optional[str] = None


class ScheduleRow(BaseModel):
    time: str = ""
    title: str = ""
    description: str = ""


class EventIn(BaseModel):
    title: str = Field(min_length=2)
    type: str = "workshop"
    college: str = Field(min_length=2)
    description: str = Field(min_length=5)
    date: str
    time: str = ""
    location: str = ""
    fee: str = "Free"
    payment: PaymentDetails = PaymentDetails()
    prize: str = ""
    team: str = ""
    seats: str = ""
    tags: list[str] | str = []
    schedule: list[Any] = []
    highlights: str = ""
    contact: str = ""
    colorA: str = "#7b2fff"
    colorB: str = "#00f0ff"
    posterBase64: str = ""
    posterUrl: str | None = None
    poster_url: str | None = None
    websiteUrl: str = ""
    coordinators: list[dict[str, Any]] = []
    instagram: str = ""
    linkedin: str = ""
    whatsappGroup: str = ""

    @validator('title')
    def title_clean(cls, v: str) -> str:
        clean = re.sub(r'<[^>]+>', '', v)
        return clean[:200]


class EventUpdate(BaseModel):
    title: str | None = None
    type: str | None = None
    college: str | None = None
    description: str | None = None
    date: str | None = None
    time: str | None = None
    location: str | None = None
    fee: str | None = None
    payment: PaymentDetails | None = None
    prize: str | None = None
    team: str | None = None
    seats: str | None = None
    tags: list[str] | str | None = None
    schedule: list[Any] | None = None
    highlights: str | None = None
    contact: str | None = None
    colorA: str | None = None
    colorB: str | None = None
    posterBase64: str | None = None
    posterUrl: str | None = None
    poster_url: str | None = None
    websiteUrl: str | None = None
    coordinators: list[dict[str, Any]] | None = None
    instagram: str | None = None
    linkedin: str | None = None
    whatsappGroup: str | None = None
    status: EventStatus | None = None

    @validator('title')
    def title_clean(cls, v: str | None) -> str | None:
        if v is not None:
            clean = re.sub(r'<[^>]+>', '', v)
            return clean[:200]
        return v


class Registration(BaseModel):
    registration_id: str
    event_id: str
    user_id: str
    registered_at: str | datetime
    status: Literal["registered", "attended", "cancelled"] = "registered"
    attended_at: str | datetime | None = None
    checked_in_by: str | None = None


class PaymentOrderRequest(BaseModel):
    event_id: str
    sub_event_ids: list[str] = []


class PaymentConfirmRequest(BaseModel):
    event_id: str
    razorpay_payment_id: str
    razorpay_order_id: str = ""
    razorpay_signature: str = ""
    sub_event_ids: list[str] = []


class PaymentRecord(BaseModel):
    id: str
    registration_id: str
    event_id: str
    user_id: str
    razorpay_order_id: str
    razorpay_payment_id: Optional[str] = None
    razorpay_signature: Optional[str] = None
    amount: float
    currency: str = "INR"
    status: str = "created"
    created_at: str
    paid_at: Optional[str] = None


class RejectRequest(BaseModel):
    reason: str = Field(min_length=2)


class NotificationIn(BaseModel):
    user_id: str
    type: str
    title: str
    message: str
    event_id: str | None = ""
