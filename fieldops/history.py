"""Two seasons of multi-species trap history, for exercising the store with realistic data.

    python -m fieldops.history                 # write data/history.csv and load data/history.db
    python -m fieldops.history --seed 7 --no-load

Deliberately separate from the demo. season.py's 2026 season is tuned (its temperature seed is
picked so block C's spray window opens on a Thursday), and build_timeline spans min..max of the
codling moth dates, so loading two years into the demo store would stretch the replay to 24
months. This writes its own CSV and its own store and never touches either demo artefact.

What makes it a workout for the store rather than a second season:
  - two full seasons, 2025 and 2026
  - ten species with different flight windows and generation counts
  - thirty traps, five per block, each carrying its own lure
  - irregular checks: each trap on its own cadence, at an arbitrary hour of the day
  - counts accumulate over the days since that trap was last checked
"""
import argparse
import csv
import json
import random
from datetime import date, datetime, timedelta
from pathlib import Path

from . import species as species_cfg
from .season import poisson

CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "history.csv"
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "history.db"
SEED = 2026
YEARS = (2025, 2026)
SEASON = ((4, 1), (9, 30))  # trapping runs April through September

# (month, day) of each generation's peak, flight width in days, moths per trap per day at the peak.
# Timings follow the usual Northeast apple sequence; treat them as plausible, not authoritative.
SPECIES = {
    "green_fruitworm":           ([(4, 12)], 14, 1.6),
    "plum_curculio":             ([(5, 12)], 18, 1.1),
    "oriental_fruit_moth":       ([(5, 6), (7, 2), (8, 20)], 15, 2.2),
    "codling_moth":              ([(5, 24), (7, 28)], 17, 2.6),
    "san_jose_scale":            ([(5, 30), (7, 26)], 12, 3.4),
    "obliquebanded_leafroller":  ([(6, 18), (8, 10)], 16, 1.9),
    "dogwood_borer":             ([(7, 6)], 34, 0.9),
    "apple_maggot":              ([(7, 20)], 40, 1.4),
    "brown_marmorated_stink_bug": ([(6, 24), (8, 28)], 22, 1.2),
    "spotted_lanternfly":        ([(8, 22)], 36, 2.0),
}

# Each trap carries one lure. Bycatch of other species is recorded only when something is caught.
LURES = list(SPECIES)
TRAPS_PER_BLOCK = 5     # a real orchard runs several lures per block, not one
BYCATCH = 0.3           # chance a non-target species is looked for at a given check
CHECK_DAYS = (2, 7)     # a trap is walked every 2 to 7 days
CHECK_HOURS = (6, 20)   # and at an arbitrary hour between these

CLIMATE = [((4, 1), 34, 52), ((5, 1), 44, 65), ((6, 1), 54, 75), ((7, 1), 61, 83),
           ((8, 1), 60, 81), ((9, 1), 52, 73), ((9, 30), 44, 64)]


def _interp(day: date) -> tuple:
    """Seasonal normal (tmin, tmax) for a day, linear between the CLIMATE anchors."""
    points = [(date(day.year, m, d), lo, hi) for (m, d), lo, hi in CLIMATE]
    if day <= points[0][0]:
        return points[0][1], points[0][2]
    for (d0, lo0, hi0), (d1, lo1, hi1) in zip(points, points[1:]):
        if day <= d1:
            f = (day - d0).days / max((d1 - d0).days, 1)
            return lo0 + (lo1 - lo0) * f, hi0 + (hi1 - hi0) * f
    return points[-1][1], points[-1][2]


def weather(rng: random.Random) -> dict:
    """{date: (tmin_f, tmax_f)} for both seasons, with warm and cold spells that persist."""
    out, anomaly = {}, 0.0
    for day in all_days():
        anomaly = 0.7 * anomaly + rng.gauss(0, 3.2)  # yesterday's weather predicts today's
        lo, hi = _interp(day)
        tmin = round(lo + anomaly + rng.gauss(0, 1.5), 1)
        tmax = round(max(hi + anomaly + rng.gauss(0, 1.8), tmin + 4), 1)
        out[day] = (tmin, tmax)
    return out


