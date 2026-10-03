"""Simulate trap readings arriving, the way the vision lane will emit them.

    python3 dashboard/tools/simulate_feed.py                 # one season day per second, loops
    python3 dashboard/tools/simulate_feed.py --pace 0.5      # faster
    python3 dashboard/tools/simulate_feed.py --start 2026-05-10 --end 2026-06-10 --no-loop

Walks data/season.csv day by day and rewrites dashboard/data/live.json on every step: the day's
records in the AGENTS.md count-contract shape (with a trap image for codling moth readings), plus
the last 30 records newest first. The dashboard's Live toggle polls that file and advances with it.
Nothing here decides anything; decide.py and the committed timeline stay the source of truth.
Stdlib only. Ctrl-C stops it.
"""
import argparse
import csv
import json
import random
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SEASON = ROOT / "data" / "season.csv"
TIMELINE = ROOT / "dashboard" / "data" / "timeline.json"
LIVE = ROOT / "dashboard" / "data" / "live.json"
TRAPS = ROOT / "data" / "traps"
IMAGE_BUCKETS = [(0, "trap_00_codling000.jpg"), (2, "trap_01_codling002.jpg"), (5, "trap_02_codling005.jpg"),
                 (12, "trap_03_codling012.jpg"), (25, "trap_04_codling025.jpg"), (50, "trap_05_codling050.jpg")]


def load_season():
    by_day = {}
    with open(SEASON, newline="") as f:
        for r in csv.DictReader(f):
            by_day.setdefault(r["date"], []).append(r)
    return by_day


def image_for(count: int):
    best = min(IMAGE_BUCKETS, key=lambda b: abs(b[0] - count))[1]
    return f"../data/traps/{best}" if (TRAPS / best).exists() else None


def day_records(day: str, rows: list, rng: random.Random) -> list:
    """Spread the day's readings across working hours so the feed looks like cameras reporting."""
    out = []
    for r in sorted(rows, key=lambda r: (r["trap_id"], r["species"])):
        minute = rng.randint(6 * 60, 18 * 60)
        stamp = f"{day}T{minute // 60:02d}:{minute % 60:02d}:00Z"
        rec = {"trap_id": r["trap_id"], "timestamp": stamp, "species": r["species"], "count": int(r["count"])}
        if r["species"] == "codling_moth":
            img = image_for(rec["count"])
            if img:
                rec["image"] = img
        out.append(rec)
    out.sort(key=lambda r: r["timestamp"])
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--pace", type=float, default=1.0, help="seconds per season day")
    p.add_argument("--start", default=None, help="YYYY-MM-DD, default first season day")
    p.add_argument("--end", default=None, help="YYYY-MM-DD, default last season day")
    p.add_argument("--no-loop", action="store_true", help="stop at --end instead of restarting")
    p.add_argument("--seed", type=int, default=7)
    args = p.parse_args()

    by_day = load_season()
    days = sorted(by_day)
    tl_dates = [d["date"] for d in json.loads(TIMELINE.read_text())["days"]] if TIMELINE.exists() else days
    start, end = args.start or days[0], args.end or days[-1]
    walk = [d for d in days if start <= d <= end]
    if not walk:
        raise SystemExit(f"no season days between {start} and {end}")
    rng = random.Random(args.seed)
    started = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    recent, tick = [], 0
    print(f"simulating {walk[0]} to {walk[-1]} at {args.pace}s per day -> {LIVE}  (Ctrl-C to stop)")
    try:
        while True:
            for day in walk:
                tick += 1
                recs = day_records(day, by_day[day], rng)
                recent = (list(reversed(recs)) + recent)[:30]
                live = {
                    "as_of": day,
                    "day_index": tl_dates.index(day) if day in tl_dates else days.index(day),
                    "tick": tick, "pace_s": args.pace, "started": started,
                    "records_today": recs, "recent": recent,
                }
                tmp = LIVE.with_suffix(".tmp")
                tmp.write_text(json.dumps(live, separators=(",", ":")))
                tmp.replace(LIVE)  # atomic, so the dashboard never reads a half-written file
                codling = sum(r["count"] for r in recs if r["species"] == "codling_moth")
                print(f"\r{day}  day {live['day_index']:3d}  {len(recs):2d} readings  {codling:3d} codling moths   ", end="", flush=True)
                time.sleep(args.pace)
            if args.no_loop:
                break
            recent = []
    except KeyboardInterrupt:
        pass
    print("\nstopped")


if __name__ == "__main__":
    main()
