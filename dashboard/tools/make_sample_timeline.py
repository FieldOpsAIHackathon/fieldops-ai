"""Deterministic sample season for the dashboard (stand-in until decide --replay exists).

Writes dashboard/data/sample_timeline.json and sample_timeline.js. Shape and decision rules
are pinned in dashboard/TIMELINE_CONTRACT.md. Standard library only.
"""
import json
import math
import random
from datetime import date, timedelta
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
START, END = date(2026, 4, 15), date(2026, 8, 31)

FARM = {"name": "Nashoba Ridge Orchard", "location": "Bolton, MA", "crop": "apple",
        "pest": "codling_moth", "pest_name": "Codling moth", "season": 2026}
TH = {"biofix_min_count": 2, "biofix_consecutive_checks": 2, "dd_base_f": 50,
      "dd_upper_f": 88, "spray_open_dd": 250, "spray_close_dd": 350}

# id letter, variety, acres, pressure (relative flight size), flight shift in days
BLOCK_DEFS = [("a", "Honeycrisp", 4.2, 1.00, 0), ("b", "McIntosh", 5.6, 0.90, 1),
              ("c", "Gala", 3.4, 1.40, -4), ("d", "Cortland", 6.0, 1.10, 2),
              ("e", "Macoun", 2.5, 0.85, 1), ("f", "Fuji", 3.1, 0.70, 3)]
TRAP_WEIGHTS = [0.8, 1.0, 1.2]

# Piecewise-linear climatology anchors: (date, tmin, tmax)
CLIMATE = [(date(2026, 4, 15), 38, 57), (date(2026, 5, 15), 47, 69), (date(2026, 6, 15), 56, 77),
           (date(2026, 7, 20), 64, 85), (date(2026, 8, 31), 56, 78)]
# (first day, last day, delta F) for cold snaps and the July heat wave
SPELLS = [(date(2026, 4, 21), date(2026, 4, 24), -9), (date(2026, 5, 4), date(2026, 5, 7), -8),
          (date(2026, 7, 9), date(2026, 7, 12), 9)]


def daterange():
    d = START
    while d <= END:
        yield d
        d += timedelta(days=1)


def climate(d):
    for (d0, lo0, hi0), (d1, lo1, hi1) in zip(CLIMATE, CLIMATE[1:]):
        if d0 <= d <= d1:
            f = (d - d0).days / (d1 - d0).days
            return lo0 + f * (lo1 - lo0), hi0 + f * (hi1 - hi0)


def make_temps(seed):
    rng = random.Random(seed)
    out = {}
    for d in daterange():
        lo, hi = climate(d)
        shift = rng.gauss(0, 3.5) + sum(x for a, b, x in SPELLS if a <= d <= b)
        tmin = round(lo + shift * 0.8 + rng.gauss(0, 1.5))
        tmax = round(hi + shift + rng.gauss(0, 2))
        out[d] = (tmin, max(tmax, tmin + 6))
    return out


def poisson(rng, lam):
    if lam <= 0:
        return 0
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def flight(d, shift):
    """Per-trap mean catch at pressure 1: bimodal, first flight ~Jun 1, second ~Aug 3."""
    n = (d - date(2026, 1, 1)).days - shift
    g = lambda peak_date, sigma, amp: amp * math.exp(-((n - (peak_date - date(2026, 1, 1)).days) ** 2) / (2 * sigma ** 2))
    v = g(date(2026, 6, 1), 9, 7.0) + g(date(2026, 8, 3), 8, 3.2)
    return v if v > 0.12 else 0.0   # nothing before the flight really starts


def make_counts():
    rng = random.Random(2026)
    counts = {}
    for letter, _, _, pressure, shift in BLOCK_DEFS:
        for i, w in enumerate(TRAP_WEIGHTS, 1):
            for d in daterange():
                lam = flight(d, shift) * pressure * w
                n = poisson(rng, lam) if lam else int(rng.random() < 0.03)  # stray 1 pre-flight
                counts[(f"block-{letter}-0{i}", d)] = n
    return counts


def degree_days(tmin, tmax):
    avg = (min(tmax, TH["dd_upper_f"]) + max(tmin, TH["dd_base_f"])) / 2
    return max(0.0, avg - TH["dd_base_f"])