def all_days():
    for year in YEARS:
        day, end = date(year, *SEASON[0]), date(year, *SEASON[1])
        while day <= end:
            yield day
            day += timedelta(days=1)


def daily_rate(species: str, day: date, shift: int, vigour: float) -> float:
    """Moths per day for one trap: the sum of this species' generation curves, plus a trickle."""
    peaks, width, peak_rate = SPECIES[species]
    total = 0.0
    for month, dom in peaks:
        centre = date(day.year, month, dom) + timedelta(days=shift)
        t = (day - centre).days
        total += peak_rate * 2.718281828 ** (-((t / width) ** 2))  # gaussian around the peak
    return 0.02 + total * vigour


def build(seed: int) -> list:
    rng = random.Random(seed)
    cfg = species_cfg.load()
    traps = [f"{b['id']}-{n:02d}" for b in cfg["blocks"] for n in range(1, TRAPS_PER_BLOCK + 1)]
    # Spread the lures across the traps so every species is somebody's target.
    lure_of = {t: LURES[i % len(LURES)] for i, t in enumerate(traps)}
    vigour = {t: rng.lognormvariate(0, 0.28) for t in traps}
    shift = {t: rng.randint(-5, 5) for t in traps}  # blocks warm up at different rates

    rows = []
    for year in YEARS:
        start, end = date(year, *SEASON[0]), date(year, *SEASON[1])
        year_shift = rng.randint(-6, 6)  # a late spring moves the whole season
        for trap in traps:
            day = start + timedelta(days=rng.randint(0, 5))
            last = day
            while day <= end:
                stamp = datetime(day.year, day.month, day.day,
                                 rng.randrange(*CHECK_HOURS), rng.randrange(60), rng.randrange(60))
                span = max((day - last).days, 1)
                offset = shift[trap] + year_shift
                caught = {}
                for species in SPECIES:
                    if species != lure_of[trap] and rng.random() > BYCATCH:
                        continue
                    lam = sum(daily_rate(species, last + timedelta(days=i), offset, vigour[trap])
                              for i in range(span))
                    if species != lure_of[trap]:
                        lam *= 0.25  # a trap without the right lure catches far less
                    n = poisson(rng, lam)
                    if n or species == lure_of[trap]:
                        caught[species] = n
                for species, n in caught.items():
                    rows.append([stamp.strftime("%Y-%m-%dT%H:%M:%SZ"), trap, lure_of[trap], species, n])
                last = day
                day += timedelta(days=rng.randint(*CHECK_DAYS))
    rows.sort(key=lambda r: (r[0], r[1], r[3]))
    return rows


def write_csv(rows: list, wx: dict, path: Path = CSV_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "trap_id", "lure", "species", "count", "tmin_f", "tmax_f"])
        for stamp, trap, lure, species, n in rows:
            tmin, tmax = wx[date.fromisoformat(stamp[:10])]
            w.writerow([stamp, trap, lure, species, n, tmin, tmax])


def records(rows: list) -> list:
    """Contract shape, which is what the store validates and stores."""
    return [{"trap_id": t, "timestamp": s, "species": sp, "count": n} for s, t, _, sp, n in rows]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--seed", type=int, default=SEED)
    p.add_argument("--csv", type=Path, default=CSV_PATH)
    p.add_argument("--db", type=Path, default=DB_PATH)
    p.add_argument("--no-load", action="store_true", help="write the CSV but do not touch a store")
    args = p.parse_args()

    rng = random.Random(args.seed)
    wx = weather(rng)
    rows = build(args.seed)
    write_csv(rows, wx, args.csv)
    print(f"wrote {len(rows)} readings to {args.csv}")

    if not args.no_load:
        from . import store

        counts = store.add(records(rows), args.db)
        days = store.add_temps(wx, args.db)
        print(f"loaded {counts} counts and {days} days of weather into {args.db}")


if __name__ == "__main__":
    main()
