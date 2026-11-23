"""Reference embedding -> frame sampling -> YOLO detect/track -> crop -> embed -> cosine
similarity -> per-track aggregation.

Threshold rule (single, authoritative): a track is returned when its BEST sampled similarity
is >= the threshold. Mean/median never discard a track; they are reported for ranking and
inspection. `match_count` is the number of sampled detections in the track at/above threshold."""
import statistics
from collections import Counter
from dataclasses import dataclass, field

import cv2
import numpy as np
import torch

from .detector import Detector

MIN_CROP = 16
AUTO_TARGET_FPS = 4.0
MAX_SAVED_PER_TRACK = 40


class VideoError(Exception):
    pass


@dataclass
class Sample:
    frame_index: int
    timestamp: float
    similarity: float
    bbox: tuple
    conf: float
    cls_name: str


@dataclass
class TrackResult:
    track_id: int
    samples: list[Sample]          # all sampled detections of the track
    matched: list[Sample]          # samples >= threshold
    best: Sample = None
    best_similarity: float = 0.0
    mean_similarity: float = 0.0
    median_similarity: float = 0.0
    consistency: float = 0.0
    track_score: float = 0.0
    first_seen: float = 0.0
    last_seen: float = 0.0
    cls_name: str = ""


@dataclass
class VideoMeta:
    fps: float
    frame_count: int
    width: int
    height: int
    duration: float


@dataclass
class SearchOutput:
    meta: VideoMeta
    sampling_fps_used: float
    frames_processed: int
    tracks: list[TrackResult] = field(default_factory=list)


def probe_video(path) -> VideoMeta:
    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            raise VideoError("The file could not be opened as a video.")
        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        ok, _ = cap.read()
        if not ok or fps <= 0 or w <= 0 or h <= 0:
            raise VideoError("The file is not a readable video.")
        if n <= 0:
            raise VideoError("The video contains no frames.")
        return VideoMeta(fps=fps, frame_count=n, width=w, height=h, duration=n / fps)
    finally:
        cap.release()


def choose_sampling(meta: VideoMeta, requested: float | None, max_frames: int) -> float:
    """AUTO (requested=None): about 4 fps, capped so a search never exceeds max_frames samples."""
    fps = requested if requested else AUTO_TARGET_FPS
    fps = min(fps, meta.fps)
    if not requested and meta.duration > 0:
        fps = max(min(fps, max_frames / meta.duration), 0.2)
    return float(fps)


def aggregate(track_id: int, samples: list[Sample], threshold: float) -> TrackResult | None:
    sims = [s.similarity for s in samples]
    best = max(samples, key=lambda s: s.similarity)
    if best.similarity < threshold:
        return None
    matched = [s for s in samples if s.similarity >= threshold]
    mean, median = float(statistics.fmean(sims)), float(statistics.median(sims))
    return TrackResult(
        track_id=track_id, samples=samples, matched=matched, best=best,
        best_similarity=best.similarity, mean_similarity=mean, median_similarity=median,
        consistency=len(matched) / len(samples),
        track_score=0.6 * best.similarity + 0.4 * median,  # ranking only, never a filter
        first_seen=min(s.timestamp for s in matched), last_seen=max(s.timestamp for s in matched),
        cls_name=Counter(s.cls_name for s in samples).most_common(1)[0][0],
    )


def run_search(video_path, ref_embedding: torch.Tensor, mode: str, threshold: float,
               sampling_fps: float | None, encoder, detector: Detector, max_frames: int,
               progress=None) -> SearchOutput:
    meta = probe_video(video_path)
    fps_used = choose_sampling(meta, sampling_fps, max_frames)
    step = max(int(round(meta.fps / fps_used)), 1)
    fps_used = meta.fps / step
    total = (meta.frame_count + step - 1) // step
    classes = detector.classes_for(mode)

    by_track: dict[int, list[Sample]] = {}
    cap = cv2.VideoCapture(str(video_path))
    processed = 0
    idx = 0
    first = True
    try:
        with detector.lock():
            while True:
                if not cap.grab():
                    break
                if idx % step == 0:
                    ok, frame = cap.retrieve()
                    if not ok:
                        idx += 1
                        continue
                    dets = detector.track(frame, classes, first)
                    first = False
                    crops, kept = [], []
                    for d in dets:
                        x1, y1, x2, y2 = (int(round(v)) for v in d.bbox)
                        x1, y1 = max(x1, 0), max(y1, 0)
                        x2, y2 = min(x2, meta.width), min(y2, meta.height)
                        if x2 - x1 < MIN_CROP or y2 - y1 < MIN_CROP:
                            continue
                        crops.append(frame[y1:y2, x1:x2])
                        kept.append(d)
                    if crops:
                        embs = encoder.embed_bgr(crops)
                        sims = (embs @ ref_embedding.to(embs.device)).cpu().tolist()
                        ts = idx / meta.fps
                        for d, sim in zip(kept, sims):
                            by_track.setdefault(d.track_id, []).append(
                                Sample(idx, ts, float(sim), d.bbox, d.conf, d.cls_name))
                    processed += 1
                    if progress and (processed % 5 == 0 or processed == total):
                        progress(processed, total)
                idx += 1
    finally:
        cap.release()

    tracks = [t for tid, s in by_track.items() if (t := aggregate(tid, s, threshold))]
    tracks.sort(key=lambda t: t.track_score, reverse=True)
    return SearchOutput(meta=meta, sampling_fps_used=fps_used, frames_processed=processed, tracks=tracks)


def pick_saved_samples(t: TrackResult) -> list[Sample]:
    """Matched samples to keep images for: evenly spread, capped, best always included."""
    m = sorted(t.matched, key=lambda s: s.frame_index)
    if len(m) > MAX_SAVED_PER_TRACK:
        pos = np.linspace(0, len(m) - 1, MAX_SAVED_PER_TRACK).round().astype(int)
        m = [m[i] for i in sorted(set(pos.tolist()))]
    if t.best not in m:
        m = sorted(m + [t.best], key=lambda s: s.frame_index)
    return m


def extract_frames(video_path, indices: list[int]) -> dict[int, bytes]:
    """Re-read specific frame indices and return JPEG bytes."""
    wanted = sorted(set(indices))
    out: dict[int, bytes] = {}
    if not wanted:
        return out
    cap = cv2.VideoCapture(str(video_path))
    try:
        i, k = 0, 0
        last = wanted[-1]
        while k < len(wanted) and i <= last:
            if not cap.grab():
                break
            if i == wanted[k]:
                ok, frame = cap.retrieve()
                if ok:
                    ok2, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 88])
                    if ok2:
                        out[i] = buf.tobytes()
                k += 1
            i += 1
    finally:
        cap.release()
    return out
