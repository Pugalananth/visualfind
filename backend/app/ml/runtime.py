"""Holds the loaded encoder and detector and reports their real state."""
import logging
import threading

import cv2
import numpy as np
import torch
import torch.nn.functional as F

from ..config import Settings
from .detector import Detector
from .encoder import load_encoder

log = logging.getLogger("visualfind.ml")
MEAN = (0.485, 0.456, 0.406)
STD = (0.229, 0.224, 0.225)


class EncoderService:
    def __init__(self, model, device: str, height: int, width: int, cfg: dict):
        self.model, self.device, self.h, self.w, self.cfg = model, device, height, width, cfg
        self.mean = torch.tensor(MEAN, device=device).view(1, 3, 1, 1)
        self.std = torch.tensor(STD, device=device).view(1, 3, 1, 1)

    def _prep(self, bgr_list: list[np.ndarray]) -> torch.Tensor:
        arrs = []
        for img in bgr_list:
            rgb = cv2.cvtColor(cv2.resize(img, (self.w, self.h), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB)
            arrs.append(torch.from_numpy(rgb))
        x = torch.stack(arrs).to(self.device).permute(0, 3, 1, 2).float() / 255.0
        return (x - self.mean) / self.std

    @torch.inference_mode()
    def embed_bgr(self, bgr_list: list[np.ndarray], batch: int = 32) -> torch.Tensor:
        outs = []
        for i in range(0, len(bgr_list), batch):
            outs.append(F.normalize(self.model(self._prep(bgr_list[i:i + batch])), dim=1))
        return torch.cat(outs)

    def embed_file(self, path) -> torch.Tensor:
        img = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if img is None:
            from PIL import Image
            pil = Image.open(path).convert("RGB")
            img = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
        return self.embed_bgr([img])[0]


class MLRuntime:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.device = ("cuda" if torch.cuda.is_available() else "cpu") if settings.device == "auto" else settings.device
        self.encoder: EncoderService | None = None
        self.detector: Detector | None = None
        self.encoder_state = {"status": "LOADING", "detail": ""}
        self.detector_state = {"status": "LOADING", "detail": ""}
        self._lock = threading.Lock()

    def load(self) -> None:
        with self._lock:
            self._load_encoder()
            self._load_detector()

    def _load_encoder(self):
        s = self.settings
        try:
            model, cfg = load_encoder(s.encoder_checkpoint, self.device)
            self.encoder = EncoderService(model, self.device, s.encoder_input_h, s.encoder_input_w, cfg)
            kind = "bottleneck" if cfg["bottleneck"] else "basic"
            self.encoder_state = {"status": "READY", "detail":
                                  f"{s.encoder_checkpoint.name} · {kind} {cfg['layers']} · {cfg['emb_dim']}-d · {self.device}"}
        except Exception as exc:
            log.warning("encoder not ready: %s", exc)
            self.encoder = None
            self.encoder_state = {"status": "NOT_READY", "detail": str(exc)[:400]}

    def _load_detector(self):
        s = self.settings
        try:
            self.detector = Detector(s.yolo_weights, self.device, s.detector_conf)
            self.detector_state = {"status": "READY", "detail": f"{s.yolo_weights} · {self.device}"}
        except Exception as exc:
            log.warning("detector not ready: %s", exc)
            self.detector = None
            self.detector_state = {"status": "NOT_READY", "detail": str(exc)[:400]}

    def ensure_ready(self):
        if self.encoder is None:
            raise RuntimeError("encoder: " + self.encoder_state["detail"])
        if self.detector is None:
            raise RuntimeError("detector: " + self.detector_state["detail"])
