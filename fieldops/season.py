"""Build data/season.csv: one synthetic apple season of daily trap counts and temperatures.

    python -m fieldops.season        # rewrites data/season.csv, deterministic for a given seed

The CSV is committed. Never run this at demo time.
"""
import argparse
import csv
import math
import random
from datetime import date, timedelta
from pathlib import Path

CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "season.csv"
START, DAYS = date(2026, 4, 15), 91
FLIGHT_START = date(2026, 5, 11)  # a Monday; block-c is the lead block in the pitch
BLOCK_LAG_DAYS = {"a": 3, "b": 1, "c": 0, "d": 2, "e": 4}
TRAPS_PER_BLOCK = 4
STRAY = ("block-c-02", date(2026, 4, 28), "codling_moth", 6)  # one-day blip that must not count as biofix

# peak = expected catch per trap per day at the top of the flight curve
FLIGHT = {
    "codling_moth": dict(peak=2.5, width=16, start_lag=0),
    "oriental_fruit_moth": dict(peak=1.0, width=22, start_lag=12),
}
BACKGROUND = 0.03


def poisson(rng: random.Random, lam: float) -> int:
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def flight_shape(t: int, width: int) -> float:
    """0 before emergence, 1.0 at the peak (day t == width - 1), long right tail."""
    if t < 0:
        return 0.0
    x = (t + 1) / width
    return (x * math.exp(1 - x)) ** 2


def build(seed: int) -> list:
    rng = random.Random(seed)
    traps = {
        f"block-{b}-{n:02d}": (b, rng.lognormvariate(0, 0.3))
        for b in BLOCK_LAG_DAYS for n in range(1, TRAPS_PER_BLOCK + 1)
    }
    rows, anomaly = [], 0.0
    for i in range(DAYS):
        day = START + timedelta(days=i)
        doy = day.timetuple().tm_yday
        anomaly = 0.6 * anomaly + rng.gauss(0, 3)  # warm and cold spells last a few days
        mean = 50 + 24 * math.sin(2 * math.pi * (doy - 110) / 365) + anomaly
        swing = rng.uniform(16, 22)
        tmax, tmin = round(mean + swing / 2, 1), round(mean - swing / 2, 1)

        for trap_id, (block, trap_mult) in traps.items():
            for sp, f in FLIGHT.items():
                first = FLIGHT_START + timedelta(days=f["start_lag"] + BLOCK_LAG_DAYS[block])
                lam = BACKGROUND + f["peak"] * trap_mult * flight_shape((day - first).days, f["width"])
                count = poisson(rng, lam)
                if (trap_id, day, sp) == STRAY[:3]:
                    count = STRAY[3]
                rows.append([day.isoformat(), tmax, tmin, trap_id, sp, count])
    return rows


def write_csv(rows: list, path: Path = CSV_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "tmax_f", "tmin_f", "trap_id", "species", "count"])
        w.writerows(rows)


def load_csv(path: Path = CSV_PATH):
    """Return (records in contract shape, {date: (tmax_f, tmin_f)})."""
    records, weather = [], {}
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            day = date.fromisoformat(r["date"])
            weather[day] = (float(r["tmax_f"]), float(r["tmin_f"]))
            records.append({
                "trap_id": r["trap_id"],
                "timestamp": f"{r['date']}T14:00:00Z",
                "species": r["species"],
                "count": int(r["count"]),
            })
    return records, weather


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--seed", type=int, default=2026)
    p.add_argument("--out", type=Path, default=CSV_PATH)
    args = p.parse_args()
    rows = build(args.seed)
    write_csv(rows, args.out)
    print(f"wrote {len(rows)} rows to {args.out}")


if __name__ == "__main__":
    main()
