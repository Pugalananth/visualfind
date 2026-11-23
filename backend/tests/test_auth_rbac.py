from .conftest import PW, login, make_user


async def test_register_login_me_flow(client, db):
    r = await client.post("/api/auth/register", json={"name": "Ana Dev", "email": "Ana@Example.com",
                                                       "password": PW, "confirm_password": PW})
    assert r.status_code == 201 and r.json()["role"] == "USER"
    stored = await db.users.find_one({"email": "ana@example.com"})
    assert stored["password_hash"] != PW and stored["password_hash"].startswith("$2")
    h = await login(client, "ana@example.com")
    me = (await client.get("/api/auth/me", headers=h)).json()
    assert set(me) == {"id", "name", "email", "role"} and me["role"] == "USER"


async def test_register_cannot_create_admin(client, db):
    r = await client.post("/api/auth/register", json={"name": "Eve Evil", "email": "eve@example.com", "password": PW,
                                                       "confirm_password": PW, "role": "ADMIN", "is_active": True})
    assert r.status_code == 201
    assert (await db.users.find_one({"email": "eve@example.com"}))["role"] == "USER"


async def test_register_validation(client):
    base = {"name": "Ana Dev", "email": "ana@example.com"}
    assert (await client.post("/api/auth/register", json={**base, "password": "weak", "confirm_password": "weak"})).status_code == 422
    assert (await client.post("/api/auth/register", json={**base, "password": PW, "confirm_password": PW + "x"})).status_code == 422
    assert (await client.post("/api/auth/register", json={**base, "email": "nope", "password": PW, "confirm_password": PW})).status_code == 422
    assert (await client.post("/api/auth/register", json={"email": "a@b.co", "password": PW, "confirm_password": PW})).status_code == 422
    assert (await client.post("/api/auth/register", json={**base, "password": PW, "confirm_password": PW})).status_code == 201
    dup = await client.post("/api/auth/register", json={**base, "password": PW, "confirm_password": PW})
    assert dup.status_code == 409


async def test_login_failures(client, db):
    await make_user(db)
    assert (await client.post("/api/auth/login", json={"email": "user@example.com", "password": "Wrong1234"})).status_code == 401
    assert (await client.post("/api/auth/login", json={"email": "ghost@example.com", "password": PW})).status_code == 401


async def test_login_lockout(client, db):
    await make_user(db, "lock@example.com")
    for _ in range(5):
        await client.post("/api/auth/login", json={"email": "lock@example.com", "password": "Wrong1234"})
    r = await client.post("/api/auth/login", json={"email": "lock@example.com", "password": PW})
    assert r.status_code == 429


async def test_protected_endpoints_require_auth(client):
    for path in ("/api/auth/me", "/api/history", "/api/profile", "/api/search/history", "/api/admin/overview",
                 "/api/admin/users", "/api/model"):
        assert (await client.get(path)).status_code == 401, path
    assert (await client.get("/api/auth/me", headers={"Authorization": "Bearer garbage"})).status_code == 401


ADMIN_GETS = ["/api/admin/overview", "/api/admin/users", "/api/admin/searches", "/api/admin/jobs",
              "/api/admin/system", "/api/admin/audit-logs", "/api/admin/settings", "/api/model"]


async def test_user_forbidden_on_all_admin_routes(client, user_h):
    for path in ADMIN_GETS:
        assert (await client.get(path, headers=user_h)).status_code == 403, path
    assert (await client.put("/api/admin/settings", json={"retention_days": 1}, headers=user_h)).status_code == 403
    assert (await client.patch("/api/admin/users/x", json={"role": "ADMIN"}, headers=user_h)).status_code == 403
    assert (await client.post("/api/model/test", headers=user_h)).status_code == 403


async def test_admin_allowed_on_admin_routes(client, admin_h):
    for path in ADMIN_GETS:
        r = await client.get(path, headers=admin_h)
        assert r.status_code == 200, (path, r.text)


