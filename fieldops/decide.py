"""Biofix, degree-days and spray window, emitted as the replay timeline the dashboard plays back.

    python -m fieldops.decide            # self-test, then print each block's milestones
    python -m fieldops.decide --replay   # also write dashboard/data/timeline.json and timeline.js

Deterministic: no LLM, no randomness. Shape and rules are pinned in
dashboard/TIMELINE_CONTRACT.md; thresholds come from species.json.
"""
import argparse
import json
import math
from collections import defaultdict
from datetime import date, timedelta
from functools import lru_cache
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


def build_timeline(records: list, weather: dict, config: dict = None, normals: dict = None) -> dict:
    """records: contract dicts. weather: {date: (tmin_f, tmax_f)} for every day in the records.

    normals feeds each block's projected_open: None uses the committed ten-year averages, {} forces the
    last-week-rate fallback.
    """
    config = config or species_cfg.load()
    normals = _default_normals() if normals is None else normals
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
                "projected_open": _estimate_open(d, th["spray_open_dd"] - s["dd"], th, normals, dd_by_day)
                if s["status"] == "accumulating" else None,
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
        for x in tl["days"]:  # projected_open is optional: absent or null means no estimate
            guess = x["blocks"][bid].get("projected_open")
            if guess is not None:
                assert x["blocks"][bid]["status"] == "accumulating", f"estimate outside accumulating: {bid} {x['date']}"
                assert date.fromisoformat(guess) > date.fromisoformat(x["date"]), f"estimate in the past: {bid} {x['date']}"
    assert all(x["tmin_f"] < x["tmax_f"] for x in tl["days"])
    assert json.loads(json.dumps(tl)) == tl, "JSON round trip"


def event_date(tl: dict, block_id: str, event_type: str):
    for day in tl["days"]:
        if any(e["block_id"] == block_id and e["type"] == event_type for e in day["events"]):
            return day["date"]
    return None


# Per-block views of the timeline, for the agent's tools. They add no rules of their own.
EVENT_NAMES = {"biofix": "biofix_confirmed", "spray_window_open": "spray_window_open",
               "spray_window_close": "spray_window_closed"}


@lru_cache(maxsize=None)
def _default_normals() -> dict:
    """The committed ten-year averages (python -m fieldops.weather --normals), or {} if absent."""
    from .weather import load_normals

    return load_normals()


def _project_open(day: date, left: float, th: dict, normals: dict):
    """First date the remaining degree-days are used up, if every later day has its normal temperatures."""
    total = 0.0
    for n in range(1, 181):
        d = day + timedelta(days=n)
        tmin, tmax = normals[(d.month, d.day)]
        total += daily_dd(tmin, tmax, th["dd_base_f"], th["dd_upper_f"])
        if total >= left:
            return d.isoformat()
    return None


def _estimate_open(day: date, left: float, th: dict, normals: dict, dd_by_day: dict):
    """Estimated date the window opens, as an ISO string, or None.

    With normals it adds each later day's average temperatures; without them it repeats the last week's
    rate, which runs weeks late in spring because the weather is still warming.
    """
    if normals:
        return _project_open(day, left, th, normals)
    recent = [dd_by_day[day - timedelta(days=k)] for k in range(7) if day - timedelta(days=k) in dd_by_day]
    rate = sum(recent) / len(recent)
    return (day + timedelta(days=math.ceil(left / rate))).isoformat() if rate > 0 else None


def _status(tl: dict, i: int, block_id: str) -> dict:
    """One block's state at the end of day i, with the dates its milestones happened."""
    day, state = tl["days"][i], tl["days"][i]["blocks"][block_id]
    so_far = {"days": tl["days"][: i + 1]}
    return {
        "species": tl["farm"]["pest"], "block": block_id, "as_of": day["date"], "status": state["status"],
        "biofix_date": state["biofix_date"], "dd": state["dd_since_biofix"],
        "confirmed_on": event_date(so_far, block_id, "biofix"),
        "opened_on": event_date(so_far, block_id, "spray_window_open"),
        "closed_on": event_date(so_far, block_id, "spray_window_close"),
        "projected_open": state.get("projected_open"),
    }


