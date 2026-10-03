"""Count pests on trap images with the trained detector and emit contract records.

    bash fieldops/yolo/run.sh count data/traps/trap_05_codling050.jpg --trap-id block-c-04
    bash fieldops/yolo/run.sh eval                 # score against data/traps/manifest.json

Deterministic: fixed weights and confidence threshold, no test-time augmentation. YOLO26 is
NMS-free, so touching moths are not merged by an overlap threshold.
Gnats and debris are detected so they are not mistaken for pests, then dropped from the counts.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import torch
from ultralytics import YOLO

# see train.py: use cuDNN only when the image has its precompiled engines
torch.backends.cudnn.enabled = Path("/usr/lib/aarch64-linux-gnu/libcudnn_engines_precompiled.so.9").exists()

PESTS = ("codling_moth", "oriental_fruit_moth", "spotted_lanternfly")
CONF, IOU, IMGSZ = 0.35, 0.5, 960


def load_model(weights: str) -> YOLO:
    return YOLO(weights)


def count_result(model: YOLO, image) -> tuple:
    """Pest counts plus an RGB PIL image with only the pest boxes drawn."""
    from PIL import Image

    result = model.predict(image, imgsz=IMGSZ, conf=CONF, iou=IOU, verbose=False)[0]
    names = [model.names[int(c)] for c in result.boxes.cls.tolist()]
    pest_ids = [i for i, n in enumerate(names) if n in PESTS]
    annotated = Image.fromarray(result[pest_ids].plot(labels=False, conf=False, line_width=3)[..., ::-1])
    return {p: names.count(p) for p in PESTS}, annotated


def count(model: YOLO, image) -> dict:
    return count_result(model, image)[0]


def records(counts: dict, trap_id: str, timestamp: str) -> list:
    return [{"trap_id": trap_id, "timestamp": timestamp, "species": s, "count": n} for s, n in counts.items()]


def evaluate(model: YOLO, manifest: Path) -> None:
    rows = json.loads(manifest.read_text())
    errors = {p: [] for p in PESTS}
    for row in rows:
        truth = {r["species"]: r["count"] for r in row["counts"]}
        got = count(model, manifest.parent / row["file"])
        for p in PESTS:
            errors[p].append(got[p] - truth.get(p, 0))
        print(f"{row['file']:<28} " + "  ".join(f"{p}: {got[p]}/{truth.get(p, 0)}" for p in PESTS))
    for p, e in errors.items():
        print(f"{p:<20} mean abs error {sum(map(abs, e)) / len(e):.2f}   exact {sum(x == 0 for x in e)}/{len(e)}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("images", nargs="*", type=Path)
    p.add_argument("--weights", default="/runs/fieldops-yolo26s-v1.pt")
    p.add_argument("--trap-id", default="block-c-04")
    p.add_argument("--eval", type=Path, help="manifest.json with ground-truth counts")
    args = p.parse_args()

    model = YOLO(args.weights)
    if args.eval:
        return evaluate(model, args.eval)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out = []
    for image in args.images:
        out += records(count(model, image), args.trap_id, stamp)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
