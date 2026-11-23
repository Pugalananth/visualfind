import asyncio
import http.server
import socketserver
import threading
from functools import partial
from pathlib import Path

import pytest

from app.config import get_settings
from app.main import app
from app.services import url_guard
from app.services.storage import get_storage
from .conftest import login, make_user


async def wait_done(client, headers, sid, timeout=180):
    for _ in range(timeout * 4):
        r = await client.get(f"/api/search/{sid}", headers=headers)
        assert r.status_code == 200, r.text
        if r.json()["status"] in ("completed", "failed"):
            return r.json()
        await asyncio.sleep(0.25)
    raise AssertionError("search did not finish")


def files(ref: Path, video: Path | None = None):
    f = {"reference_image": (ref.name, ref.read_bytes(), "image/jpeg")}
    if video:
        f["video"] = (video.name, video.read_bytes(), "video/mp4")
    return f


async def submit(client, headers, scene, mode="person", thr="0.7", video=True, **form):
    data = {"detection_mode": mode, "similarity_threshold": thr, **form}
    return await client.post("/api/search", headers=headers, data=data,
                             files=files(scene["ref"], scene["video"] if video else None))


async def test_person_search_end_to_end(client, user_h, scene):
    r = await submit(client, user_h, scene, mode="person", thr="0.5")
    assert r.status_code == 202, r.text
    s = await wait_done(client, user_h, r.json()["id"])
    assert s["status"] == "completed", s
    assert s["detection_mode"] == "person" and s["threshold"] == 0.5
    assert s["sampling_fps_used"] and s["video_meta"]["frame_count"] == 20
    assert s["match_count"] == len(s["results"]) >= 1
    top = s["results"][0]
    for k in ("track_id", "best_similarity", "track_score", "mean_similarity", "median_similarity", "consistency",
              "first_seen", "last_seen", "match_count", "class_name", "detection_confidence",
              "best_frame_index", "best_bbox"):
        assert k in top
    assert top["class_name"] == "person"
    assert all(t["best_similarity"] >= 0.5 for t in s["results"])
    assert top["first_seen"] <= top["best_timestamp"] <= top["last_seen"]
    # real frame + real bbox
    img = await client.get(f"/api/search/{s['id']}/frame/{top['best_frame_index']}", headers=user_h)
    assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg" and img.content[:2] == b"\xff\xd8"
    fr = (await client.get(f"/api/search/{s['id']}/frames", params={"track_id": top["track_id"]}, headers=user_h)).json()["frames"]
    assert any(f["frame_index"] == top["best_frame_index"] and f["bbox"] == top["best_bbox"] for f in fr)
    assert all(f["has_image"] for f in fr)
    ref = await client.get(f"/api/search/{s['id']}/reference", headers=user_h)
    assert ref.status_code == 200 and ref.headers["content-type"] == "image/jpeg"


async def test_history_persisted_and_isolated(client, db, user_h, admin_h, scene):
    sid = (await submit(client, user_h, scene, thr="0.5")).json()["id"]
    await wait_done(client, user_h, sid)
    await make_user(db, "other@example.com")
    other_h = await login(client, "other@example.com")
    mine = (await client.get("/api/history", headers=user_h)).json()
    assert mine["total"] == 1 and mine["items"][0]["id"] == sid
    assert mine["items"][0]["video_filename"] == "scene.mp4" and mine["items"][0]["threshold"] == 0.5
    assert (await client.get("/api/history", headers=other_h)).json()["total"] == 0
    assert (await client.get("/api/search/history", headers=other_h)).json()["total"] == 0
    for path in (f"/api/search/{sid}", f"/api/search/{sid}/frames?track_id=1", f"/api/search/{sid}/frame/0",
                 f"/api/search/{sid}/reference"):
        assert (await client.get(path, headers=other_h)).status_code == 404, path
    assert (await client.delete(f"/api/history/{sid}", headers=other_h)).status_code == 404
    adm = (await client.get("/api/admin/searches", headers=admin_h)).json()
    assert adm["total"] == 1 and adm["items"][0]["user"]["email"] == "user@example.com"
    assert (await client.get(f"/api/search/{sid}", headers=admin_h)).status_code == 200
    filt = (await client.get("/api/admin/searches", params={"status": "failed"}, headers=admin_h)).json()
    assert filt["total"] == 0
    ov = (await client.get("/api/admin/overview", headers=admin_h)).json()["stats"]
    assert ov["total_searches"] == 1 and ov["completed_searches"] == 1 and ov["total_users"] == 3


async def test_object_mode_reaches_detector_and_excludes_people(client, user_h, scene):
    sid = (await submit(client, user_h, scene, mode="object", thr="0.5")).json()["id"]
    s = await wait_done(client, user_h, sid)
    assert s["status"] == "completed" and s["detection_mode"] == "object"
    assert all(t["class_name"] != "person" for t in s["results"])


