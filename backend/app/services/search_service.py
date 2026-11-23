"""Search lifecycle: queued -> processing(stage) -> completed | failed. Status/stage live in
MongoDB, so what the UI and admin Jobs page show is the real state of the job."""
import asyncio
import logging
import shutil
import tempfile
from pathlib import Path

from ..config import get_settings
from ..db import iso, new_id, utcnow
from ..ml import pipeline
from ..ml.pipeline import VideoError
from . import audit
from .app_settings import get_app_settings
from .emailer import send_email
from .storage import get_storage
from .url_guard import DownloadError, UrlError, download_video

log = logging.getLogger("visualfind.search")
STAGES = ["queued", "preparing_reference", "preparing_video", "analysing", "ranking", "complete"]
_sem: asyncio.Semaphore | None = None
_tasks: set[asyncio.Task] = set()


def _semaphore() -> asyncio.Semaphore:
    global _sem
    if _sem is None:
        _sem = asyncio.Semaphore(max(get_settings().search_concurrency, 1))
    return _sem


def reset_semaphore() -> None:
    global _sem
    _sem = None


def submit(db, runtime, search_id: str, resolver=None) -> asyncio.Task:
    task = asyncio.create_task(_run_guarded(db, runtime, search_id, resolver))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return task


async def wait_all() -> None:
    if _tasks:
        await asyncio.gather(*list(_tasks), return_exceptions=True)


async def _set(db, search_id: str, **fields):
    await db.searches.update_one({"_id": search_id}, {"$set": fields})


async def _run_guarded(db, runtime, search_id, resolver):
    async with _semaphore():
        await _run(db, runtime, search_id, resolver)


async def _run(db, runtime, search_id: str, resolver=None):
    storage = get_storage()
    search = await db.searches.find_one({"_id": search_id})
    if not search:
        return
    user = await db.users.find_one({"_id": search["user_id"]})
    tmp_dir: Path | None = None
    loop = asyncio.get_running_loop()
    try:
        cfg = await get_app_settings(db)
        await _set(db, search_id, status="processing", stage="preparing_reference", started_at=utcnow())
        runtime.ensure_ready()
        ref_path = storage.get_file(search["reference_key"])
        try:
            ref_emb = await asyncio.to_thread(runtime.encoder.embed_file, ref_path)
        except Exception as exc:
            raise _Fail("invalid_image", "The reference image could not be processed.") from exc

        await _set(db, search_id, stage="preparing_video")
        if search.get("video_url"):
            tmp_dir = Path(tempfile.mkdtemp(prefix="vf_dl_", dir=_tmp_root()))
            try:
                video_path, vname = await download_video(search["video_url"], tmp_dir,
                                                         cfg["max_url_download_mb"] * 1024 * 1024,
                                                         cfg["url_download_timeout_s"], resolver)
            except UrlError as exc:
                raise _Fail("invalid_url", str(exc)) from exc
            except DownloadError as exc:
                raise _Fail("download_failed", str(exc)) from exc
            await _set(db, search_id, video_filename=vname)
        else:
            video_path = storage.get_file(search["video_key"])
        try:
            meta = await asyncio.to_thread(pipeline.probe_video, video_path)
        except VideoError as exc:
            raise _Fail("invalid_video", str(exc)) from exc
        await _set(db, search_id, video_meta={"fps": meta.fps, "frame_count": meta.frame_count, "width": meta.width,
                                              "height": meta.height, "duration": meta.duration})

        await _set(db, search_id, stage="analysing", progress={"processed": 0, "total": 0})

        def progress(done, total):
            asyncio.run_coroutine_threadsafe(_set(db, search_id, progress={"processed": done, "total": total}), loop)

        try:
            out = await asyncio.to_thread(
                pipeline.run_search, video_path, ref_emb, search["detection_mode"], search["threshold"],
                search.get("sampling_fps_requested"), runtime.encoder, runtime.detector,
                cfg["max_sampled_frames"], progress)
        except VideoError as exc:
            raise _Fail("invalid_video", str(exc)) from exc
        except Exception as exc:
            log.exception("pipeline failure")
            raise _Fail("model_failure", "The detection or embedding model failed while processing the video.") from exc

        await _set(db, search_id, stage="ranking", sampling_fps_used=out.sampling_fps_used,
                   progress={"processed": out.frames_processed, "total": out.frames_processed})
        await _persist_results(db, storage, search_id, out, video_path)
        await _set(db, search_id, status="completed", stage="complete", match_count=len(out.tracks),
                   completed_at=utcnow(), error=None, error_code=None)
        await audit.record(db, "search.completed", actor=user, target=search_id,
                           metadata={"matches": len(out.tracks), "mode": search["detection_mode"]})
        if user and user.get("notify_on_complete"):
            await asyncio.to_thread(send_email, user["email"], "Your VisualFind search is complete",
                                    f"Search {search_id} finished with {len(out.tracks)} match(es).")
    except _Fail as f:
        await _fail(db, search_id, user, f.code, f.message)
    except Exception as exc:
        log.exception("search %s failed", search_id)
        text = str(exc)
        if isinstance(exc, RuntimeError) and text.startswith(("encoder:", "detector:")):
            await _fail(db, search_id, user, "model_unavailable",
                        f"The {text.split(':', 1)[0]} is not ready. An administrator should check System status.")
        else:
            await _fail(db, search_id, user, "internal", "VisualFind encountered an internal processing error.")
    finally:
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)  # downloaded video is never kept