def build(temps, counts):
    blocks = []
    for k, (letter, variety, acres, _, _) in enumerate(BLOCK_DEFS):
        blocks.append({"id": f"block-{letter}", "name": f"Block {letter.upper()}", "variety": variety,
                       "acres": acres, "traps": [f"block-{letter}-0{i}" for i in (1, 2, 3)],
                       "col": k % 3, "row": k // 3})
    st = {b["id"]: {"run": 0, "run_start": None, "biofix": None, "dd": 0.0, "status": "watching"} for b in blocks}
    prev = {b["id"]: 0 for b in blocks}
    days = []
    for d in daterange():
        tmin, tmax = temps[d]
        ddt = degree_days(tmin, tmax)
        day = {"date": d.isoformat(), "tmin_f": tmin, "tmax_f": tmax, "dd_today": round(ddt, 1),
               "counts": {}, "traps": {}, "blocks": {}, "events": []}
        for b in blocks:
            bid, s = b["id"], st[b["id"]]
            tc = {t: counts[(t, d)] for t in b["traps"]}
            c = sum(tc.values())
            day["traps"].update(tc)
            day["counts"][bid] = c
            events = []
            if s["biofix"] is None:
                if c >= TH["biofix_min_count"]:
                    if s["run"] == 0:
                        s["run_start"] = d
                    s["run"] += 1
                else:
                    s["run"] = 0
                if s["run"] >= TH["biofix_consecutive_checks"]:
                    s["biofix"], s["status"] = s["run_start"], "accumulating"
                    events.append(("biofix", f"Biofix set on {b['name']}",
                                   f"Sustained codling moth catch on {b['name']}: {c} moths today after {prev[bid]} yesterday. "
                                   "Degree-day clock starts now."))
            else:
                s["dd"] += ddt
                if s["status"] == "accumulating" and s["dd"] >= TH["spray_open_dd"]:
                    s["status"] = "spray_window"
                    events.append(("spray_window_open", f"Spray window open on {b['name']}",
                                   f"{b['name']} has reached {s['dd']:.0f} degree-days since biofix with {c} moths in traps today. "
                                   "Time to spray for codling moth."))
                if s["status"] == "spray_window" and s["dd"] >= TH["spray_close_dd"]:
                    s["status"] = "window_closed"
                    events.append(("spray_window_close", f"Spray window closed on {b['name']}",
                                   f"{b['name']} is at {s['dd']:.0f} degree-days since biofix with {c} moths today. "
                                   "The first-generation spray window has passed."))
            prev[bid] = c
            day["blocks"][bid] = {"status": s["status"], "biofix_date": s["biofix"].isoformat() if s["biofix"] else None,
                                  "dd_since_biofix": round(s["dd"], 1)}
            day["events"] += [{"block_id": bid, "type": t, "title": ti, "message": m} for t, ti, m in events]
        days.append(day)
    return {"farm": FARM, "thresholds": TH, "blocks": blocks, "days": days}


def event_date(tl, bid, typ):
    for day in tl["days"]:
        if any(e["block_id"] == bid and e["type"] == typ for e in day["events"]):
            return day["date"]


def check(tl):
    ds = [date.fromisoformat(x["date"]) for x in tl["days"]]
    assert ds[0] == START and ds[-1] == END
    assert all((b - a).days == 1 for a, b in zip(ds, ds[1:])), "gap in days"
    for b in tl["blocks"]:
        bid = b["id"]
        assert all(isinstance(x["counts"][bid], int) and x["counts"][bid] >= 0 for x in tl["days"])
        dds = [x["blocks"][bid]["dd_since_biofix"] for x in tl["days"]]
        assert all(a <= c for a, c in zip(dds, dds[1:])), f"dd decreased in {bid}"
        for typ in ("biofix", "spray_window_open"):
            assert event_date(tl, bid, typ) < "2026-07-15", f"{bid} {typ} late"
        assert event_date(tl, bid, "biofix") > "2026-05-05", f"{bid} early biofix"
    assert all(x["tmin_f"] < x["tmax_f"] and isinstance(x["tmin_f"], int) for x in tl["days"])
    assert all("—" not in e["message"] + e["title"] for x in tl["days"] for e in x["events"])
    assert json.loads(json.dumps(tl)) == tl, "JSON round trip"


def main():
    counts = make_counts()
    # Nudge the temperature seed (counts untouched) until Block C's window opens on a Thursday.
    for seed in range(1, 400):
        tl = build(make_temps(seed), counts)
        if date.fromisoformat(event_date(tl, "block-c", "spray_window_open")).weekday() == 3:
            break
    check(tl)
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "sample_timeline.json").write_text(json.dumps(tl, indent=1) + "\n")
    js = "window.FIELDOPS_TIMELINE = " + json.dumps(tl, separators=(",", ":")) + ";\n"
    assert js.startswith("window.FIELDOPS_TIMELINE = ")
    (DATA / "sample_timeline.js").write_text(js)
    print(f"temperature seed {seed}")
    print(f"{'block':8}{'biofix':12}{'open':12}{'close':12}{'peak':6}peak date")
    for b in tl["blocks"]:
        peak, pd = max((x["counts"][b["id"]], x["date"]) for x in tl["days"])
        print(f"{b['name']:8}{event_date(tl, b['id'], 'biofix'):12}{event_date(tl, b['id'], 'spray_window_open'):12}"
              f"{event_date(tl, b['id'], 'spray_window_close') or '-':12}{peak:<6}{pd}")
    co = event_date(tl, "block-c", "spray_window_open")
    print("Block C window opens", co, date.fromisoformat(co).strftime("%A"))


if __name__ == "__main__":
    main()
