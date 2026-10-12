"""Patch classifier (TDD 2.3, 4): pretrained MobileNetV3-Small or ResNet-18, binary head."""
import torch
from torch import nn
from torchvision import models

ARCHS = ("mobilenet_v3_small", "resnet18")
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


def build_model(arch: str = "mobilenet_v3_small", pretrained: bool = True) -> nn.Module:
    """ImageNet backbone with a single-logit head (logit of P_malignant)."""
    if arch == "mobilenet_v3_small":
        model = models.mobilenet_v3_small(
            weights=models.MobileNet_V3_Small_Weights.IMAGENET1K_V1 if pretrained else None
        )
        model.classifier[-1] = nn.Linear(model.classifier[-1].in_features, 1)
    elif arch == "resnet18":
        model = models.resnet18(weights=models.ResNet18_Weights.IMAGENET1K_V1 if pretrained else None)
        model.fc = nn.Linear(model.fc.in_features, 1)
    else:
        raise ValueError(f"unknown arch {arch!r}, expected one of {ARCHS}")
    return model


class ProbabilityModel(nn.Module):
    """What gets exported to ONNX: RGB float NCHW in [0, 1] -> P_malignant per patch, shape (N,).

    ImageNet normalisation and the sigmoid live inside the graph, so the runtime (step 5)
    only has to resize patches, divide by 255 and transpose to NCHW.
    """

    def __init__(self, model: nn.Module):
        super().__init__()
        self.model = model
        self.register_buffer("mean", torch.tensor(IMAGENET_MEAN).view(1, 3, 1, 1))
        self.register_buffer("std", torch.tensor(IMAGENET_STD).view(1, 3, 1, 1))

    def logits(self, x: torch.Tensor) -> torch.Tensor:
        """Raw logits, shape (N,). Training uses these with BCEWithLogitsLoss."""
        return self.model((x - self.mean) / self.std).squeeze(1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return torch.sigmoid(self.logits(x))


def tta_views(x: torch.Tensor, views: int):
    """Yield up to 8 orientations of the batch for test-time augmentation (identity first)."""
    transforms = [
        lambda t: t,
        lambda t: t.flip(-1),
        lambda t: t.flip(-2),
        lambda t: t.flip(-1).flip(-2),
        lambda t: t.transpose(-1, -2),
        lambda t: t.transpose(-1, -2).flip(-1),
        lambda t: t.transpose(-1, -2).flip(-2),
        lambda t: t.transpose(-1, -2).flip(-1).flip(-2),
    ]
    if not 1 <= views <= len(transforms):
        raise ValueError(f"views must be 1-8, got {views}")
    for transform in transforms[:views]:
        yield transform(x)


class TTAModel(nn.Module):
    """ProbabilityModel averaged over `views` orientations of each patch (test-time
    augmentation). Same input/output contract; `views` times the compute."""

    def __init__(self, net: ProbabilityModel, views: int):
        super().__init__()
        if not 1 <= views <= 8:
            raise ValueError(f"views must be 1-8, got {views}")
        self.net, self.views = net, views

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return torch.stack([self.net(v) for v in tta_views(x, self.views)]).mean(0)
