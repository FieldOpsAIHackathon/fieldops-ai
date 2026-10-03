"""Fetch real daily temperatures from Open-Meteo once, while online, and save them for offline replay.

    python -m fieldops.weather                      # Bolton, MA over the season window -> data/weather.csv
    python -m fieldops.weather --lat 42.4 --lon -71.6 --start 2026-04-15 --end 2026-08-31
    python -m fieldops.weather --normals            # 2016-2025 average temps per calendar day -> data/climate_normals.csv

Open-Meteo needs no API key. Run it with the network on, commit the CSV, and nothing reaches the
internet at demo time. The season fetch does not touch season.csv or the dashboard timeline: it prints
how the replay's key dates would move if these temperatures were used.

The normals are the forecast decide uses to estimate when a spray window will open. They come from
earlier years only, so an estimate made on May 9 never sees May 10.
"""
import argparse
import csv
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
WEATHER_CSV = Path(__file__).resolve().parent.parent / "data" / "weather.csv"
NORMALS_CSV = Path(__file__).resolve().parent.parent / "data" / "climate_normals.csv"
NORMALS_YEARS = (2016, 2025)
BOLTON_MA = (42.43, -71.60)
TIMEOUT_S = 20


def fetch(lat: float, lon: float, start: str, end: str) -> dict:
    """Return {date: (tmin_f, tmax_f)} for every day in [start, end], or raise ValueError."""
    query = urllib.parse.urlencode({
        "latitude": lat, "longitude": lon, "start_date": start, "end_date": end,
        "daily": "temperature_2m_max,temperature_2m_min", "temperature_unit": "fahrenheit",
        "timezone": "America/New_York",
    })
    try:
        with urllib.request.urlopen(f"{ARCHIVE_URL}?{query}", timeout=TIMEOUT_S) as resp:
            body = json.load(resp)
    except urllib.error.HTTPError as e:  # the server answered, so the network is fine
        try:
            reason = json.load(e).get("reason", e.reason)
        except ValueError:
            reason = e.reason
        raise ValueError(f"Open-Meteo rejected the request: {reason}") from None
    if "daily" not in body:
        raise ValueError(f"Open-Meteo returned no data: {body.get('reason', body)}")

    daily = body["daily"]
    weather = {}
    for day, tmax, tmin in zip(daily["time"], daily["temperature_2m_max"], daily["temperature_2m_min"]):
        if tmax is None or tmin is None:
            raise ValueError(f"missing temperature on {day}; the archive lags a few days behind today")
        if tmax < tmin:
            raise ValueError(f"max below min on {day}")
        weather[date.fromisoformat(day)] = (round(tmin, 1), round(tmax, 1))
    expected = (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
    if len(weather) != expected:
        raise ValueError(f"expected {expected} days, got {len(weather)}")
    return weather


def write_csv(weather: dict, path: Path = WEATHER_CSV) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "tmin_f", "tmax_f"])
        for day, (tmin, tmax) in sorted(weather.items()):
            w.writerow([day.isoformat(), tmin, tmax])


def load_csv(path: Path = WEATHER_CSV) -> dict:
    """Same shape decide takes: {date: (tmin_f, tmax_f)}."""
    with open(path, newline="") as f:
        return {date.fromisoformat(r["date"]): (float(r["tmin_f"]), float(r["tmax_f"])) for r in csv.DictReader(f)}


def fetch_normals(lat: float, lon: float, first_year: int, last_year: int) -> dict:
    """Average tmin/tmax for each (month, day) over the given years: {(month, day): (tmin_f, tmax_f)}."""
    history = fetch(lat, lon, f"{first_year}-01-01", f"{last_year}-12-31")
    by_day = {}
    for day, pair in history.items():
        by_day.setdefault((day.month, day.day), []).append(pair)
    return {
        key: (round(sum(p[0] for p in pairs) / len(pairs), 1), round(sum(p[1] for p in pairs) / len(pairs), 1))
        for key, pairs in sorted(by_day.items())
    }


def write_normals(normals: dict, path: Path = NORMALS_CSV) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["month", "day", "tmin_f", "tmax_f"])
        for (month, day), (tmin, tmax) in sorted(normals.items()):
            w.writerow([month, day, tmin, tmax])


def load_normals(path: Path = NORMALS_CSV) -> dict:
    """{(month, day): (tmin_f, tmax_f)}, or {} if the file has not been fetched."""
    if not Path(path).exists():
        return {}
    with open(path, newline="") as f:
        return {(int(r["month"]), int(r["day"])): (float(r["tmin_f"]), float(r["tmax_f"])) for r in csv.DictReader(f)}


def compare(real: dict) -> None:
    """Show Block C's milestones under the synthetic temperatures and under these."""
    from . import decide
    from .season import load_csv as load_season

    records, synthetic = load_season()
    print(f"\n{'':22}{'synthetic (committed)':24}{'real (Open-Meteo)'}")
    results = {}
    for name, weather in (("synthetic", synthetic), ("real", real)):
        tl = decide.build_timeline(records, weather)
        results[name] = {t: decide.event_date(tl, "block-c", t) for t in ("biofix", "spray_window_open", "spray_window_close")}
    for label, key in (("Block C biofix set", "biofix"), ("spray window opens", "spray_window_open"),
                       ("spray window closes", "spray_window_close")):
        print(f"{label:22}{str(results['synthetic'][key]):24}{results['real'][key]}")
    opens = results["real"]["spray_window_open"]
    if opens:
        print(f"\nWith real temperatures Block C's window opens on a {date.fromisoformat(opens):%A}.")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--lat", type=float, default=BOLTON_MA[0])
    p.add_argument("--lon", type=float, default=BOLTON_MA[1])
    p.add_argument("--start")
    p.add_argument("--end")
    p.add_argument("--out", type=Path, default=WEATHER_CSV)
    p.add_argument("--no-compare", action="store_true")
    p.add_argument("--normals", action="store_true",
                   help=f"fetch {NORMALS_YEARS[0]}-{NORMALS_YEARS[1]} daily averages instead of one season")
    args = p.parse_args()

    if args.normals:
        out = args.out if args.out != WEATHER_CSV else NORMALS_CSV
        try:
            normals = fetch_normals(args.lat, args.lon, *NORMALS_YEARS)
        except (OSError, ValueError) as e:
            print(f"could not fetch weather: {e}", file=sys.stderr)
            return 1
        write_normals(normals, out)
        print(f"wrote normals for {len(normals)} calendar days ({NORMALS_YEARS[0]}-{NORMALS_YEARS[1]}) to {out}")
        return 0

    from .season import END, START

    start, end = args.start or START.isoformat(), args.end or END.isoformat()
    try:
        weather = fetch(args.lat, args.lon, start, end)
    except (OSError, ValueError) as e:
        print(f"could not fetch weather: {e}", file=sys.stderr)
        return 1
    write_csv(weather, args.out)
    print(f"wrote {len(weather)} days ({start} to {end}) to {args.out}")
    if not args.no_compare and (start, end) == (START.isoformat(), END.isoformat()):
        compare(weather)
    return 0


if __name__ == "__main__":
    sys.exit(main())
