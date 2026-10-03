"""Generate synthetic sticky-trap photos with known insect counts.

    python -m fieldops.synth_traps                       # default ladder of counts
    python -m fieldops.synth_traps --counts 3 9 40 --seed 7

Writes JPEGs plus manifest.json (ground truth) to data/traps/. The manifest's
"counts" lists follow the integration contract; boxes stay in this file's output
because they belong to the vision layer.
"""
from __future__ import annotations

import argparse
import json
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter

SS = 4  # supersampling factor so insect edges are smooth after downscaling
W, H = 1280, 960
CARD = (48, 48, W - 48, H - 48)
GRID_PX = 100

# Species keys must match species.yaml; sizes are in output pixels.
SPECIES = {
    "codling_moth": dict(
        length=(44, 52), width=(17, 20), profile=(0.7, 0.7),
        base=(128, 112, 96), stripe=(170, 154, 136), stripes=14,
        tip=(150, 92, 48), spots=0, hindwing=None,
    ),
    "oriental_fruit_moth": dict(
        length=(32, 38), width=(12, 15), profile=(0.7, 0.7),
        base=(104, 100, 96), stripe=(140, 134, 126), stripes=8,
        tip=None, spots=0, hindwing=None,
    ),
    "spotted_lanternfly": dict(
        length=(64, 74), width=(24, 28), profile=(0.85, 0.3),
        base=(158, 146, 128), stripe=(140, 128, 112), stripes=6,
        tip=(96, 84, 74), spots=12, hindwing=(176, 48, 48),
    ),
}


