"""Build data/season.csv: one synthetic apple season of daily trap counts and temperatures.

    python -m fieldops.season        # rewrites data/season.csv, deterministic

The CSV is committed. Never run this at demo time.
"""
import argparse
import csv
import math
import random
from datetime import date, timedelta
from pathlib import Path

CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "season.csv"
START, END = date(2026, 4, 15), date(2026, 8, 31)
COUNT_SEED = 2026
TEMP_SEED = 94  # picked so block-c's spray window opens on a Thursday for the pitch line

# block letter -> (relative pressure, flight shift in days; negative is earlier)
BLOCKS = {"a": (1.00, 0), "b": (0.90, 1), "c": (1.40, -4), "d": (1.10, 2), "e": (0.85, 1), "f": (0.70, 3)}
TRAP_WEIGHTS = [0.8, 1.0, 1.2]
STRAY = ("block-c-02", date(2026, 4, 28), "codling_moth", 6)  # one-day blip that must not set biofix

# Piecewise-linear climate anchors: (date, tmin_f, tmax_f), plus (first, last, delta_f) spells.
CLIMATE = [(date(2026, 4, 15), 38, 57), (date(2026, 5, 15), 47, 69), (date(2026, 6, 15), 56, 77),
           (date(2026, 7, 20), 64, 85), (date(2026, 8, 31), 56, 78)]
SPELLS = [(date(2026, 4, 21), date(2026, 4, 24), -9), (date(2026, 5, 4), date(2026, 5, 7), -8),
          (date(2026, 7, 9), date(2026, 7, 12), 9)]


def poisson(rng: random.Random, lam: float) -> int:
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def flight(day: date, shift: int) -> float:
    """Mean catch per trap at pressure 1: first flight peaks ~Jun 1, second ~Aug 3, else ~0."""
    n = (day - date(2026, 1, 1)).days - shift
    peak = lambda when, sigma, amp: amp * math.exp(-((n - (when - date(2026, 1, 1)).days) ** 2) / (2 * sigma ** 2))
    v = peak(date(2026, 6, 1), 9, 7.0) + peak(date(2026, 8, 3), 8, 3.2)
    return v if v > 0.12 else 0.0


def days():
    d = START
    while d <= END:
        yield d
        d += timedelta(days=1)


def temps(seed: int) -> dict:
    rng = random.Random(seed)
    out = {}
    for d in days():
        for (d0, lo0, hi0), (d1, lo1, hi1) in zip(CLIMATE, CLIMATE[1:]):
            if d0 <= d <= d1:
                f = (d - d0).days / (d1 - d0).days
                lo, hi = lo0 + f * (lo1 - lo0), hi0 + f * (hi1 - hi0)
                break
        shift = rng.gauss(0, 3.5) + sum(x for a, b, x in SPELLS if a <= d <= b)
        tmin = round(lo + shift * 0.8 + rng.gauss(0, 1.5))
        tmax = round(hi + shift + rng.gauss(0, 2))
        out[d] = (tmin, max(tmax, tmin + 6))
    return out


def counts() -> list:
    """(date, trap_id, species, count) rows; independent of the temperature seed."""
    rng = random.Random(COUNT_SEED)
    rows = []
    for letter, (pressure, shift) in BLOCKS.items():
        for i, w in enumerate(TRAP_WEIGHTS, 1):
            trap_id = f"block-{letter}-0{i}"
            for d in days():
                for sp, scale, lag in (("codling_moth", 1.0, 0), ("oriental_fruit_moth", 0.35, 10)):
                    lam = flight(d, shift + lag) * pressure * w * scale
                    n = poisson(rng, lam) if lam else int(rng.random() < 0.03)  # rare pre-flight stray
                    if (trap_id, d, sp) == STRAY[:3]:
                        n = STRAY[3]
                    rows.append((d, trap_id, sp, n))
    return rows


def write_csv(path: Path = CSV_PATH, temp_seed: int = TEMP_SEED) -> int:
    weather, rows = temps(temp_seed), counts()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "tmin_f", "tmax_f", "trap_id", "species", "count"])
        for d, trap_id, sp, n in sorted(rows, key=lambda r: (r[0], r[1], r[2])):
            w.writerow([d.isoformat(), *weather[d], trap_id, sp, n])
    return len(rows)


def load_csv(path: Path = CSV_PATH):
    """Return (records in contract shape, {date: (tmin_f, tmax_f)})."""
    records, weather = [], {}
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            weather[date.fromisoformat(r["date"])] = (float(r["tmin_f"]), float(r["tmax_f"]))
            records.append({
                "trap_id": r["trap_id"],
                "timestamp": f"{r['date']}T14:00:00Z",
                "species": r["species"],
                "count": int(r["count"]),
            })
    return records, weather


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--temp-seed", type=int, default=TEMP_SEED)
    p.add_argument("--out", type=Path, default=CSV_PATH)
    args = p.parse_args()
    print(f"wrote {write_csv(args.out, args.temp_seed)} rows to {args.out}")


if __name__ == "__main__":
    main()
