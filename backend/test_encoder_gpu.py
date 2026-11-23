from pathlib import Path

import torch

from app.config import get_settings
from app.ml.encoder import load_encoder


def main():

    settings = get_settings()

    device = (
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    print("=" * 60)
    print("VISUALFIND ENCODER TEST")
    print("=" * 60)

    print("PyTorch:", torch.__version__)
    print("CUDA available:", torch.cuda.is_available())
    print("Device:", device)

    if torch.cuda.is_available():

        print(
            "GPU:",
            torch.cuda.get_device_name(0)
        )

        print(
            "VRAM:",
            round(
                torch.cuda.get_device_properties(0).total_memory
                / 1024**3,
                2
            ),
            "GB"
        )

    checkpoint = Path(
        settings.encoder_checkpoint
    )

    print("Checkpoint:", checkpoint)
    print("Exists:", checkpoint.exists())

    print()
    print("Loading checkpoint...")

    model, cfg = load_encoder(
        checkpoint,
        device,
    )

    print()
    print("MODEL LOADED SUCCESSFULLY")
    print("Config:", cfg)

    # --------------------------------------------------------
    # Dummy image
    # --------------------------------------------------------

    x = torch.randn(
        1,
        3,
        settings.encoder_input_h,
        settings.encoder_input_w,
        device=device,
    )

    print()
    print("Input:", tuple(x.shape))
    print("Input device:", x.device)

    with torch.inference_mode():

        embedding = model(x)

    print()
    print("Embedding shape:", tuple(embedding.shape))
    print("Embedding device:", embedding.device)
    print("Embedding dtype:", embedding.dtype)

    norm = torch.linalg.vector_norm(
        embedding,
        dim=1,
    )

    print(
        "Embedding norm:",
        norm.detach().cpu().tolist()
    )

    if embedding.shape != (1, 128):

        raise RuntimeError(
            f"Unexpected embedding shape: {embedding.shape}"
        )

    if not torch.allclose(
        norm,
        torch.ones_like(norm),
        atol=1e-4,
    ):

        raise RuntimeError(
            "Embedding is not L2 normalized."
        )

    if device == "cuda":

        torch.cuda.synchronize()

        print(
            "GPU allocated:",
            round(
                torch.cuda.memory_allocated()
                / 1024**2,
                2
            ),
            "MB"
        )

        print(
            "GPU reserved:",
            round(
                torch.cuda.memory_reserved()
                / 1024**2,
                2
            ),
            "MB"
        )

    print()
    print("=" * 60)
    print("ENCODER GPU TEST: SUCCESS")
    print("=" * 60)


if __name__ == "__main__":
    main()