# What to do about a block, by status. Deterministic: the agent phrases these, it never invents them.
def next_step(state: dict, cfg: dict) -> dict:
    """One ranked, plain-language action for a block. A pure function of decide's own verdict."""
    status, dd = state["status"], state["dd"]
    as_of = date.fromisoformat(state["as_of"])

    if status == "spray_window":
        closes = cfg["spray_close_dd"]
        return {"urgency": 0, "level": "act", "headline": "Spray now",
                "detail": f"Window opened {state['opened_on']} at {dd:.0f} DD; "
                          f"{closes - dd:.0f} degree-days of window left before it closes."}

    if status == "window_closed":
        return {"urgency": 4, "level": "done", "headline": "Window closed",
                "detail": f"Closed {state['closed_on']} at {cfg['spray_close_dd']} DD. Nothing to "
                          f"do for this generation; keep trapping for the next flight."}

    if status == "accumulating":
        need = cfg["spray_open_dd"] - dd
        when = state.get("projected_open")
        days = (date.fromisoformat(when) - as_of).days if when else None
        soon = days is not None and days <= 3
        return {"urgency": 1 if soon else 2,
                "level": "prepare" if soon else "watch",
                "headline": "Get ready to spray" if soon else "Accumulating",
                "detail": f"{dd:.0f} of {cfg['spray_open_dd']} degree-days since biofix "
                          f"{state['biofix_date']}, {need:.0f} to go"
                          + (f"; window expected around {when}." if when else ".")}

    return {"urgency": 3, "level": "watch", "headline": "No biofix yet",
            "detail": f"No sustained catch yet. The clock starts at {cfg['biofix_min_count']} "
                      f"moths on {cfg['biofix_consecutive_checks']} consecutive days."}


def evaluate(records: list, weather: dict, as_of: date, config: dict = None, normals: dict = None) -> list:
    """Status of every block using only data up to as_of. normals as in build_timeline."""
    seen = [r for r in records if r["timestamp"][:10] <= as_of.isoformat()]
    try:
        tl = build_timeline(seen, weather, config, normals)
    except ValueError:
        return []  # nothing counted yet
    return [_status(tl, len(tl["days"]) - 1, b["id"]) for b in tl["blocks"]]


def replay(records: list, weather: dict, config: dict = None, normals: dict = None) -> list:
    """One event per milestone, in date order, each carrying that block's status on the day."""
    tl = build_timeline(records, weather, config, normals)
    return [
        dict(_status(tl, i, e["block_id"]), event=EVENT_NAMES[e["type"]])
        for i, day in enumerate(tl["days"]) for e in day["events"]
    ]


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

    def inputs(counts):
        records = [{"trap_id": "block-x-01", "timestamp": f"{start + timedelta(days=i):%Y-%m-%d}T14:00:00Z",
                    "species": "codling_moth", "count": n} for i, n in enumerate(counts)]
        weather = {start + timedelta(days=i): (50, 70) for i in range(len(counts))}  # 10 DD every day
        return records, weather

    def run(counts):
        return build_timeline(*inputs(counts), cfg)

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

    # The agent's views read the same timeline: May 6 is biofix day, and the estimate matches what happens.
    records, weather = inputs([0, 5, 0, 0, 3, 4, 0, 0, 0])
    assert evaluate(records[:1], weather, date(2026, 5, 1), cfg, normals={})[0]["status"] == "watching"
    s = evaluate(records, weather, date(2026, 5, 6), cfg, normals={})[0]  # {} = the last-week-rate fallback
    assert (s["status"], s["biofix_date"], s["dd"], s["opened_on"]) == ("accumulating", "2026-05-05", 10, None)
    assert s["projected_open"] == "2026-05-08"  # 15 DD to go at 10 a day, rounded up to 2 days

    # With normals, each later day adds its own average temperatures: a flat 19 DD (50 / 88) a day is 1 day for 15 DD.
    hot = {(m, d): (50.0, 95.0) for m in range(1, 13) for d in range(1, 32)}
    assert evaluate(records, weather, date(2026, 5, 6), cfg, normals=hot)[0]["projected_open"] == "2026-05-07"
    cool = {(m, d): (40.0, 60.0) for m in range(1, 13) for d in range(1, 32)}  # (60 + 50) / 2 - 50 = 5 DD a day
    assert evaluate(records, weather, date(2026, 5, 6), cfg, normals=cool)[0]["projected_open"] == "2026-05-09"
    assert evaluate(records, weather, date(2026, 5, 4), cfg, normals=hot)[0]["projected_open"] is None  # no biofix yet

    # The same estimate rides in the timeline, only while a block is accumulating.
    tl_hot = build_timeline(records, weather, cfg, normals=hot)
    est = lambda i: tl_hot["days"][i]["blocks"]["block-x"]["projected_open"]
    assert est(4) is None  # May 5: run not complete yet, still watching
    assert est(5) == "2026-05-07"  # May 6: biofix confirmed, 15 DD to go at 19 a day
    assert est(7) is None  # May 8: window open, nothing left to estimate
    validate(tl_hot)

    assert [e["event"] for e in replay(records, weather, cfg)] == [
        "biofix_confirmed", "spray_window_open", "spray_window_closed"]


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
