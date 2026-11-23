import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from . import db as dbmod
from .config import get_settings
from .db import iso, utcnow
from .ml.runtime import MLRuntime
from .routers import admin, auth, history, model, profile, public, search
from .services import search_service

log = logging.getLogger("visualfind")
DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


async def _retention_loop(app):
    while True:
        try:
            await search_service.apply_retention(app.state.db)
        except Exception:
            log.exception("retention run failed")
        await asyncio.sleep(3600)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if not hasattr(app.state, "db"):
        app.state.client, app.state.db = dbmod.connect(settings.mongodb_uri, settings.mongodb_db_name)
    await dbmod.ensure_indexes(app.state.db)
    if not hasattr(app.state, "runtime"):
        app.state.runtime = MLRuntime(settings)
        if settings.load_models_on_startup:
            asyncio.get_running_loop().run_in_executor(None, app.state.runtime.load)
    # jobs interrupted by a restart can never finish: say so instead of showing them as running
    await app.state.db.searches.update_many(
        {"status": {"$in": ["queued", "processing"]}},
        {"$set": {"status": "failed", "stage": "failed", "error_code": "interrupted", "completed_at": utcnow(),
                  "error": "The server restarted while this search was running. Please run it again."}})
    task = asyncio.create_task(_retention_loop(app))
    yield
    task.cancel()


app = FastAPI(title="VisualFind API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_list, allow_credentials=False,
                   allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    msgs = []
    for e in exc.errors():
        loc = ".".join(str(p) for p in e["loc"] if p not in ("body", "query", "path"))
        msgs.append(f"{loc}: {e['msg']}" if loc else e["msg"])
    return JSONResponse(status_code=422, content={"detail": "Please check the inputs. " + "; ".join(msgs[:4])})


@app.get("/api/health")
async def health(request: Request):
    try:
        await request.app.state.db.command("ping")
        database = "ok"
    except Exception:
        database = "unavailable"
    rt = request.app.state.runtime
    return {"status": "ok" if database == "ok" else "degraded", "time": iso(utcnow()), "database": database,
            "encoder": rt.encoder_state["status"], "detector": rt.detector_state["status"]}


for r in (auth.router, search.router, history.router, profile.router, admin.router, model.router, public.router):
    app.include_router(r)


if DIST.is_dir():
    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "Not found.")
        f = (DIST / path).resolve()
        if path and DIST in f.parents and f.is_file():
            return FileResponse(f)
        return FileResponse(DIST / "index.html")
