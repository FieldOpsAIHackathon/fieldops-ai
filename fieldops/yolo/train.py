"""Train a YOLO26 detector on the synthetic trap dataset. Runs in the local/fieldops-yolo container.

    bash fieldops/yolo/run.sh train            # from the repo root on the GB10

Seeded and deterministic. Augmentation (rotation, perspective, scale, colour) stands in for the
gap between rendered cards and a webcam pointed at a printed card.
"""
import argparse
from pathlib import Path

import torch
from ultralytics import YOLO

# The vLLM base image ships cuDNN without libcudnn_engines_precompiled ("unable to find an engine",
# SUBLIBRARY_UNAVAILABLE). The Dockerfile restores it; without it, fall back to PyTorch's own convs.
torch.backends.cudnn.enabled = Path("/usr/lib/aarch64-linux-gnu/libcudnn_engines_precompiled.so.9").exists()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data", default="/data/data.yaml")
    p.add_argument("--model", default="/runs/yolo26s.pt")
    p.add_argument("--epochs", type=int, default=40)
    p.add_argument("--hours", type=float, default=0.5, help="hard time budget; training stops when it runs out")
    p.add_argument("--imgsz", type=int, default=960)
    p.add_argument("--batch", type=int, default=16)
    p.add_argument("--project", default="/runs")
    p.add_argument("--name", default="traps")
    args = p.parse_args()

    YOLO(args.model).train(
        data=args.data, epochs=args.epochs, time=args.hours, imgsz=args.imgsz, batch=args.batch,
        project=args.project, name=args.name, exist_ok=True,
        seed=0, deterministic=True, workers=8, cache="ram", patience=10,
        degrees=15, perspective=0.0005, scale=0.5, translate=0.1,
        fliplr=0.5, flipud=0.5, mosaic=1.0, close_mosaic=5,
        hsv_h=0.02, hsv_s=0.5, hsv_v=0.4,
    )
    print(f"best weights: {Path(args.project) / args.name / 'weights' / 'best.pt'}")


if __name__ == "__main__":
    main()
