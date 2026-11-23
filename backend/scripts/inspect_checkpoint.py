"""Inspect a checkpoint and report whether it loads into the VisualFind encoder.

    python scripts/inspect_checkpoint.py models/encoder_tri_epoch5.pth
"""
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.ml.encoder import VisualFindEncoder, _extract_state_dict, _infer_architecture  # noqa: E402


def main(path: str) -> int:
    raw = torch.load(path, map_location="cpu", weights_only=True)
    if isinstance(raw, dict):
        print("top-level keys:", [k for k in raw.keys()][:12])
    sd = _extract_state_dict(raw)
    print(f"{len(sd)} tensors")
    for k, v in list(sd.items())[:6] + [("...", None)] + list(sd.items())[-6:]:
        print(" ", k, tuple(v.shape) if v is not None else "")
    bottleneck, layers = _infer_architecture(sd)
    print("inferred:", "bottleneck" if bottleneck else "basic", layers, "SE blocks:", any(".se." in k for k in sd))
    dim = next((v.shape[0] for k, v in sd.items() if k.endswith("embedding.weight")), 128)
    model = VisualFindEncoder(dim, bottleneck, layers)
    missing, unexpected = model.load_state_dict(sd, strict=False)
    print(f"missing keys: {len(missing)}  unexpected keys: {len(unexpected)}")
    print("  missing   (first 8):", missing[:8])
    print("  unexpected(first 8):", unexpected[:8])
    return 0 if not missing and not unexpected else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