async def test_admin_user_management_and_audit(client, db, admin_h):
    u = await make_user(db, "bob@example.com", name="Bob")
    r = await client.patch(f"/api/admin/users/{u['_id']}", json={"is_active": False}, headers=admin_h)
    assert r.status_code == 200 and r.json()["is_active"] is False
    bad = await client.post("/api/auth/login", json={"email": "bob@example.com", "password": PW})
    assert bad.status_code == 403
    await client.patch(f"/api/admin/users/{u['_id']}", json={"is_active": True}, headers=admin_h)
    await client.patch(f"/api/admin/users/{u['_id']}", json={"role": "ADMIN"}, headers=admin_h)
    assert (await db.users.find_one({"_id": u["_id"]}))["role"] == "ADMIN"
    logs = (await client.get("/api/admin/audit-logs", headers=admin_h)).json()["items"]
    actions = {x["action"] for x in logs}
    assert {"user.deactivated", "user.activated", "admin.changed_user_role", "admin.login"} <= actions
    assert all("password" not in str(x["metadata"]).lower() for x in logs)


async def test_admin_cannot_lock_self_out(client, db, admin_h):
    me = (await client.get("/api/auth/me", headers=admin_h)).json()
    assert (await client.patch(f"/api/admin/users/{me['id']}", json={"is_active": False}, headers=admin_h)).status_code == 409
    assert (await client.patch(f"/api/admin/users/{me['id']}", json={"role": "USER"}, headers=admin_h)).status_code == 409


async def test_deactivated_user_token_stops_working(client, db, admin_h):
    u = await make_user(db, "carl@example.com")
    h = await login(client, "carl@example.com")
    await client.patch(f"/api/admin/users/{u['_id']}", json={"is_active": False}, headers=admin_h)
    assert (await client.get("/api/auth/me", headers=h)).status_code == 403


async def test_profile_cannot_escalate(client, user_h, db):
    r = await client.patch("/api/profile", json={"name": "New Name", "role": "ADMIN", "is_active": False}, headers=user_h)
    assert r.status_code == 200 and r.json()["role"] == "USER" and r.json()["name"] == "New Name"
    p = (await client.get("/api/profile", headers=user_h)).json()
    assert p["search_count"] == 0 and p["role"] == "USER"


async def test_password_change_invalidates_old_token(client, user_h):
    r = await client.post("/api/profile/password", headers=user_h,
                          json={"current_password": PW, "new_password": "NewPass123", "confirm_password": "NewPass123"})
    assert r.status_code == 200
    assert (await client.get("/api/auth/me", headers=user_h)).status_code == 401
    new_h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert (await client.get("/api/auth/me", headers=new_h)).status_code == 200


async def test_password_reset_flow(client, db, caplog):
    await make_user(db, "reset@example.com")
    with caplog.at_level("WARNING", logger="visualfind.auth"):
        assert (await client.post("/api/auth/forgot-password", json={"email": "reset@example.com"})).status_code == 200
        assert (await client.post("/api/auth/forgot-password", json={"email": "nobody@example.com"})).status_code == 200
    token = [r.message for r in caplog.records if "reset-password?token=" in r.message][0].split("token=")[1]
    r = await client.post("/api/auth/reset-password", json={"token": token, "password": "Another123", "confirm_password": "Another123"})
    assert r.status_code == 200
    assert (await client.post("/api/auth/reset-password", json={"token": token, "password": "Another123", "confirm_password": "Another123"})).status_code == 400
    await login(client, "reset@example.com", "Another123")


async def test_registration_can_be_disabled(client, admin_h):
    await client.put("/api/admin/settings", json={"registration_enabled": False}, headers=admin_h)
    r = await client.post("/api/auth/register", json={"name": "Zed Zed", "email": "z@example.com", "password": PW, "confirm_password": PW})
    assert r.status_code == 403


async def test_health(client):
    r = await client.get("/api/health")
    assert r.status_code == 200, r.text
    assert r.json()["encoder"] == "READY" and r.json()["detector"] == "READY"
