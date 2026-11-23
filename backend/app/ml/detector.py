import threading
from dataclasses import dataclass

import numpy as np

PERSON_CLASS = 0


@dataclass
class Det:
    track_id: int
    cls_id: int
    cls_name: str
    conf: float
    bbox: tuple[float, float, float, float]


class DetectorError(Exception):
    pass


class Detector:
    """YOLO detection + ByteTrack tracking (ultralytics)."""

    def __init__(self, weights: str, device: str, conf: float = 0.25):
        from ultralytics import YOLO
        self.model = YOLO(weights)
        self.device = device
        self.conf = conf
        self.names: dict[int, str] = dict(self.model.names)
        self.weights = weights
        self._lock = threading.Lock()

    def classes_for(self, mode: str) -> list[int] | None:
        if mode == "person":
            return [PERSON_CLASS]
        if mode == "object":
            return [i for i in self.names if i != PERSON_CLASS]
        if mode == "auto":
            return None
        raise DetectorError(f"Unknown detection mode: {mode}")

    def lock(self):
        return self._lock

    def track(self, frame: np.ndarray, classes: list[int] | None, first: bool) -> list[Det]:
        res = self.model.track(frame, persist=not first, tracker="bytetrack.yaml", classes=classes,
                               conf=self.conf, device=self.device, verbose=False)[0]
        boxes = res.boxes
        if boxes is None or boxes.id is None:
            return []
        out = []
        for xyxy, tid, c, cf in zip(boxes.xyxy.cpu().numpy(), boxes.id.cpu().numpy(),
                                    boxes.cls.cpu().numpy(), boxes.conf.cpu().numpy()):
            out.append(Det(int(tid), int(c), self.names.get(int(c), str(int(c))), float(cf),
                           tuple(float(v) for v in xyxy)))
        return out
