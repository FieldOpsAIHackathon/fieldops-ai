"""Stress test: synthetic cards made to look like phone photos, scored against exact counts.

    bash fieldops/yolo/run.sh phone-test --n 200              # writes /runs/phone_test/, prints errors
    bash fieldops/yolo/run.sh phone-test --n 200 --severity 2 # harsher camera

Each card comes from synth_traps.render (so its counts are exact), then gets effects the training
set never saw: a desk background, perspective tilt, rotation, focus or motion blur, glare and
uneven light, colour cast, sensor noise, heavy JPEG and a phone resolution. Seeds differ from the
training and validation seeds, so nothing here was trained on. This is the overfitting check.
"""
import argparse
import io
import json
import random
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter

from .. import synth_traps
from .make_dataset import sample_counts

SEED = 3_000_000  # train uses 1M+, val 2M+


def desk(size, rng):
    w, h = size
    base = tuple(rng.randint(30, 200) for _ in range(3))
    img = Image.new("RGB", (w, h), base)
    noise = Image.effect_noise((w // 16, h // 16), rng.uniform(10, 40)).resize((w, h), Image.BICUBIC)
    return Image.blend(img, Image.merge("RGB", [noise] * 3), 0.25)


def perspective_coeffs(src, dst):
    """Coefficients for Image.transform(PERSPECTIVE) mapping dst quad -> src quad."""
    import numpy as np

    a = []
    for (x, y), (u, v) in zip(dst, src):
        a.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        a.append([0, 0, 0, x, y, 1, -v * x, -v * y])
    return np.linalg.solve(np.array(a, float), np.array(src, float).reshape(8)).tolist()


def _map_boxes(boxes, coeffs, angle, size):
    """Move boxes through the card perspective warp, then the rotation; return clipped boxes."""
    import math

    a, b, c, d, e, f, g, h = coeffs
    w, hh = size
    cx, cy, t = w / 2, hh / 2, math.radians(angle)

    def move(x, y):
        den = g * x + h * y + 1
        u, v = (a * x + b * y + c) / den, (d * x + e * y + f) / den
        dx, dy = u - cx, v - cy
        return cx + dx * math.cos(t) + dy * math.sin(t), cy - dx * math.sin(t) + dy * math.cos(t)

    out = []
    for box in boxes:
        x0, y0, x1, y1 = box["bbox"]
        pts = [move(x, y) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
        xs, ys = [q[0] for q in pts], [q[1] for q in pts]
        nb = [max(0, min(xs)), max(0, min(ys)), min(w, max(xs)), min(hh, max(ys))]
        if nb[2] - nb[0] > 2 and nb[3] - nb[1] > 2:
            out.append({"label": box["label"], "bbox": nb})
    return out


def phone_photo(card: Image.Image, rng: random.Random, severity: float, boxes=None):
    """Return the phone-style photo, or (photo, moved boxes) when boxes are given."""
    s = severity
    out_w = rng.choice([1600, 2016, 2400])
    out_h = int(out_w * 3 / 4)
    canvas = desk((out_w, out_h), rng)

    # Place the card with a random scale, then tilt it in perspective.
    scale = rng.uniform(0.70, 0.92)
    cw, ch = int(out_w * scale), int(out_w * scale * card.height / card.width)
    ch = min(ch, int(out_h * 0.95))
    cw = int(ch * card.width / card.height)
    x0, y0 = (out_w - cw) // 2 + rng.randint(-20, 20), (out_h - ch) // 2 + rng.randint(-20, 20)
    j = lambda: rng.uniform(-0.06, 0.06) * s * cw
    dst = [(x0 + j(), y0 + j()), (x0 + cw + j(), y0 + j()), (x0 + cw + j(), y0 + ch + j()), (x0 + j(), y0 + ch + j())]
    src = [(0, 0), (card.width, 0), (card.width, card.height), (0, card.height)]
    warped = card.transform((out_w, out_h), Image.PERSPECTIVE, perspective_coeffs(src, dst), Image.BICUBIC)
    mask = Image.new("L", (out_w, out_h), 0)
    ImageDraw.Draw(mask).polygon(dst, fill=255)
    canvas.paste(warped, (0, 0), mask)
    angle = rng.uniform(-8, 8) * s
    canvas = canvas.rotate(angle, resample=Image.BICUBIC, fillcolor=canvas.getpixel((2, 2)))
    moved = _map_boxes(boxes, perspective_coeffs(dst, src), angle, (out_w, out_h)) if boxes is not None else None

    # Lighting: a broad gradient plus a glare spot.
    shade = Image.linear_gradient("L").resize((out_w, out_h), Image.BICUBIC)
    shade = shade.transpose(rng.choice([Image.Transpose.ROTATE_180, Image.Transpose.FLIP_LEFT_RIGHT,
                                        Image.Transpose.FLIP_TOP_BOTTOM, Image.Transpose.TRANSPOSE]))
    shade = shade.resize((out_w, out_h), Image.BICUBIC)
    dim = rng.uniform(0.1, 0.35) * s
    shade = shade.point(lambda v: int(255 - v * dim))
    canvas = ImageChops.multiply(canvas, Image.merge("RGB", [shade] * 3))
    if rng.random() < 0.6:
        glare = Image.new("L", (out_w, out_h), 0)
        gx, gy, gr = rng.uniform(0.2, 0.8) * out_w, rng.uniform(0.2, 0.8) * out_h, rng.uniform(0.08, 0.2) * out_w
        ImageDraw.Draw(glare).ellipse([gx - gr, gy - gr, gx + gr, gy + gr], fill=int(rng.uniform(60, 140) * s))
        glare = glare.filter(ImageFilter.GaussianBlur(gr / 2))
        canvas = ImageChops.add(canvas, Image.merge("RGB", [glare] * 3))

    # Colour cast, contrast, focus or motion blur, noise.
    r, g, b = canvas.split()
    cast = [rng.uniform(1 - 0.12 * s, 1 + 0.12 * s) for _ in range(3)]
    canvas = Image.merge("RGB", [ch_.point(lambda v, k=k: min(255, int(v * k))) for ch_, k in zip((r, g, b), cast)])
    canvas = ImageEnhance.Contrast(canvas).enhance(rng.uniform(0.8, 1.15))
    if rng.random() < 0.5:
        canvas = canvas.filter(ImageFilter.GaussianBlur(rng.uniform(0.5, 1.8) * s))
    else:  # motion blur: a 5-pixel streak in one of four directions (PIL kernels max out at 5x5)
        line = rng.choice([[10, 11, 12, 13, 14], [2, 7, 12, 17, 22], [0, 6, 12, 18, 24], [4, 8, 12, 16, 20]])
        kernel = [1 if i in line else 0 for i in range(25)]
        for _ in range(max(1, round(s))):
            canvas = canvas.filter(ImageFilter.Kernel((5, 5), kernel, scale=5))
    noise = Image.effect_noise((out_w, out_h), rng.uniform(4, 14) * s)
    canvas = Image.blend(canvas, ImageChops.overlay(canvas, Image.merge("RGB", [noise] * 3)), 0.25)

    buf = io.BytesIO()
    canvas.save(buf, "JPEG", quality=rng.randint(55, 85))
    photo = Image.open(io.BytesIO(buf.getvalue())).convert("RGB")
    return photo if boxes is None else (photo, moved)


def main() -> None:
    from .count import PESTS, count, load_model  # needs ultralytics (GPU container)

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--n", type=int, default=200)
    p.add_argument("--severity", type=float, default=1.0)
    p.add_argument("--weights", default="/runs/fieldops-yolo26s-v2.pt")
    p.add_argument("--out", type=Path, default=Path("/runs/phone_test"))
    args = p.parse_args()

    model = load_model(args.weights)
    args.out.mkdir(parents=True, exist_ok=True)
    errors = {sp: [] for sp in PESTS}
    rows = []
    for i in range(args.n):
        rng = random.Random(SEED + i)
        counts, gnats, debris = sample_counts(rng)
        card, boxes = synth_traps.render(counts, gnats, debris, rng)
        truth = {sp: sum(b["label"] == sp for b in boxes) for sp in PESTS}
        photo = phone_photo(card, rng, args.severity)
        if i < 12:
            photo.save(args.out / f"phone_{i:03d}.jpg", quality=85)
        got = count(model, photo)
        for sp in PESTS:
            errors[sp].append(got[sp] - truth[sp])
        rows.append({"i": i, "truth": truth, "got": got})

    (args.out / f"results_sev{args.severity}.json").write_text(json.dumps(rows))
    print(f"{args.n} phone-style photos, severity {args.severity}")
    for sp, e in errors.items():
        total = sum(r["truth"][sp] for r in rows)
        mae = sum(map(abs, e)) / len(e)
        within1 = sum(abs(x) <= 1 for x in e)
        print(f"  {sp:<20} truth total {total:5d}  MAE {mae:5.2f}  bias {sum(e) / len(e):+5.2f}  "
              f"exact {sum(x == 0 for x in e):3d}/{len(e)}  within 1: {within1}/{len(e)}")
    worst = sorted(rows, key=lambda r: -sum(abs(r["got"][s] - r["truth"][s]) for s in PESTS))[:3]
    for r in worst:
        print(f"  worst #{r['i']}: truth {r['truth']}  got {r['got']}")


if __name__ == "__main__":
    main()