def _finish_tile(tile: Image.Image, rng: random.Random) -> Image.Image:
    tile = tile.rotate(rng.uniform(0, 360), resample=Image.BICUBIC, expand=True)
    tile = tile.resize(
        (max(1, tile.width // SS), max(1, tile.height // SS)), Image.LANCZOS
    )
    return tile.crop(tile.getbbox())


def moth_tile(spec: dict, rng: random.Random) -> Image.Image:
    length = rng.uniform(*spec["length"]) * SS
    width = rng.uniform(*spec["width"]) * SS
    cw, ch = int(length * 1.5), int(width * 2.8)
    x0, cy = (cw - length) / 2, ch / 2
    pa, pb = spec["profile"]

    def half_width(t: float) -> float:
        return width / 2 * math.sin(math.pi * t**pa) ** pb

    ts = [i / 48 for i in range(49)]
    outline = [(x0 + length * t, cy - half_width(t)) for t in ts]
    outline += [(x0 + length * t, cy + half_width(t)) for t in reversed(ts)]

    mask = Image.new("L", (cw, ch), 0)
    ImageDraw.Draw(mask).polygon(outline, fill=255)

    tile = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    td = ImageDraw.Draw(tile)
    if spec["hindwing"]:
        td.ellipse(
            [x0 + length * 0.35, cy - width * 0.1, x0 + length * 0.8, cy + width * 0.75],
            fill=spec["hindwing"] + (255,),
        )

    wing = Image.new("RGBA", (cw, ch), spec["base"] + (255,))
    wd = ImageDraw.Draw(wing)
    for _ in range(spec["stripes"]):
        x = x0 + length * rng.uniform(0.1, 0.95)
        dx = length * rng.uniform(-0.08, 0.08)
        wd.line(
            [(x, cy - width / 2), (x + dx, cy + width / 2)],
            fill=spec["stripe"] + (255,),
            width=max(1, int(SS * rng.uniform(0.6, 1.3))),
        )
    if spec["tip"]:
        wd.ellipse(
            [x0 + length * 0.76, cy - width * 0.3, x0 + length * 0.98, cy + width * 0.3],
            fill=spec["tip"] + (255,),
        )
    for _ in range(spec["spots"]):
        sx = x0 + length * rng.uniform(0.1, 0.9)
        sy = cy + width * rng.uniform(-0.3, 0.3)
        r = SS * rng.uniform(1.0, 2.2)
        wd.ellipse([sx - r, sy - r, sx + r, sy + r], fill=(30, 28, 26, 255))
    wd.line(
        [(x0 + length * 0.04, cy), (x0 + length * 0.97, cy)],
        fill=(70, 60, 50, 255),
        width=SS,
    )
    tile.paste(wing, mask=mask)

    dark = (45, 38, 32, 255)
    td = ImageDraw.Draw(tile)
    td.line(outline + [outline[0]], fill=dark, width=SS)
    for i in range(3):  # legs
        lx = x0 + length * (0.08 + 0.07 * i)
        for sign in (-1, 1):
            td.line(
                [(lx, cy + sign * half_width(0.1 + 0.07 * i) * 0.8),
                 (lx - length * 0.05, cy + sign * width * 0.95)],
                fill=dark, width=max(1, SS // 2),
            )
    hr = width * 0.17  # head and antennae
    td.ellipse([x0 - hr * 1.6, cy - hr, x0 + hr * 0.4, cy + hr], fill=dark)
    for sign in (-1, 1):
        td.line(
            [(x0 - hr, cy), (x0 - length * 0.18, cy + sign * width * 0.55)],
            fill=dark, width=max(1, SS // 2),
        )
    return _finish_tile(tile, rng)


def gnat_tile(rng: random.Random) -> Image.Image:
    size = 14 * SS
    c = size / 2
    tile = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(tile)
    for sign in (-1, 1):
        d.ellipse([c - SS, c + sign * 3.2 * SS - 1.4 * SS, c + 4 * SS, c + sign * 3.2 * SS + 1.4 * SS],
                  fill=(205, 205, 198, 130))
        for i in range(3):
            lx = c - 2 * SS + i * 1.6 * SS
            d.line([(lx, c), (lx - SS, c + sign * 4.5 * SS)], fill=(40, 36, 32, 255), width=max(1, SS // 3))
    d.ellipse([c - 3.5 * SS, c - 1.3 * SS, c + 3.5 * SS, c + 1.3 * SS], fill=(35, 32, 30, 255))
    return _finish_tile(tile, rng)


def debris_tile(rng: random.Random) -> Image.Image:
    size = 40 * SS
    c = size / 2
    tile = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(tile)
    if rng.random() < 0.4:  # leaf fragment
        n, stretch = rng.randint(6, 9), rng.uniform(1.0, 1.8)
        r0 = rng.uniform(6, 13) * SS
        pts = []
        for i in range(n):
            a = 2 * math.pi * i / n
            r = r0 * rng.uniform(0.7, 1.1)
            pts.append((c + r * stretch * math.cos(a), c + r * math.sin(a)))
        shade = rng.randint(-15, 15)
        d.polygon(pts, fill=(98 + shade, 92 + shade, 52, 255), outline=(60, 56, 34, 255))
        d.line([pts[0], pts[n // 2]], fill=(66, 62, 38, 255), width=SS // 2 or 1)
    else:  # dust speck
        r = rng.uniform(1.0, 2.8) * SS
        d.ellipse([c - r, c - r, c + r, c + r], fill=(62, 56, 46, 255))
    return _finish_tile(tile, rng)


def card_background(rng: random.Random) -> Image.Image:
    img = Image.new("RGB", (W, H), (58, 62, 66))
    d = ImageDraw.Draw(img)
    tint = rng.randint(-8, 8)
    d.rounded_rectangle(CARD, radius=14, fill=(244 + tint // 2, 214 + tint, 58))
    line = (226 + tint // 2, 194 + tint, 40)
    for x in range(CARD[0] + GRID_PX, CARD[2], GRID_PX):
        d.line([(x, CARD[1]), (x, CARD[3])], fill=line, width=1)
    for y in range(CARD[1] + GRID_PX, CARD[3], GRID_PX):
        d.line([(CARD[0], y), (CARD[2], y)], fill=line, width=1)
    return img


def _noise(size: tuple[int, int], rng: random.Random) -> Image.Image:
    return Image.frombytes("L", size, rng.randbytes(size[0] * size[1])).convert("RGB")


def camera_effects(img: Image.Image, rng: random.Random) -> Image.Image:
    blotch = _noise((W // 8, H // 8), rng).resize((W, H), Image.BICUBIC)
    img = Image.blend(img, ImageChops.overlay(img, blotch), 0.10)
    img = Image.blend(img, ImageChops.overlay(img, _noise((W, H), rng)), 0.05)
    vignette = (
        Image.radial_gradient("L").resize((W, H), Image.BICUBIC)
        .point(lambda v: 255 - int(v * 0.3)).convert("RGB")
    )
    img = ImageChops.multiply(img, vignette)
    img = ImageEnhance.Brightness(img).enhance(rng.uniform(0.9, 1.08))
    return img.filter(ImageFilter.GaussianBlur(0.6))


def place(img: Image.Image, tiles: list, rng: random.Random) -> list:
    """Paste tiles without overlap; return a box record per tile actually placed."""
    placed, boxes = [], []
    for label, tile in sorted(tiles, key=lambda t: -max(t[1].size)):
        r = max(tile.size) / 2 * 0.8
        for _ in range(300):
            x = rng.uniform(CARD[0] + r + 8, CARD[2] - r - 8)
            y = rng.uniform(CARD[1] + r + 8, CARD[3] - r - 8)
            if all(math.hypot(x - px, y - py) >= r + pr for px, py, pr in placed):
                left, top = int(x - tile.width / 2), int(y - tile.height / 2)
                img.paste(tile, (left, top), tile)
                placed.append((x, y, r))
                boxes.append({"label": label, "bbox": [left, top, left + tile.width, top + tile.height]})
                break
    return boxes


def render(counts: dict, n_gnats: int, n_debris: int, rng: random.Random):
    img = card_background(rng)
    tiles = [(k, moth_tile(SPECIES[k], rng)) for k, n in counts.items() for _ in range(n)]
    tiles += [("gnat", gnat_tile(rng)) for _ in range(n_gnats)]
    tiles += [("debris", debris_tile(rng)) for _ in range(n_debris)]
    boxes = place(img, tiles, rng)
    return camera_effects(img, rng), boxes


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--counts", type=int, nargs="+", default=[0, 2, 5, 12, 25, 50],
                   help="codling moth count for each image")
    p.add_argument("--out", type=Path, default=root / "data" / "traps")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--trap-id", default="block-c-04")
    args = p.parse_args()

    rng = random.Random(args.seed)
    args.out.mkdir(parents=True, exist_ok=True)
    start = datetime(2026, 5, 12, 14, 3, tzinfo=timezone.utc)
    manifest = []

    for i, n in enumerate(args.counts):
        counts = {
            "codling_moth": n,
            "oriental_fruit_moth": n // 4,
            "spotted_lanternfly": rng.choice([0, 0, 1, 2]) if n >= 5 else 0,
        }
        img, boxes = render(counts, rng.randint(4, 10) + n // 3, rng.randint(6, 14) + n // 2, rng)
        name = f"trap_{i:02d}_codling{n:03d}.jpg"
        img.save(args.out / name, quality=92)

        stamp = (start + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M:%SZ")
        actual = {k: sum(b["label"] == k for b in boxes) for k in SPECIES}
        if actual != counts:
            print(f"warning: {name} could only place {actual}, wanted {counts}")
        manifest.append({
            "file": name,
            "counts": [
                {"trap_id": args.trap_id, "timestamp": stamp, "species": k, "count": v}
                for k, v in actual.items()
            ],
            "boxes": boxes,
        })
        print(f"{name}: {actual}")

    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
