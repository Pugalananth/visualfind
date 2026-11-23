import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="vf_test_"))
os.environ.update({
    "DATA_DIR": str(_TMP / "data"),
    "ENCODER_CHECKPOINT": str(_TMP / "test_encoder.pth"),
    "YOLO_WEIGHTS": str(Path(__file__).resolve().parents[1] / "models" / "yolov8n.pt"),
    "LOAD_MODELS_ON_STARTUP": "false",
    "DEVICE": "cpu",
})

import cv2  # noqa: E402
import httpx  # noqa: E402
import numpy as np  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
import torch  # noqa: E402
from mongomock_motor import AsyncMongoMockClient  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import ensure_indexes  # noqa: E402
from app.main import app  # noqa: E402
from app.ml.encoder import VisualFindEncoder  # noqa: E402
from app.ml.runtime import MLRuntime  # noqa: E402
from app.services import search_service  # noqa: E402
from app.services.storage import reset_storage  # noqa: E402
from app.services.users import create_user  # noqa: E402

PW = "Str0ngPass"


@pytest.fixture(scope="session")
def runtime():
    """Real YOLO + the real encoder architecture. The checkpoint is a TEST FIXTURE with
    random weights (the production checkpoint is not part of the repo): these tests validate
    plumbing, auth and aggregation, not embedding quality."""
    torch.manual_seed(0)
    torch.save(VisualFindEncoder().state_dict(), os.environ["ENCODER_CHECKPOINT"])
    rt = MLRuntime(get_settings())
    rt.load()
    assert rt.encoder_state["status"] == "READY", rt.encoder_state
    assert rt.detector_state["status"] == "READY", rt.detector_state
    return rt


@pytest_asyncio.fixture
async def db():
    reset_storage()
    search_service.reset_semaphore()
    d = AsyncMongoMockClient()["vf_test"]
    await ensure_indexes(d)
    return d


@pytest_asyncio.fixture
async def client(db, runtime):
    app.state.db = db
    app.state.runtime = runtime
    app.state.url_resolver = None
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await search_service.wait_all()


async def make_user(db, email="user@example.com", role="USER", name="Test User"):
    return await create_user(db, name, email, PW, role=role)


async def login(client, email, password=PW):
    r = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest_asyncio.fixture
async def user_h(client, db):
    await make_user(db)
    return await login(client, "user@example.com")


@pytest_asyncio.fixture
async def admin_h(client, db):
    await make_user(db, "admin@example.com", "ADMIN", "Admin")
    return await login(client, "admin@example.com")


def bus_image() -> np.ndarray:
    import ultralytics
    return cv2.imread(str(Path(ultralytics.__file__).parent / "assets" / "bus.jpg"))


def write_video(path: Path, frames: list[np.ndarray], fps: int = 10):
    h, w = frames[0].shape[:2]
    vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    for f in frames:
        vw.write(f)
    vw.release()
    assert path.stat().st_size > 0


@pytest.fixture(scope="session")
def scene(runtime, tmp_path_factory):
    """A real video made from a real photo (people + a bus) and a reference crop of a person."""
    d = tmp_path_factory.mktemp("media")
    img = bus_image()
    h, w = img.shape[:2]
    frames = []
    for i in range(20):  # 2 s @ 10 fps with a slow pan
        M = np.float32([[1, 0, i * 2], [0, 1, 0]])
        frames.append(cv2.warpAffine(img, M, (w, h)))
    video = d / "scene.mp4"
    write_video(video, frames)
    dets = runtime.detector.model.predict(img, classes=[0], verbose=False, device="cpu")[0].boxes
    x1, y1, x2, y2 = (int(v) for v in dets.xyxy[int(dets.conf.argmax())].tolist())
    ref = d / "person.jpg"
    cv2.imwrite(str(ref), img[y1:y2, x1:x2])
    blank = d / "blank.mp4"
    write_video(blank, [np.full((240, 320, 3), 127, np.uint8)] * 20)
    return {"video": video, "ref": ref, "blank": blank}
