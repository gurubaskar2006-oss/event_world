import os
import cloudinary
import cloudinary.uploader
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Request
from utils.limiter import limiter
from middleware.auth_guard import require_roles

router = APIRouter(prefix="/api/uploads", tags=["uploads"])

ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp"]
MAX_SIZE = 5 * 1024 * 1024  # 5MB

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_SECRET")
)

@router.post("/upload-poster")
@limiter.limit("5/minute")
async def upload_poster(
    request: Request,
    file: UploadFile = File(...),
    inst: dict = Depends(require_roles("institution", "admin"))
):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Only JPEG, PNG, WebP allowed"
        )

    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(
            status_code=400,
            detail="File too large. Maximum 5MB."
        )

    try:
        result = cloudinary.uploader.upload(
            content,
            folder="event_world/posters",
            resource_type="image"
        )
        return {"url": result["secure_url"]}
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Upload failed. Try again."
        )
