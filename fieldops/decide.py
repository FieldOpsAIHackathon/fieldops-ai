"""Biofix, degree-days and spray window. Deterministic: no LLM, no randomness.

    python -m fieldops.decide        # self-test, then replay data/season.csv

Thresholds come from species.json. Counts are grouped by block (trap_id minus its last "-NN").
"""
import math
from collections import defaultdict
from datetime import date, timedelta

from . import species as species_cfg

MILESTONES = (
    ("biofix_confirmed", "confirmed_on"),
    ("spray_window_open", "opened_on"),
    ("spray_window_closed", "closed_on"),
)


def block_of(trap_id: str) -> str:
    return trap_id.rsplit("-", 1)[0]


def daily_dd(tmax: float, tmin: float, lower: float, upper: float) -> float:
    """Simple average with horizontal cutoffs at the lower and upper thresholds."""
    clamp = lambda t: min(max(t, lower), upper)
    return (clamp(tmax) + clamp(tmin)) / 2 - lower


def find_biofix(daily_totals: list, min_count: int, consecutive: int):
    """daily_totals: sorted (date, count). Return (first day of run, day confirmed) or None.

    A missing day breaks the run; a day under min_count breaks it too.
    """
    run = []
    for day, n in daily_totals:
        if n < min_count:
            run = []
        elif run and day == run[-1] + timedelta(days=1):
            run.append(day)
        else:
            run = [day]
        if len(run) >= consecutive:
            return run[0], day
    return None


def _recent_dd_rate(weather: dict, as_of: date, lower: float, upper: float) -> float:
    rates = [
        daily_dd(*weather[d], lower, upper)
        for d in (as_of - timedelta(days=i) for i in range(7)) if d in weather
    ]
    return sum(rates) / len(rates) if rates else 0.0


def _block_status(sp: str, block: str, by_day: dict, weather: dict, as_of: date, cfg: dict) -> dict:
    rule, dd = cfg["biofix"], cfg["degree_days"]
    out = {
        "species": sp, "block": block, "as_of": as_of.isoformat(), "status": "no_biofix",
        "biofix_date": None, "confirmed_on": None, "dd": 0.0,
        "opened_on": None, "closed_on": None, "projected_open": None,
    }
    hit = find_biofix(sorted(by_day.items()), rule["min_count"], rule["consecutive_days"])
    if not hit:
        return out

    start, confirmed = hit
    total, day = 0.0, start
    while day <= as_of:
        if day not in weather:
            raise ValueError(f"no weather for {day}; cannot accumulate degree-days")
        total += daily_dd(*weather[day], dd["lower_f"], dd["upper_f"])
        if out["opened_on"] is None and total >= dd["spray_open"]:
            out["opened_on"] = day.isoformat()
        if out["closed_on"] is None and total >= dd["spray_close"]:
            out["closed_on"] = day.isoformat()
        day += timedelta(days=1)

    out.update(biofix_date=start.isoformat(), confirmed_on=confirmed.isoformat(), dd=round(total, 1))
    if out["closed_on"]:
        out["status"] = "window_closed"
    elif out["opened_on"]:
        out["status"] = "spray_window"
    else:
        out["status"] = "biofix"
        rate = _recent_dd_rate(weather, as_of, dd["lower_f"], dd["upper_f"])
        if rate > 0:
            days_left = math.ceil((dd["spray_open"] - total) / rate)
            out["projected_open"] = (as_of + timedelta(days=days_left)).isoformat()
    return out


def evaluate(records: list, weather: dict, as_of: date, config: dict = None) -> list:
    """One status dict per (species, block) that has a biofix rule, using data up to as_of.

    records: contract dicts. weather: {date: (tmax_f, tmin_f)}.
    """
    config = config or species_cfg.load()
    totals = defaultdict(lambda: defaultdict(int))
    for r in records:
        day = date.fromisoformat(r["timestamp"][:10])
        if day <= as_of:
            totals[(r["species"], block_of(r["trap_id"]))][day] += r["count"]

    results = []
    for (sp, block), by_day in sorted(totals.items()):
        cfg = config["species"].get(sp, {})
        if "biofix" in cfg:
            results.append(_block_status(sp, block, by_day, weather, as_of, cfg))
    return results


def replay(records: list, weather: dict, config: dict = None) -> list:
    """Walk the season day by day and return an event for each milestone, in date order."""
    days = sorted({date.fromisoformat(r["timestamp"][:10]) for r in records})
    events = []
    for day in days:
        for status in evaluate(records, weather, day, config):
            for name, key in MILESTONES:
                if status[key] == day.isoformat():
                    events.append(dict(status, event=name))
    return events


def describe(e: dict) -> str:
    text = f"{e['as_of']}  {e['block']:<8} {e['species']}  {e['event']:<19} biofix {e['biofix_date']}  DD {e['dd']}"
    if e["event"] == "biofix_confirmed" and e["projected_open"]:
        d = date.fromisoformat(e["projected_open"])
        text += f"  spray window projected {d:%A} {d}"
    return text


def selftest() -> None:
    assert daily_dd(70, 50, 50, 88) == 10
    assert daily_dd(45, 40, 50, 88) == 0
    assert daily_dd(95, 60, 50, 88) == 24  # highs above 88 are capped

    d = lambda n: date(2026, 5, n)
    assert find_biofix([(d(1), 6), (d(2), 0), (d(3), 0)], 3, 3) is None  # one blip is not sustained
    assert find_biofix([(d(1), 3), (d(2), 3), (d(4), 3), (d(5), 3)], 3, 3) is None  # gap breaks the run
    assert find_biofix([(d(1), 1), (d(2), 3), (d(3), 4), (d(4), 5)], 3, 3) == (d(2), d(4))


def main() -> None:
    from .season import load_csv

    selftest()
    print("selftest ok\n")
    records, weather = load_csv()
    for e in replay(records, weather):
        print(describe(e))


if __name__ == "__main__":
    main()