async def test_auto_mode_and_explicit_fps(client, user_h, scene):
    sid = (await submit(client, user_h, scene, mode="auto", thr="0.5", sampling_fps="5")).json()["id"]
    s = await wait_done(client, user_h, sid)
    assert s["status"] == "completed" and s["detection_mode"] == "auto"
    assert s["sampling_fps_requested"] == 5.0 and abs(s["sampling_fps_used"] - 5.0) < 0.01


async def test_zero_results_is_a_valid_completed_search(client, user_h, scene):
    sid = (await client.post("/api/search", headers=user_h, data={"detection_mode": "person", "similarity_threshold": "0.9"},
                             files=files(scene["ref"], scene["blank"]))).json()["id"]
    s = await wait_done(client, user_h, sid)
    assert s["status"] == "completed" and s["match_count"] == 0 and s["results"] == []


async def test_threshold_keeps_high_best_with_low_mean():
    from app.ml.pipeline import Sample, aggregate
    mk = lambda i, sim: Sample(i, i / 10, sim, (0, 0, 10, 10), 0.9, "person")
    t = aggregate(1, [mk(0, 0.98)] + [mk(i, 0.2) for i in range(1, 10)], 0.8)
    assert t is not None and t.best_similarity == 0.98 and t.mean_similarity < 0.3 and len(t.matched) == 1
    assert aggregate(2, [mk(0, 0.79), mk(1, 0.5)], 0.8) is None


async def test_input_validation(client, user_h, scene):
    ref, vid = scene["ref"], scene["video"]
    ok = {"detection_mode": "person", "similarity_threshold": "0.7"}
    r = await client.post("/api/search", headers=user_h, data=ok, files={"video": ("v.mp4", vid.read_bytes(), "video/mp4")})
    assert r.status_code == 422 and r.json()["detail"] == "Reference image is required."
    r = await client.post("/api/search", headers=user_h, data=ok, files=files(ref))
    assert r.status_code == 422 and "video" in r.json()["detail"].lower()
    r = await client.post("/api/search", headers=user_h, data={**ok, "video_url": "https://example.com/a.mp4"}, files=files(ref, vid))
    assert r.status_code == 422 and "not both" in r.json()["detail"]
    for bad in ({"detection_mode": "banana"}, {"similarity_threshold": "0.2"}, {"similarity_threshold": "0.99"}, {"sampling_fps": "abc"}):
        r = await client.post("/api/search", headers=user_h, data={**ok, **bad}, files=files(ref, vid))
        assert r.status_code == 422, bad
    r = await client.post("/api/search", headers=user_h, data=ok,
                          files={"reference_image": ("x.jpg", b"not an image", "image/jpeg"), "video": ("v.mp4", vid.read_bytes(), "video/mp4")})
    assert r.status_code == 422 and "not a valid image" in r.json()["detail"]
    r = await client.post("/api/search", headers=user_h, data=ok,
                          files={"reference_image": ("x.gif", ref.read_bytes(), "image/gif"), "video": ("v.mp4", vid.read_bytes(), "video/mp4")})
    assert r.status_code == 422
    r = await client.post("/api/search", headers=user_h, data=ok,
                          files={"reference_image": ("r.jpg", ref.read_bytes(), "image/jpeg"), "video": ("v.mp4", b"garbage", "video/mp4")})
    assert r.status_code == 422 and "Invalid video" in r.json()["detail"]
    r = await client.post("/api/search", headers=user_h, data=ok,
                          files={"reference_image": ("r.jpg", ref.read_bytes(), "image/jpeg"), "video": ("v.exe", b"x", "video/mp4")})
    assert r.status_code == 422
    assert (await client.get("/api/history", headers=user_h)).json()["total"] == 0  # rejected requests leave nothing behind


# ---------------- URL source ----------------
class _Srv:
    def __init__(self, root: Path):
        handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
        handler.log_message = lambda *a, **k: None
        socketserver.TCPServer.allow_reuse_address = True
        self.httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()


@pytest.fixture
def server(scene, tmp_path):
    (tmp_path / "page.html").write_text("<html>hi</html>")
    (tmp_path / "scene.mp4").write_bytes(scene["video"].read_bytes())
    (tmp_path / "fake.mp4").write_bytes(b"this is not a video at all")
    s = _Srv(tmp_path)
    yield s
    s.close()


def allow_local(monkeypatch):
    """Tests only: let the 'localhost' name through the resolver check so a local fixture server can be used.
    The literal-IP and scheme checks stay active."""
    monkeypatch.setattr(app.state, "url_resolver", lambda host, port: ["127.0.0.1"], raising=False)


