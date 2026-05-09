from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from database import create_indexes
from routes import admin, auth, events, notifications

app = FastAPI(title="Event World API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://localhost:5500",
        "http://localhost:8000",
        "http://127.0.0.1:5500",
        "http://127.0.0.1:8000",
        "null",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(events.router)
app.include_router(events.ticket_router)
app.include_router(admin.router)
app.include_router(notifications.router)

FRONTEND_ROOT = Path(__file__).resolve().parent.parent
PUBLIC_FILES = {
    "index.html",
    "Login.html",
    "register.html",
    "events.html",
    "event-detail.html",
    "submit-event.html",
    "admin.html",
    "admin-login.html",
    "dashboard.html",
    "event-data.js",
    "notifications.js",
    "ticket.html",
}


@app.on_event("startup")
async def startup() -> None:
    await create_indexes()


@app.get("/api/health")
async def health():
    return {"ok": True, "service": "event-world-api"}


@app.get("/")
async def frontend_index():
    return FileResponse(FRONTEND_ROOT / "index.html", headers={"Cache-Control": "no-store, max-age=0"})


@app.head("/")
async def frontend_index_head():
    return {"ok": True}


@app.get("/{file_name}")
async def frontend_file(file_name: str):
    if file_name in PUBLIC_FILES and (FRONTEND_ROOT / file_name).exists():
        return FileResponse(FRONTEND_ROOT / file_name, headers={"Cache-Control": "no-store, max-age=0"})
    return FileResponse(FRONTEND_ROOT / "index.html", headers={"Cache-Control": "no-store, max-age=0"})
