import asyncio
import io
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from PIL import Image

from ..db import new_id, utcnow
from ..deps import current_user, get_db, get_runtime
from ..schemas import DetectionMode
from ..services import audit, search_service
from ..services.app_settings import get_app_settings
from ..services.storage import IMAGE_EXT, VIDEO_EXT, FileTooLarge, get_storage
from ..services.url_guard import UrlError, async_validate

router = APIRouter(prefix="/api/search", tags=["search"])
MAX_IMAGE_BYTES = 15 * 1024 * 1024
IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}


def _ext(upload: UploadFile) -> str:
    return Path(upload.filename or "").suffix.lower()


async def get_accessible(db, search_id: str, user: dict) -> dict:
    s = await db.searches.find_one({"_id": search_id})
    if not s or (user["role"] != "ADMIN" and s["user_id"] != user["_id"]):
        raise HTTPException(404, "Search not found.")  # 404 for foreign ids: do not reveal existence
    return s


@router.post("", status_code=202)
async def create_search(
    request: Request,
    reference_image: UploadFile | None = File(None),
    video: UploadFile | None = File(None),
    video_url: str | None = Form(None),
    detection_mode: str = Form("auto"),
    similarity_threshold: float = Form(...),
    sampling_fps: str | None = Form(None),
    user=Depends(current_user), db=Depends(get_db), runtime=Depends(get_runtime),
):
    storage = get_storage()
    cfg = await get_app_settings(db)
    if reference_image is None or not reference_image.filename:
        raise HTTPException(422, "Reference image is required.")
    if detection_mode not in DetectionMode.__args__:
        raise HTTPException(422, "Detection mode must be person, object or auto.")
    if not 0.5 <= similarity_threshold <= 0.95:
        raise HTTPException(422, "Similarity threshold must be between 0.50 and 0.95.")
    fps_requested = None
    if sampling_fps and sampling_fps.lower() != "auto":
        try:
            fps_requested = float(sampling_fps)
        except ValueError:
            raise HTTPException(422, "Sampling FPS must be a number or AUTO.")
        if not 0.1 <= fps_requested <= 30:
            raise HTTPException(422, "Sampling FPS must be between 0.1 and 30.")
    has_file = video is not None and bool(video.filename)
    has_url = bool(video_url and video_url.strip())
    if has_file == has_url:
        raise HTTPException(422, "Provide either a video file or a video URL, not both." if has_file
                            else "Provide a video file or a video URL.")
    if has_url:
        try:
            video_url = await async_validate(video_url, getattr(request.app.state, "url_resolver", None))
        except UrlError as exc:
            raise HTTPException(422, str(exc))
    elif _ext(video) not in VIDEO_EXT:
        raise HTTPException(422, "Unsupported video type. Use MP4, MOV, AVI, MKV or WEBM.")
    if _ext(reference_image) not in IMAGE_EXT:
        raise HTTPException(422, "Reference image must be JPG, PNG or WEBP.")

    ref_key = video_key = None
    try:
        data = await reference_image.read()
        if len(data) > MAX_IMAGE_BYTES:
            raise HTTPException(422, "Reference image is larger than 15 MB.")
        try:
            with Image.open(io.BytesIO(data)) as im:
                if im.format not in IMAGE_FORMATS:
                    raise HTTPException(422, "Reference image must be JPG, PNG or WEBP.")
                im.verify()
        except HTTPException:
            raise
        except Exception:  # ultralytics patches Image.open, so failures are not always UnidentifiedImageError
            raise HTTPException(422, "The reference image is not a valid image file.")
        ref_key = await asyncio.to_thread(storage.save_reference, user["_id"], _ext(reference_image),
                                          io.BytesIO(data), MAX_IMAGE_BYTES)
        if has_file:
            try:
                video_key = await asyncio.to_thread(storage.save_video, user["_id"], _ext(video), video.file,
                                                    cfg["max_video_mb"] * 1024 * 1024)
            except FileTooLarge:
                raise HTTPException(422, f"The video exceeds the {cfg['max_video_mb']} MB limit.")
            from ..ml.pipeline import VideoError, probe_video
            try:
                await asyncio.to_thread(probe_video, storage.get_file(video_key))
            except VideoError as exc:
                raise HTTPException(422, f"Invalid video: {exc}")
    except HTTPException:
        for k in (ref_key, video_key):
            if k:
                storage.delete_file(k)
        raise

    doc = {
        "_id": new_id(), "user_id": user["_id"], "status": "queued", "stage": "queued", "progress": None,
        "reference_key": ref_key, "reference_filename": reference_image.filename[:120],
        "video_key": video_key, "video_filename": video.filename[:120] if has_file else None,
        "video_url": video_url if has_url else None, "detection_mode": detection_mode,
        "threshold": similarity_threshold, "sampling_fps_requested": fps_requested, "sampling_fps_used": None,
        "match_count": 0, "created_at": utcnow(), "started_at": None, "completed_at": None,
        "error": None, "error_code": None, "media_deleted": False,
    }
    await db.searches.insert_one(doc)
    await audit.record(db, "search.created", actor=user, target=doc["_id"],
                       metadata={"mode": detection_mode, "threshold": similarity_threshold,
                                 "source": "url" if has_url else "upload"})
    search_service.submit(db, runtime, doc["_id"], getattr(request.app.state, "url_resolver", None))
    return {"id": doc["_id"], "status": "queued"}


