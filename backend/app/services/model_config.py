import time

import httpx

from ..config import get_settings
from ..db import iso, utcnow
from ..security import decrypt_secret, encrypt_secret
from .url_guard import DownloadError, UrlError, validate_url

UNSUPPORTED = "Connection test is not supported for this provider."


async def get_config(db) -> dict | None:
    return await db.model_config.find_one({"_id": "default"})


def public(doc: dict | None) -> dict:
    if not doc:
        return {"configured": False}
    return {
        "configured": True, "provider": doc["provider"], "model_name": doc["model_name"],
        "endpoint_url": doc["endpoint_url"], "version": doc.get("version"), "options": doc.get("options") or {},
        "has_api_key": bool(doc.get("api_key_enc")),  # the key itself is never returned
        "status": doc.get("status", "NOT_TESTED"), "last_test": doc.get("last_test"),
        "updated_at": iso(doc.get("updated_at")),
    }


async def save_config(db, data: dict) -> dict:
    validate_url(data["endpoint_url"])  # SSRF-safe endpoint
    existing = await get_config(db) or {}
    doc = {
        "provider": data["provider"], "model_name": data["model_name"].strip(),
        "endpoint_url": data["endpoint_url"].strip(), "version": data.get("version"),
        "options": data.get("options") or {}, "updated_at": utcnow(),
        "api_key_enc": encrypt_secret(data["api_key"]) if data.get("api_key") else existing.get("api_key_enc"),
        "status": "NOT_TESTED", "last_test": None,
    }
    await db.model_config.update_one({"_id": "default"}, {"$set": doc}, upsert=True)
    return await get_config(db)


async def test_connection(db) -> dict:
    doc = await get_config(db)
    if not doc:
        return {"connected": False, "status": "NOT_CONFIGURED", "message": "No model connection is configured."}
    base = {"provider": doc["provider"], "model": doc["model_name"]}
    if doc["provider"] != "custom":
        res = {**base, "connected": False, "status": "UNSUPPORTED", "latency_ms": None, "message": UNSUPPORTED}
    else:
        res = await _http_probe(doc, base)
    stored = {**res, "at": iso(utcnow())}
    await db.model_config.update_one({"_id": "default"}, {"$set": {"status": res["status"], "last_test": stored}})
    return res


async def _http_probe(doc: dict, base: dict) -> dict:
    headers = {"User-Agent": "VisualFind/1.0"}
    key = decrypt_secret(doc["api_key_enc"]) if doc.get("api_key_enc") else None
    if key:
        headers["Authorization"] = f"Bearer {key}"
    try:
        validate_url(doc["endpoint_url"])
        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=10, follow_redirects=False,
                                     trust_env=get_settings().url_use_env_proxy) as client:
            r = await client.get(doc["endpoint_url"], headers=headers)
        ms = round((time.perf_counter() - start) * 1000)
        ok = r.status_code < 400
        return {**base, "connected": ok, "status": "CONNECTED" if ok else "CONNECTION_FAILED", "latency_ms": ms,
                "message": "Endpoint reachable." if ok else f"Endpoint answered HTTP {r.status_code}."}
    except (UrlError, DownloadError) as exc:
        return {**base, "connected": False, "status": "CONNECTION_FAILED", "latency_ms": None, "message": str(exc)}
    except httpx.TimeoutException:
        return {**base, "connected": False, "status": "CONNECTION_FAILED", "latency_ms": None,
                "message": "The endpoint did not respond within 10 seconds."}
    except httpx.HTTPError:
        return {**base, "connected": False, "status": "CONNECTION_FAILED", "latency_ms": None,
                "message": "The endpoint could not be reached."}
