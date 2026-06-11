from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi import Request

from database import create_indexes
from routes import admin, ai, auth, events, notifications, payments, uploads
from utils.limiter import limiter
from slowapi.errors import RateLimitExceeded

app = FastAPI(title="Event World API", version="1.0.0")
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Try again later."}
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"Internal error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong. Please try again."}
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://event-world.onrender.com",
        "http://localhost",
        "http://localhost:5500",
        "http://localhost:8000",
        "http://127.0.0.1:5500",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router)
app.include_router(events.router)
app.include_router(events.ticket_router)
app.include_router(events.stats_router)
app.include_router(events.institution_router)
app.include_router(payments.router)
app.include_router(ai.router, prefix="/api/ai")
app.include_router(admin.router)
app.include_router(notifications.router)
app.include_router(uploads.router)

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
    "institution.html",
    "attendees.html",
    "gate-scanner.html",
    "event-data.js",
    "notifications.js",
    "ticket.html",
    "sitemap.xml",
    "robots.txt",
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


@app.get("/sitemap.xml")
async def sitemap():
    return FileResponse(FRONTEND_ROOT / "sitemap.xml", media_type="application/xml")

@app.get("/robots.txt")
async def robots():
    return FileResponse(FRONTEND_ROOT / "robots.txt", media_type="text/plain")


@app.get("/{file_name}")
async def frontend_file(file_name: str):
    if file_name in PUBLIC_FILES and (FRONTEND_ROOT / file_name).exists():
        return FileResponse(FRONTEND_ROOT / file_name, headers={"Cache-Control": "no-store, max-age=0"})
    return FileResponse(FRONTEND_ROOT / "index.html", headers={"Cache-Control": "no-store, max-age=0"})
