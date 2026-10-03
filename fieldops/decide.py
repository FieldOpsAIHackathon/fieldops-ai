"""Biofix, degree-days and spray window, emitted as the replay timeline the dashboard plays back.

    python -m fieldops.decide            # self-test, then print each block's milestones
    python -m fieldops.decide --replay   # also write dashboard/data/timeline.json and timeline.js

Deterministic: no LLM, no randomness. Shape and rules are pinned in
dashboard/TIMELINE_CONTRACT.md; thresholds come from species.json.
"""
import argparse
import json
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from . import species as species_cfg

DASHBOARD_DATA = Path(__file__).resolve().parent.parent / "dashboard" / "data"
THRESHOLD_KEYS = (
    "biofix_min_count", "biofix_consecutive_checks", "dd_base_f", "dd_upper_f",
    "spray_open_dd", "spray_close_dd",
)


def block_of(trap_id: str) -> str:
    return trap_id.rsplit("-", 1)[0]


def daily_dd(tmin: float, tmax: float, base: float, upper: float) -> float:
    """Average method with horizontal cutoff, as pinned in the timeline contract."""
    avg = (min(tmax, upper) + max(tmin, base)) / 2
    return max(0.0, avg - base)


def _pest_key(config: dict) -> str:
    for key, cfg in config["species"].items():
        if all(k in cfg for k in THRESHOLD_KEYS):
            return key
    raise ValueError("no species in config has biofix and degree-day thresholds")


def build_timeline(records: list, weather: dict, config: dict = None) -> dict:
    """records: contract dicts. weather: {date: (tmin_f, tmax_f)} for every day in the records."""
    config = config or species_cfg.load()
    pest = _pest_key(config)
    cfg = config["species"][pest]
    th = {k: cfg[k] for k in THRESHOLD_KEYS}
    pest_name = cfg["display_name"]

    by_trap = defaultdict(lambda: defaultdict(int))
    for r in records:
        if r["species"] == pest:
            by_trap[r["trap_id"]][date.fromisoformat(r["timestamp"][:10])] += r["count"]
    if not by_trap:
        raise ValueError(f"no {pest} counts to build a timeline from")

    known = {b["id"] for b in config["blocks"]}
    traps = defaultdict(list)
    for trap_id in sorted(by_trap):
        if block_of(trap_id) not in known:
            raise ValueError(f"trap {trap_id} is not in any block in species.json")
        traps[block_of(trap_id)].append(trap_id)
    blocks = [
        {"id": b["id"], "name": b["name"], "variety": b["variety"], "acres": b["acres"],
         "traps": traps[b["id"]], "col": b["col"], "row": b["row"]}
        for b in config["blocks"]
    ]

    all_days = {d for per_day in by_trap.values() for d in per_day}
    first, last = min(all_days), max(all_days)
    state = {b["id"]: {"run": [], "biofix": None, "dd": 0.0, "status": "watching"} for b in blocks}
    prev = {b["id"]: 0 for b in blocks}
    dd_by_day, days = {}, []

    d = first
    while d <= last:
        if d not in weather:
            raise ValueError(f"no weather for {d}; cannot accumulate degree-days")
        tmin, tmax = weather[d]
        dd_today = daily_dd(tmin, tmax, th["dd_base_f"], th["dd_upper_f"])
        dd_by_day[d] = dd_today
        day = {"date": d.isoformat(), "tmin_f": tmin, "tmax_f": tmax, "dd_today": round(dd_today, 1),
               "counts": {}, "traps": {}, "blocks": {}, "events": []}

        for b in blocks:
            bid, name, s = b["id"], b["name"], state[b["id"]]
            trap_counts = {t: by_trap[t].get(d, 0) for t in b["traps"]}
            c = sum(trap_counts.values())
            day["traps"].update(trap_counts)
            day["counts"][bid] = c
            events = []

            if s["biofix"] is None:
                s["run"] = s["run"] + [d] if c >= th["biofix_min_count"] else []
                if len(s["run"]) >= th["biofix_consecutive_checks"]:
                    s["biofix"], s["status"] = s["run"][0], "accumulating"
                    # The run is only recognised once it completes, so catch up on the days after its first day.
                    s["dd"] = sum(dd_by_day[s["biofix"] + timedelta(days=i)]
                                  for i in range(1, (d - s["biofix"]).days + 1))
                    events.append(("biofix", f"Biofix set on {name}",
                                   f"Sustained {pest_name.lower()} catch on {name}: {c} moths today after "
                                   f"{prev[bid]} yesterday. Degree-day clock starts now."))
            else:
                s["dd"] += dd_today

            if s["status"] == "accumulating" and s["dd"] >= th["spray_open_dd"]:
                s["status"] = "spray_window"
                events.append(("spray_window_open", f"Spray window open on {name}",
                               f"{name} has reached {s['dd']:.0f} degree-days since biofix with {c} moths in "
                               f"traps today. Time to spray for {pest_name.lower()}."))
            if s["status"] == "spray_window" and s["dd"] >= th["spray_close_dd"]:
                s["status"] = "window_closed"
                events.append(("spray_window_close", f"Spray window closed on {name}",
                               f"{name} is at {s['dd']:.0f} degree-days since biofix with {c} moths today. "
                               "The first-generation spray window has passed."))

            prev[bid] = c
            day["blocks"][bid] = {
                "status": s["status"],
                "biofix_date": s["biofix"].isoformat() if s["biofix"] else None,
                "dd_since_biofix": round(s["dd"], 1),
            }
            day["events"] += [{"block_id": bid, "type": t, "title": ti, "message": m} for t, ti, m in events]

        days.append(day)
        d += timedelta(days=1)

    farm = dict(config["farm"], crop=config["crop"], pest=pest, pest_name=pest_name)
    return {"farm": farm, "thresholds": th, "blocks": blocks, "days": days}