class _Fail(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


async def _fail(db, search_id, user, code, message):
    await _set(db, search_id, status="failed", stage="failed", error=message, error_code=code, completed_at=utcnow())
    await audit.record(db, "search.failed", actor=user, target=search_id, metadata={"code": code, "error": message})


def _tmp_root() -> Path:
    root = get_settings().data_dir / "tmp"
    root.mkdir(parents=True, exist_ok=True)
    return root


async def _persist_results(db, storage, search_id, out, video_path):
    saved: dict[int, list] = {t.track_id: pipeline.pick_saved_samples(t) for t in out.tracks}
    wanted = [s.frame_index for ss in saved.values() for s in ss]
    frames = await asyncio.to_thread(pipeline.extract_frames, video_path, wanted)
    for idx, data in frames.items():
        await asyncio.to_thread(storage.save_frame, search_id, idx, data)
    await db.search_results.delete_many({"search_id": search_id})
    await db.search_frames.delete_many({"search_id": search_id})
    results, frame_docs = [], []
    for rank, t in enumerate(out.tracks, start=1):
        results.append({
            "_id": new_id(), "search_id": search_id, "rank": rank, "track_id": t.track_id,
            "best_similarity": t.best_similarity, "track_score": t.track_score,
            "mean_similarity": t.mean_similarity, "median_similarity": t.median_similarity,
            "consistency": t.consistency, "first_seen": t.first_seen, "last_seen": t.last_seen,
            "match_count": len(t.matched), "total_samples": len(t.samples), "class_name": t.cls_name,
            "detection_confidence": t.best.conf, "best_frame_index": t.best.frame_index,
            "best_timestamp": t.best.timestamp, "best_bbox": list(t.best.bbox),
        })
        for s in saved[t.track_id]:
            frame_docs.append({
                "_id": new_id(), "search_id": search_id, "track_id": t.track_id, "frame_index": s.frame_index,
                "timestamp": s.timestamp, "similarity": s.similarity, "bbox": list(s.bbox),
                "confidence": s.conf, "class_name": s.cls_name, "has_image": s.frame_index in frames,
                "width": out.meta.width, "height": out.meta.height,
            })
    if results:
        await db.search_results.insert_many(results)
    if frame_docs:
        await db.search_frames.insert_many(frame_docs)


def serialize_search(doc: dict, owner: dict | None = None) -> dict:
    out = {
        "id": doc["_id"], "user_id": doc["user_id"], "status": doc["status"], "stage": doc.get("stage"),
        "progress": doc.get("progress"), "reference_filename": doc.get("reference_filename"),
        "video_filename": doc.get("video_filename"), "video_url": doc.get("video_url"),
        "detection_mode": doc["detection_mode"], "threshold": doc["threshold"],
        "sampling_fps_requested": doc.get("sampling_fps_requested"), "sampling_fps_used": doc.get("sampling_fps_used"),
        "match_count": doc.get("match_count", 0), "video_meta": doc.get("video_meta"),
        "error": doc.get("error"), "error_code": doc.get("error_code"), "media_deleted": doc.get("media_deleted", False),
        "created_at": iso(doc["created_at"]), "started_at": iso(doc.get("started_at")),
        "completed_at": iso(doc.get("completed_at")),
    }
    if owner:
        out["user"] = {"id": owner["_id"], "name": owner["name"], "email": owner["email"]}
    return out


def serialize_result(r: dict) -> dict:
    return {k: r[k] for k in (
        "track_id", "rank", "best_similarity", "track_score", "mean_similarity", "median_similarity",
        "consistency", "first_seen", "last_seen", "match_count", "total_samples", "class_name",
        "detection_confidence", "best_frame_index", "best_timestamp", "best_bbox")}


def serialize_frame(f: dict) -> dict:
    return {k: f[k] for k in ("track_id", "frame_index", "timestamp", "similarity", "bbox",
                              "confidence", "class_name", "has_image", "width", "height")}


async def delete_search_media(db, search: dict) -> None:
    storage = get_storage()
    for key in (search.get("reference_key"), search.get("video_key")):
        if key:
            await asyncio.to_thread(storage.delete_file, key)
    await asyncio.to_thread(storage.delete_prefix, f"frames/{search['_id']}")


async def purge_search(db, search: dict) -> None:
    await delete_search_media(db, search)
    await db.search_results.delete_many({"search_id": search["_id"]})
    await db.search_frames.delete_many({"search_id": search["_id"]})
    await db.searches.delete_one({"_id": search["_id"]})


async def apply_retention(db) -> int:
    cfg = await get_app_settings(db)
    days = cfg["retention_days"]
    if not days:
        return 0
    from datetime import timedelta
    cutoff = utcnow() - timedelta(days=days)
    n = 0
    async for s in db.searches.find({"created_at": {"$lt": cutoff}, "media_deleted": {"$ne": True},
                                     "status": {"$in": ["completed", "failed"]}}):
        await delete_search_media(db, s)
        await db.searches.update_one({"_id": s["_id"]}, {"$set": {"media_deleted": True}})
        n += 1
    if n:
        await audit.record(db, "retention.media_deleted", metadata={"searches": n, "retention_days": days})
    return n
