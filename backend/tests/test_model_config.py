import http.server
import socketserver
import threading

import pytest

from app.services import url_guard


@pytest.fixture
def endpoint(monkeypatch):
    seen = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            seen["auth"] = self.headers.get("Authorization")
            code = 200 if self.path == "/ok" else 503
            self.send_response(code)
            self.end_headers()
        log_message = lambda *a, **k: None
    httpd = socketserver.TCPServer(("127.0.0.1", 0), H)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    monkeypatch.setattr(url_guard, "resolve_public", lambda host, port: ["127.0.0.1"])
    yield httpd.server_address[1], seen
    httpd.httpd = None
    httpd.shutdown()


def body(port, path="ok", provider="custom", key="sk-secret-123"):
    return {"provider": provider, "model_name": "VisualFind Encoder", "endpoint_url": f"http://localhost:{port}/{path}",
            "api_key": key, "version": "1.0"}


async def test_connection_flow_never_exposes_key(client, admin_h, db, endpoint):
    port, seen = endpoint
    r = await client.put("/api/model", json=body(port), headers=admin_h)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["test"]["connected"] is True and j["test"]["status"] == "CONNECTED" and j["test"]["latency_ms"] is not None
    assert j["config"]["has_api_key"] is True and "sk-secret-123" not in r.text
    assert seen["auth"] == "Bearer sk-secret-123"
    stored = await db.model_config.find_one({"_id": "default"})
    assert "sk-secret-123" not in str(stored) and stored["api_key_enc"]
    g = await client.get("/api/model", headers=admin_h)
    assert "sk-secret-123" not in g.text and g.json()["status"] == "CONNECTED"
    # updating without a key keeps the stored one
    r = await client.put("/api/model", json={**body(port), "api_key": None, "version": "2"}, headers=admin_h)
    assert r.json()["config"]["has_api_key"] is True and r.json()["config"]["version"] == "2"
    logs = (await client.get("/api/admin/audit-logs", headers=admin_h)).json()["items"]
    assert any(l["action"] == "admin.model_config_saved" for l in logs) and "sk-secret" not in str(logs)


async def test_failed_and_unsupported(client, admin_h, endpoint):
    port, _ = endpoint
    r = await client.put("/api/model", json=body(port, "down"), headers=admin_h)
    assert r.json()["test"]["status"] == "CONNECTION_FAILED" and "503" in r.json()["test"]["message"]
    r = await client.put("/api/model", json=body(port, provider="aws_sagemaker"), headers=admin_h)
    assert r.json()["test"]["status"] == "UNSUPPORTED"
    assert r.json()["test"]["message"] == "Connection test is not supported for this provider."
    t = await client.post("/api/model/test", headers=admin_h)
    assert t.json()["connected"] is False


async def test_unreachable_and_ssrf_endpoint(client, admin_h):
    r = await client.put("/api/model", json={**body(1), "endpoint_url": "http://127.0.0.1:9/x"}, headers=admin_h)
    assert r.status_code == 422
    r = await client.put("/api/model", json={**body(1), "endpoint_url": "file:///etc/passwd"}, headers=admin_h)
    assert r.status_code == 422
    r = await client.put("/api/model", json={**body(1), "provider": "nonsense"}, headers=admin_h)
    assert r.status_code == 422


async def test_test_without_config(client, admin_h):
    r = await client.post("/api/model/test", headers=admin_h)
    assert r.status_code == 200 and r.json()["status"] == "NOT_CONFIGURED"


async def test_system_status_is_real(client, admin_h):
    s = {x["name"]: x for x in (await client.get("/api/admin/system", headers=admin_h)).json()["services"]}
    assert s["API"]["status"] == "ONLINE" and s["Database"]["status"] == "ONLINE" and s["Storage"]["status"] == "ONLINE"
    assert s["Encoder"]["status"] == "READY" and s["YOLO detector"]["status"] == "READY"
