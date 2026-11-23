import sys

import torch

from .encoder import _extract_state_dict, infer_config

if __name__ == "__main__":
    ckpt = torch.load(sys.argv[1], map_location="cpu", weights_only=True)
    if isinstance(ckpt, dict):
        print("top-level keys:", [k for k in ckpt.keys()][:20])
    sd = _extract_state_dict(ckpt)
    print(f"{len(sd)} tensors; inferred config: {infer_config(sd)}")
    for k, v in list(sd.items())[:15] + [("...", None)] + list(sd.items())[-10:]:
        print(k, tuple(v.shape) if v is not None else "")