async def test_url_search_downloads_searches_and_cleans_up(client, user_h, scene, server, monkeypatch):
    allow_local(monkeypatch)
    url = f"http://localhost:{server.port}/scene.mp4"
    r = await client.post("/api/search", headers=user_h, files=files(scene["ref"]),
                          data={"detection_mode": "person", "similarity_threshold": "0.5", "video_url": url})
    assert r.status_code == 202, r.text
    s = await wait_done(client, user_h, r.json()["id"])
    assert s["status"] == "completed", s
    assert s["video_url"] == url and s["video_filename"] == "scene.mp4" and s["match_count"] >= 1
    assert "vf_dl_" not in str(s)  # no temp paths leak
    tmp_root = get_settings().data_dir / "tmp"
    assert not list(tmp_root.glob("vf_dl_*"))  # temp download removed
    stored = await app.state.db.searches.find_one({"_id": s["id"]})
    assert stored["video_key"] is None  # URL videos are never retained


async def test_url_failures_are_reported(client, user_h, scene, server, monkeypatch):
    allow_local(monkeypatch)
    for path, needle in (("page.html", "supported video"), ("missing.mp4", "HTTP 404"), ("fake.mp4", "opened as a video")):
        r = await client.post("/api/search", headers=user_h, files=files(scene["ref"]),
                              data={"detection_mode": "person", "similarity_threshold": "0.5",
                                    "video_url": f"http://localhost:{server.port}/{path}"})
        assert r.status_code == 202
        s = await wait_done(client, user_h, r.json()["id"])
        assert s["status"] == "failed" and needle in s["error"], (path, s["error"])
    assert not list((get_settings().data_dir / "tmp").glob("vf_dl_*"))


async def test_url_size_limit(client, user_h, admin_h, scene, server, monkeypatch):
    allow_local(monkeypatch)
    await app.state.db.app_settings.update_one({"_id": "app"}, {"$set": {"max_url_download_mb": 0}}, upsert=True)  # force tiny cap
    r = await client.post("/api/search", headers=user_h, files=files(scene["ref"]),
                          data={"detection_mode": "person", "similarity_threshold": "0.5",
                                "video_url": f"http://localhost:{server.port}/scene.mp4"})
    s = await wait_done(client, user_h, r.json()["id"])
    assert s["status"] == "failed" and "limit" in s["error"]


@pytest.mark.parametrize("url", [
    "http://localhost/a.mp4", "http://127.0.0.1/a.mp4", "http://127.1.2.3:8000/a.mp4", "http://10.0.0.5/a.mp4",
    "http://192.168.1.1/a.mp4", "http://172.16.0.9/a.mp4", "http://169.254.169.254/latest/meta-data",
    "http://[::1]/a.mp4", "http://0.0.0.0/a.mp4", "http://[::ffff:127.0.0.1]/a.mp4",
    "file:///etc/passwd", "ftp://example.com/a.mp4", "gopher://example.com", "javascript:alert(1)",
    "http://user:pw@example.com/a.mp4", "not a url", "", "http://",
])
async def test_ssrf_and_bad_urls_rejected(client, user_h, scene, url):
    r = await client.post("/api/search", headers=user_h, files=files(scene["ref"]),
                          data={"detection_mode": "person", "similarity_threshold": "0.5", "video_url": url or " "})
    assert r.status_code == 422, (url, r.text)
    assert (await client.get("/api/history", headers=user_h)).json()["total"] == 0


async def test_redirect_to_internal_address_blocked(scene, tmp_path):
    class Redirect(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(302)
            self.send_header("Location", "http://169.254.169.254/latest/meta-data")
            self.end_headers()
        log_message = lambda *a, **k: None
    httpd = socketserver.TCPServer(("127.0.0.1", 0), Redirect)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        with pytest.raises(url_guard.UrlError):
            await url_guard.download_video(f"http://localhost:{httpd.server_address[1]}/x.mp4", tmp_path, 10**7, 10,
                                           resolver=lambda h, p: ["127.0.0.1"] if h == "localhost" else url_guard.resolve_public(h, p))
    finally:
        httpd.shutdown()


async def test_interrupted_jobs_marked_failed_on_restart(db, runtime):
    from app.db import utcnow
    app.state.db, app.state.runtime = db, runtime
    await db.searches.insert_one({"_id": "s1", "user_id": "u", "status": "processing", "detection_mode": "auto",
                                  "threshold": 0.7, "created_at": utcnow()})
    async with app.router.lifespan_context(app):
        pass
    s = await db.searches.find_one({"_id": "s1"})
    assert s["status"] == "failed" and s["error_code"] == "interrupted"


async def test_admin_user_filter_and_clear_history(client, user_h, admin_h, scene):
    sid = (await submit(client, user_h, scene, thr="0.5")).json()["id"]
    await wait_done(client, user_h, sid)
    assert (await client.get("/api/admin/searches", params={"user": "user@exam"}, headers=admin_h)).json()["total"] == 1
    assert (await client.get("/api/admin/searches", params={"user": "nobody"}, headers=admin_h)).json()["total"] == 0
    assert (await client.delete("/api/history", headers=user_h)).json()["deleted"] == 1
    assert (await client.get("/api/history", headers=user_h)).json()["total"] == 0
    assert not get_storage().exists(f"frames/{sid}/0.jpg")
