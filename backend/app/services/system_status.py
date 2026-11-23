import asyncio
import time


async def collect(request) -> list[dict]:
    from ..services.storage import get_storage
    app = request.app
    out = [{"name": "API", "status": "ONLINE", "detail": "Serving requests"}]
    t = time.perf_counter()
    try:
        await asyncio.wait_for(app.state.db.command("ping"), timeout=5)
        out.append({"name": "Database", "status": "ONLINE", "detail": f"MongoDB · {app.state.db.name}",
                    "latency_ms": round((time.perf_counter() - t) * 1000)})
    except Exception as exc:
        out.append({"name": "Database", "status": "OFFLINE", "detail": type(exc).__name__})
    rt = app.state.runtime
    out.append({"name": "Encoder", "status": rt.encoder_state["status"], "detail": rt.encoder_state["detail"]})
    out.append({"name": "YOLO detector", "status": rt.detector_state["status"], "detail": rt.detector_state["detail"]})
    try:
        h = await asyncio.to_thread(get_storage().health)
        out.append({"name": "Storage", "status": "ONLINE" if h["ok"] else "OFFLINE",
                    "detail": f"{h['backend']} · {h['free_gb']} GB free"})
    except Exception as exc:
        out.append({"name": "Storage", "status": "OFFLINE", "detail": type(exc).__name__})
    return out
