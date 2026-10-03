"""Generate a YOLO detection dataset from synth_traps, with exact ground-truth boxes.

    python -m fieldops.yolo.make_dataset --train 2000 --val 300 --out ~/hackathon-stack/yolo-data

Deterministic: image i of a split always comes from the same seed, so a re-run reproduces the
dataset byte for byte. Gnats and debris are labelled as their own classes so the detector learns
to tell them apart from pests; only the pest classes are counted downstream.
"""
import argparse
import json
import random
from multiprocessing import Pool
from pathlib import Path

from .. import synth_traps

CLASSES = ["codling_moth", "oriental_fruit_moth", "spotted_lanternfly", "gnat", "debris"]
SPLIT_SEED = {"train": 1_000_000, "val": 2_000_000}


def sample_counts(rng: random.Random) -> tuple:
    """Pest counts spanning empty cards to crowded peak-flight cards."""
    crowd = rng.choice([0.1, 0.4, 1.0])
    counts = {
        "codling_moth": rng.randint(0, int(60 * crowd)),
        "oriental_fruit_moth": rng.randint(0, int(30 * crowd)),
        "spotted_lanternfly": rng.choice([0, 0, 1, 2, 3, 5]),
    }
    return counts, rng.randint(0, 25), rng.randint(2, 30)


def yolo_line(box: dict) -> str:
    x0, y0, x1, y1 = box["bbox"]
    x0, y0 = max(x0, 0), max(y0, 0)
    x1, y1 = min(x1, synth_traps.W), min(y1, synth_traps.H)
    cx, cy = (x0 + x1) / 2 / synth_traps.W, (y0 + y1) / 2 / synth_traps.H
    w, h = (x1 - x0) / synth_traps.W, (y1 - y0) / synth_traps.H
    return f"{CLASSES.index(box['label'])} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}"


def make_one(job: tuple) -> dict:
    out, split, i = job
    rng = random.Random(SPLIT_SEED[split] + i)
    counts, gnats, debris = sample_counts(rng)
    img, boxes = synth_traps.render(counts, gnats, debris, rng)
    name = f"{split}_{i:05d}"
    img.save(out / "images" / split / f"{name}.jpg", quality=rng.randint(70, 95))
    (out / "labels" / split / f"{name}.txt").write_text("\n".join(yolo_line(b) for b in boxes) + "\n")
    return {"file": f"{name}.jpg", "counts": {c: sum(b["label"] == c for b in boxes) for c in CLASSES}}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--train", type=int, default=2000)
    p.add_argument("--val", type=int, default=300)
    p.add_argument("--out", type=Path, default=Path.home() / "hackathon-stack" / "yolo-data")
    p.add_argument("--workers", type=int, default=16)
    args = p.parse_args()

    out = args.out.expanduser().resolve()
    for split in ("train", "val"):
        (out / "images" / split).mkdir(parents=True, exist_ok=True)
        (out / "labels" / split).mkdir(parents=True, exist_ok=True)

    jobs = [(out, "train", i) for i in range(args.train)] + [(out, "val", i) for i in range(args.val)]
    with Pool(args.workers) as pool:
        truth = pool.map(make_one, jobs, chunksize=8)

    (out / "ground_truth.json").write_text(json.dumps(truth) + "\n")
    (out / "data.yaml").write_text(
        "path: /data\ntrain: images/train\nval: images/val\nnames:\n"
        + "".join(f"  {i}: {c}\n" for i, c in enumerate(CLASSES))
    )
    totals = {c: sum(t["counts"][c] for t in truth) for c in CLASSES}
    print(f"wrote {len(truth)} images to {out}: {totals}")


if __name__ == "__main__":
    main()