def validate(tl: dict) -> None:
    """Check the timeline against the invariants in TIMELINE_CONTRACT.md."""
    days = [date.fromisoformat(x["date"]) for x in tl["days"]]
    assert all((b - a).days == 1 for a, b in zip(days, days[1:])), "gap in days"
    for b in tl["blocks"]:
        bid = b["id"]
        assert all(isinstance(x["counts"][bid], int) and x["counts"][bid] >= 0 for x in tl["days"])
        dds = [x["blocks"][bid]["dd_since_biofix"] for x in tl["days"]]
        assert all(a <= c for a, c in zip(dds, dds[1:])), f"degree-days decreased in {bid}"
    assert all(x["tmin_f"] < x["tmax_f"] for x in tl["days"])
    assert json.loads(json.dumps(tl)) == tl, "JSON round trip"


def event_date(tl: dict, block_id: str, event_type: str):
    for day in tl["days"]:
        if any(e["block_id"] == block_id and e["type"] == event_type for e in day["events"]):
            return day["date"]
    return None


def write_timeline(tl: dict, out_dir: Path = DASHBOARD_DATA) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "timeline.json").write_text(json.dumps(tl, indent=1) + "\n")
    (out_dir / "timeline.js").write_text(
        "window.FIELDOPS_TIMELINE = " + json.dumps(tl, separators=(",", ":")) + ";\n"
    )


def print_summary(tl: dict) -> None:
    print(f"{'block':9}{'biofix':12}{'confirmed':12}{'spray open':12}{'spray close':12}")
    for b in tl["blocks"]:
        bid = b["id"]
        biofix = next((x["blocks"][bid]["biofix_date"] for x in tl["days"] if x["blocks"][bid]["biofix_date"]), None)
        row = (b["name"], biofix, event_date(tl, bid, "biofix"),
               event_date(tl, bid, "spray_window_open"), event_date(tl, bid, "spray_window_close"))
        print(f"{row[0]:9}" + "".join(f"{v or '-':12}" for v in row[1:]))
    opens = event_date(tl, "block-c", "spray_window_open")
    if opens:
        print(f"\nBlock C spray window opens {date.fromisoformat(opens):%A} {opens}")


def selftest() -> None:
    assert daily_dd(40, 48, 50, 88) == 0  # mean sits below base
    assert daily_dd(40, 58, 50, 88) == 4  # the low is clamped up to 50, so (58 + 50) / 2 - 50
    assert daily_dd(60, 95, 50, 88) == 24  # a 95 F high is clamped to 88
    assert daily_dd(48, 70, 50, 88) == 10  # a low under base is clamped up to 50

    cfg = {
        "farm": {"name": "t", "location": "t", "season": 2026}, "crop": "apple",
        "blocks": [{"id": "block-x", "name": "Block X", "variety": "v", "acres": 1, "col": 0, "row": 0}],
        "species": {"codling_moth": {
            "display_name": "Codling moth", "dd_base_f": 50, "dd_upper_f": 88,
            "biofix_min_count": 2, "biofix_consecutive_checks": 2, "spray_open_dd": 25, "spray_close_dd": 35,
        }},
    }
    start = date(2026, 5, 1)

    def run(counts):
        records = [{"trap_id": "block-x-01", "timestamp": f"{start + timedelta(days=i):%Y-%m-%d}T14:00:00Z",
                    "species": "codling_moth", "count": n} for i, n in enumerate(counts)]
        weather = {start + timedelta(days=i): (50, 70) for i in range(len(counts))}  # 10 DD every day
        return build_timeline(records, weather, cfg)

    quiet = run([0] * 8)
    assert all(x["blocks"]["block-x"]["status"] == "watching" for x in quiet["days"])
    assert event_date(quiet, "block-x", "biofix") is None

    # A lone blip on May 2 is ignored; the run on May 5-6 sets biofix_date May 5, and the event fires May 6.
    tl = run([0, 5, 0, 0, 3, 4, 0, 0, 0])
    block = lambda i: tl["days"][i]["blocks"]["block-x"]
    assert event_date(tl, "block-x", "biofix") == "2026-05-06"
    assert block(5)["biofix_date"] == "2026-05-05"
    assert block(5)["dd_since_biofix"] == 10  # only days after biofix_date count
    assert block(6)["dd_since_biofix"] == 20  # hand-computed: two days x 10 DD
    assert event_date(tl, "block-x", "spray_window_open") == "2026-05-08"  # 30 DD >= 25
    assert event_date(tl, "block-x", "spray_window_close") == "2026-05-09"  # 40 DD >= 35
    validate(tl)


def main() -> None:
    from . import store
    from .season import CSV_PATH, load_csv

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--season", type=Path, default=CSV_PATH, help="season CSV to read")
    p.add_argument("--db", type=Path, default=store.DEFAULT_DB, help="store to read instead of the CSV")
    p.add_argument("--csv", action="store_true", help="read the CSV even if the store has data")
    p.add_argument("--replay", action="store_true", help="write dashboard/data/timeline.json and .js")
    args = p.parse_args()

    selftest()
    records, weather = (None, None) if args.csv else store.read(args.db)
    if records and weather:
        print(f"reading {args.db}")
    else:
        if not args.csv:
            print(f"{args.db} is empty; reading {args.season}"
                  f" (load it with: python -m fieldops.store --load {args.season})")
        records, weather = load_csv(args.season)
    tl = build_timeline(records, weather)
    validate(tl)
    print_summary(tl)
    if args.replay:
        write_timeline(tl)
        print(f"\nwrote {DASHBOARD_DATA / 'timeline.json'} and timeline.js")


if __name__ == "__main__":
    main()