@router.get("/history")
async def history_alias(skip: int = 0, limit: int = 50, user=Depends(current_user), db=Depends(get_db)):
    from .history import list_own
    return await list_own(skip, limit, None, user, db)


@router.get("/{search_id}")
async def get_search(search_id: str, user=Depends(current_user), db=Depends(get_db)):
    s = await get_accessible(db, search_id, user)
    results = [search_service.serialize_result(r) async for r in
               db.search_results.find({"search_id": search_id}).sort("rank", 1)]
    owner = await db.users.find_one({"_id": s["user_id"]}) if user["role"] == "ADMIN" else None
    return {**search_service.serialize_search(s, owner), "results": results}


@router.get("/{search_id}/frames")
async def get_frames(search_id: str, track_id: int, user=Depends(current_user), db=Depends(get_db)):
    await get_accessible(db, search_id, user)
    frames = [search_service.serialize_frame(f) async for f in
              db.search_frames.find({"search_id": search_id, "track_id": track_id}).sort("frame_index", 1)]
    return {"frames": frames}


@router.get("/{search_id}/frame/{frame_index}")
async def get_frame_image(search_id: str, frame_index: int, user=Depends(current_user), db=Depends(get_db)):
    s = await get_accessible(db, search_id, user)
    if s.get("media_deleted"):
        raise HTTPException(410, "This media was removed by the retention policy.")
    storage = get_storage()
    key = f"frames/{search_id}/{int(frame_index)}.jpg"
    if not storage.exists(key):
        raise HTTPException(404, "Frame not found.")
    return FileResponse(storage.get_file(key), media_type="image/jpeg",
                        headers={"Cache-Control": "private, max-age=3600"})


@router.get("/{search_id}/reference")
async def get_reference(search_id: str, user=Depends(current_user), db=Depends(get_db)):
    s = await get_accessible(db, search_id, user)
    if s.get("media_deleted"):
        raise HTTPException(410, "This media was removed by the retention policy.")
    storage = get_storage()
    if not storage.exists(s["reference_key"]):
        raise HTTPException(404, "Reference image not found.")
    ext = Path(s["reference_key"]).suffix.lower().lstrip(".")
    return FileResponse(storage.get_file(s["reference_key"]),
                        media_type={"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                                    "webp": "image/webp"}.get(ext, "application/octet-stream"),
                        headers={"Cache-Control": "private, max-age=3600"})
