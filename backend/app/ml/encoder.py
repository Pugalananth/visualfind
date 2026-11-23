"""
VisualFind checkpoint-compatible encoder.

Compatible with:
    models/encoder_se_epoch30.pth
    models/encoder_tri_epoch5.pth

Architecture:
    ResNet-50 style bottleneck backbone
    Stage-level Squeeze-Excitation
    GeM pooling
    2048 -> 512 -> 128 projection
    L2-normalized 128-D embedding
"""

from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F


# ============================================================
# GeM Pooling
# ============================================================

class GeM(nn.Module):
    def __init__(self, p: float = 3.0, eps: float = 1e-6):
        super().__init__()

        self.gem_p = nn.Parameter(torch.ones(1) * p)
        self.eps = eps

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x.clamp(min=self.eps)
        x = x.pow(self.gem_p)
        x = F.adaptive_avg_pool2d(x, (1, 1))
        return x.pow(1.0 / self.gem_p)


# ============================================================
# Squeeze-and-Excitation
# ============================================================

class SEModule(nn.Module):
    def __init__(self, channels: int, reduction: int):
        super().__init__()

        reduced = max(channels // reduction, 1)
        self.fc = nn.Sequential(
            nn.Linear(channels, reduced, bias=True),
            nn.ReLU(inplace=True),
            nn.Linear(reduced, channels, bias=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        y = F.adaptive_avg_pool2d(x, 1)
        y = y.flatten(1)
        y = self.fc(y)
        y = y.unsqueeze(-1).unsqueeze(-1)
        y = torch.sigmoid(y)
        return x * y


# ============================================================
# ResNet Bottleneck
# ============================================================

class Bottleneck(nn.Module):
    expansion = 4

    def __init__(
        self,
        inplanes: int,
        planes: int,
        stride: int = 1,
        downsample=None,
    ):
        super().__init__()

        outplanes = planes * self.expansion

        self.conv1 = nn.Conv2d(
            inplanes,
            planes,
            kernel_size=1,
            bias=False,
        )

        self.bn1 = nn.BatchNorm2d(planes)

        self.conv2 = nn.Conv2d(
            planes,
            planes,
            kernel_size=3,
            stride=stride,
            padding=1,
            bias=False,
        )

        self.bn2 = nn.BatchNorm2d(planes)

        self.conv3 = nn.Conv2d(
            planes,
            outplanes,
            kernel_size=1,
            bias=False,
        )

        self.bn3 = nn.BatchNorm2d(outplanes)

        self.relu = nn.ReLU(inplace=True)

        self.downsample = downsample

        self.stride = stride

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        identity = x

        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)

        out = self.conv2(out)
        out = self.bn2(out)
        out = self.relu(out)

        out = self.conv3(out)
        out = self.bn3(out)

        if self.downsample is not None:
            identity = self.downsample(x)

        out += identity
        out = self.relu(out)

        return out


# ============================================================
# VisualFind Encoder
# ============================================================

class VisualFindEncoder(nn.Module):

    def __init__(
        self,
        emb_dim: int = 128,
        reduction: int = 16,
    ):
        super().__init__()

        self.inplanes = 64

        # ----------------------------------------------------
        # Stem (checkpoint-compatible naming)
        # ----------------------------------------------------

        self.stem = nn.Sequential(
            nn.Conv2d(
                3,
                64,
                kernel_size=7,
                stride=2,
                padding=3,
                bias=False,
            ),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(
                kernel_size=3,
                stride=2,
                padding=1,
            ),
        )

        # ----------------------------------------------------
        # ResNet-50 stages
        # ----------------------------------------------------

        self.layer1 = self._make_layer(
            64,
            blocks=3,
            stride=1,
        )

        self.layer2 = self._make_layer(
            128,
            blocks=4,
            stride=2,
        )

        self.layer3 = self._make_layer(
            256,
            blocks=6,
            stride=2,
        )

        self.layer4 = self._make_layer(
            512,
            blocks=3,
            stride=2,
        )

        # ----------------------------------------------------
        # Stage-level SE
        # ----------------------------------------------------

        self.se1 = SEModule(
            256,
            reduction,
        )

        self.se2 = SEModule(
            512,
            reduction,
        )

        self.se3 = SEModule(
            1024,
            reduction,
        )

        self.se4 = SEModule(
            2048,
            reduction,
        )

        # ----------------------------------------------------
        # GeM
        # ----------------------------------------------------

        self.gem_p = nn.Parameter(torch.ones(1) * 3.0)
        self.eps = 1e-6

        # ----------------------------------------------------
        # Projection head
        #
        # 2048 -> 512 -> 128
        # ----------------------------------------------------

        self.projector = nn.Sequential(
            nn.Linear(2048, 512),
            nn.ReLU(inplace=True),
            nn.Linear(512, emb_dim),
        )

        self._initialize_weights()

    # ========================================================
    # Layer construction
    # ========================================================

    def _make_layer(
        self,
        planes: int,
        blocks: int,
        stride: int,
    ):

        downsample = None

        outplanes = planes * Bottleneck.expansion

        if stride != 1 or self.inplanes != outplanes:

            downsample = nn.Sequential(
                nn.Conv2d(
                    self.inplanes,
                    outplanes,
                    kernel_size=1,
                    stride=stride,
                    bias=False,
                ),
                nn.BatchNorm2d(outplanes),
            )

        layers = [
            Bottleneck(
                self.inplanes,
                planes,
                stride,
                downsample,
            )
        ]

        self.inplanes = outplanes

        for _ in range(1, blocks):

            layers.append(
                Bottleneck(
                    self.inplanes,
                    planes,
                )
            )

        return nn.Sequential(*layers)

    # ========================================================
    # Weight initialization
    # ========================================================

    def _initialize_weights(self):

        for m in self.modules():

            if isinstance(m, nn.Conv2d):

                nn.init.kaiming_normal_(
                    m.weight,
                    mode="fan_out",
                    nonlinearity="relu",
                )

            elif isinstance(m, nn.BatchNorm2d):

                nn.init.constant_(
                    m.weight,
                    1,
                )

                nn.init.constant_(
                    m.bias,
                    0,
                )

            elif isinstance(m, nn.Linear):

                nn.init.normal_(
                    m.weight,
                    0,
                    0.01,
                )

                if m.bias is not None:
                    nn.init.constant_(
                        m.bias,
                        0,
                    )

    # ========================================================
    # Forward
    # ========================================================

    def forward(
        self,
        x: torch.Tensor,
    ) -> torch.Tensor:

        # Stem
        x = self.stem(x)

        # Stage 1
        x = self.layer1(x)
        x = self.se1(x)

        # Stage 2
        x = self.layer2(x)
        x = self.se2(x)

        # Stage 3
        x = self.layer3(x)
        x = self.se3(x)

        # Stage 4
        x = self.layer4(x)
        x = self.se4(x)

        # GeM
        x = x.clamp(min=self.eps)
        x = x.pow(self.gem_p)
        x = F.adaptive_avg_pool2d(x, (1, 1))
        x = x.pow(1.0 / self.gem_p)
        x = torch.flatten(x, 1)

        # Projection
        x = self.projector(x)

        # L2-normalized embedding
        x = F.normalize(
            x,
            p=2,
            dim=1,
        )

        return x


# ============================================================
# Checkpoint utilities
# ============================================================

def _extract_state_dict(checkpoint):

    if isinstance(checkpoint, dict):

        for key in (
            "state_dict",
            "model_state_dict",
            "model",
            "encoder",
            "encoder_state_dict",
        ):

            value = checkpoint.get(key)

            if isinstance(value, dict):

                checkpoint = value
                break

    if not isinstance(checkpoint, dict):
        raise RuntimeError(
            "Checkpoint does not contain a valid state dictionary."
        )

    # Remove common wrappers
    cleaned = {}

    for key, value in checkpoint.items():

        new_key = key

        for prefix in (
            "module.",
            "model.",
            "encoder.",
        ):

            if new_key.startswith(prefix):
                new_key = new_key[len(prefix):]

        cleaned[new_key] = value

    return cleaned


def _infer_embedding_dimension(state_dict):

    weight = state_dict.get(
        "projector.2.weight"
    )

    if weight is None:

        weight = state_dict.get(
            "projector.2.bias"
        )

        if weight is None:
            return 128

        return weight.shape[0]

    return weight.shape[0]


def _infer_reduction(state_dict):

    weight = state_dict.get("se1.fc.0.weight")

    if weight is None:
        return 16

    channels = weight.shape[1]
    reduced = weight.shape[0]

    if reduced <= 0 or channels <= 0:
        return 16

    return max(channels // reduced, 1)


# ============================================================
# Public loader
# ============================================================

def load_encoder(
    path: Path | str,
    device: str,
):

    path = Path(path)

    if not path.exists():

        raise FileNotFoundError(
            f"Encoder checkpoint not found: {path}"
        )

    checkpoint = torch.load(
        path,
        map_location="cpu",
        weights_only=True,
    )

    state_dict = _extract_state_dict(
        checkpoint
    )

    emb_dim = _infer_embedding_dimension(
        state_dict
    )

    reduction = _infer_reduction(
        state_dict
    )

    model = VisualFindEncoder(
        emb_dim=emb_dim,
        reduction=reduction,
    )

    # --------------------------------------------------------
    # Strict compatibility check
    # --------------------------------------------------------

    try:

        model.load_state_dict(
            state_dict,
            strict=True,
        )

    except RuntimeError as exc:

        raise RuntimeError(
            "Checkpoint is not compatible with the "
            "VisualFindEncoder architecture. "
            f"Checkpoint: {path.name}\n\n"
            f"{exc}"
        ) from exc

    model = model.to(device)

    model.eval()

    return model, {
        "bottleneck": True,
        "layers": (3, 4, 6, 3),
        "emb_dim": emb_dim,
        "reduction": reduction,
        "checkpoint": str(path),
        "device": device,
    }