import os
import time
from datetime import datetime, timezone
from typing import Any

import google.generativeai as genai
from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from utils.limiter import limiter
from pydantic import BaseModel, Field

from database import db

router = APIRouter(tags=["ai"])
_last_request_by_ip: dict[str, float] = {}


class ChatMessage(BaseModel):
    role: str = "user"
    parts: str = ""


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    conversation_history: list[ChatMessage] = Field(default_factory=list)


def format_events_for_context(events: list[dict[str, Any]]) -> str:
    if not events:
        return "No events are currently listed on the platform."
    lines = []
    for event in events:
        tags = event.get("tags", [])
        if not isinstance(tags, list):
            tags = [str(tags)]
        lines.append(
            f"Event: {event.get('title', '')} | Type: {event.get('type', '')} | "
            f"College: {event.get('college', '')} | Date: {event.get('date', '')} | "
            f"Location: {event.get('location', '')} | Fee: {event.get('fee', '')} | "
            f"Prize: {event.get('prize', '')} | Tags: {', '.join(map(str, tags))} | "
            f"Description: {str(event.get('description', ''))[:160]}"
        )
    return "\n".join(lines)


def build_prompt(message: str, history: list[ChatMessage], events_context: str) -> str:
    recent = history[-6:]
    history_text = "\n".join(f"{item.role}: {item.parts}" for item in recent if item.parts)
    return f"""
You are EVENT.AI, an intelligent assistant for Event World -- a Chennai college event discovery platform.
You help students find events, get details, and decide which events to attend.

You have access to all current events on the platform.
Always be helpful, friendly, and concise.
Use emojis occasionally to make responses engaging.
If asked about events not in the database, say you don't have information about that event yet.
Never make up events that don't exist in the data.
Always respond in English.
Keep responses under 150 words unless detailed info is needed.

CURRENT EVENTS ON PLATFORM:
{events_context}

Current date: {datetime.now(timezone.utc).date().isoformat()}
Platform: Event World -- Chennai College Events

Conversation history:
{history_text or "No prior messages."}

Student question:
{message}
""".strip()


@router.post("/chat")
@limiter.limit("10/minute")
async def chat(request: Request, payload: ChatRequest):
    ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    last_request = _last_request_by_ip.get(ip, 0)
    if now - last_request < 2:
        return {"response": "Slow down a little so I can answer properly. Try again in a second."}
    _last_request_by_ip[ip] = now

    events = await db.events.find({"status": "approved"}).sort("date", 1).limit(80).to_list(length=80)
    if not events:
        return {"response": "No events are listed yet. Once institutions submit events and admins approve them, I can help you find the best ones."}

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return {"response": "I'm having trouble connecting right now. Try asking about hackathons, culturals, or workshops!"}

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = build_prompt(payload.message, payload.conversation_history, format_events_for_context(events))
        result = await run_in_threadpool(model.generate_content, prompt)
        response_text = getattr(result, "text", "") or "I could not generate a response right now. Try again!"
        return {"response": response_text.strip()}
    except Exception:
        return {"response": "I'm having trouble connecting right now. Try asking about hackathons, culturals, or workshops!"}
