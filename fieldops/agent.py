"""Agent layer: tools over decide's output, plus the local LLM that phrases it. It never decides.

    python -m fieldops.agent --replay                 # paced season replay, phone buzzes on milestones
    python -m fieldops.agent --replay --dry-run       # same, alerts logged instead of sent
    python -m fieldops.agent --ask "Why Thursday?"    # grounded answer from the current replay day
    python -m fieldops.agent --status                 # what the tools return right now

The same tools are served to OpenClaw (in the NemoClaw sandbox) by fieldops.api.
The LLM is Qwen on the GB10's local vLLM server; if it is down, alerts fall back to a template.
"""
import argparse
import json
import time
import urllib.request
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

from . import alert, decide
from . import species as species_cfg

LLM_URL = "http://127.0.0.1:8000/v1/chat/completions"
LLM_MODEL = "nvidia/Qwen3.6-35B-A3B-NVFP4"
STATE = Path(__file__).resolve().parent.parent / "data" / "replay_state.json"
DEFAULT_SPECIES = "codling_moth"
ALERT_EVENTS = ("biofix_confirmed", "spray_window_open")


# --- data ------------------------------------------------------------------------------------

@lru_cache(maxsize=None)
def _season():
    from .season import load_csv

    return load_csv()


def season_days() -> list:
    records, _ = _season()
    return sorted({date.fromisoformat(r["timestamp"][:10]) for r in records})


def current_day() -> date:
    """The replay clock: the day the replay last reached, else the end of the season."""
    try:
        return date.fromisoformat(json.loads(STATE.read_text())["as_of"])
    except (OSError, ValueError, KeyError):
        return season_days()[-1]


def set_current_day(day: date) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"as_of": day.isoformat()}))


def _as_of(as_of) -> date:
    return date.fromisoformat(as_of) if isinstance(as_of, str) else (as_of or current_day())


def _block(name):
    """Accept "c", "C", "block c" or "block-c"."""
    if not name:
        return None
    name = name.strip().lower().replace(" ", "-")
    return name if name.startswith("block-") else f"block-{name}"


def _weekday(iso):
    return f"{date.fromisoformat(iso):%A %b %-d}" if iso else None


# --- tools (also served to OpenClaw by fieldops.api) -----------------------------------------

def get_counts(block=None, species=DEFAULT_SPECIES, days=14, as_of=None) -> dict:
    """Daily trap-catch totals per block for the last `days` days up to as_of."""
    end = _as_of(as_of)
    start = end - timedelta(days=int(days) - 1)
    block = _block(block)
    totals = {}
    for r in _season()[0]:
        day = date.fromisoformat(r["timestamp"][:10])
        b = decide.block_of(r["trap_id"])
        if r["species"] == species and start <= day <= end and (block is None or b == block):
            key = (b, day.isoformat())
            totals[key] = totals.get(key, 0) + r["count"]
    rows = [{"block": b, "date": d, "count": n} for (b, d), n in sorted(totals.items())]
    return {"as_of": end.isoformat(), "species": species, "daily_counts": rows}


def get_degree_days(block=None, species=DEFAULT_SPECIES, as_of=None) -> dict:
    """decide's verdict per block: biofix, degree-days since biofix, spray window, thresholds."""
    end = _as_of(as_of)
    records, weather = _season()
    cfg = species_cfg.load()["species"][species]
    block = _block(block)
    blocks = []
    for s in decide.evaluate(records, weather, end):
        if s["species"] == species and (block is None or s["block"] == block):
            s = dict(s)
            for key in ("biofix_date", "confirmed_on", "opened_on", "closed_on", "projected_open"):
                s[key + "_weekday"] = _weekday(s[key])
            blocks.append(s)
    return {
        "as_of": end.isoformat(),
        "species": species,
        "rules": {**cfg["biofix"], **cfg["degree_days"], "method": "daily average, horizontal cutoffs"},
        "blocks": blocks,
    }


def get_status(as_of=None) -> dict:
    """Everything the agent needs to explain the current situation, plus the last alert sent."""
    status = get_degree_days(as_of=as_of)
    status["last_alerts"] = alert.last(3)
    return status


def send_alert(text: str) -> dict:
    return {"delivered": alert.send(text)}


# --- LLM -------------------------------------------------------------------------------------

def _llm(system: str, user: str, max_tokens: int = 200) -> str:
    body = json.dumps({
        "model": LLM_MODEL,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "max_tokens": max_tokens,
        "temperature": 0.3,
        "chat_template_kwargs": {"enable_thinking": False},
    }).encode()
    req = urllib.request.Request(LLM_URL, body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["choices"][0]["message"]["content"].strip()


ALERT_SYSTEM = (
    "You write SMS alerts for an apple grower. One or two short sentences, plain words, no emoji, "
    "no greeting, no advice beyond what the facts say. Use only the facts given; never invent a "
    "number or date. Refer to the block by its letter, e.g. 'block C'."
)


def _template(d: dict) -> str:
    block = f"block {d['block'].split('-')[-1].upper()}"
    if d["event"] == "biofix_confirmed":
        text = f"Biofix reached on {block}: codling moth flight confirmed, degree-day clock started."
        if d.get("projected_open"):
            text += f" Spray window expected to open {_weekday(d['projected_open'])}."
        return text
    if d["event"] == "spray_window_open":
        return f"Spray window is open on {block}: {d['dd']:.0f} degree-days since biofix. Spray now."
    return f"Spray window closed on {block} at {d['dd']:.0f} degree-days."


def write_alert(decision: dict) -> str:
    """Turn one decide event into a grower-facing sentence. Falls back to a template."""
    facts = {
        "event": decision["event"],
        "block": decision["block"],
        "pest": species_cfg.load()["species"][decision["species"]]["display"],
        "today": _weekday(decision["as_of"]),
        "biofix_date": _weekday(decision["biofix_date"]),
        "degree_days_since_biofix": decision["dd"],
        "spray_window_expected_to_open": _weekday(decision.get("projected_open")),
    }
    try:
        text = _llm(ALERT_SYSTEM, json.dumps(facts), max_tokens=120)
        if text and len(text) < 400:
            return text
    except Exception as e:
        print(f"[llm unavailable ({type(e).__name__}); using template]")
    return _template(decision)


def answer(question: str, as_of=None) -> str:
    """Answer a grower's question from decide's numbers. The LLM explains; it does not compute."""
    context = get_status(as_of)
    context["recent_counts"] = get_counts(days=10, as_of=as_of)["daily_counts"]
    system = (
        "You are FieldOps, a pest-monitoring assistant for an apple orchard. Answer in 2-4 short "
        "sentences using only the JSON facts provided. Spray timing comes from degree-days "
        "accumulated since biofix (first sustained moth catch); quote the actual numbers and dates. "
        "If the facts don't answer the question, say so."
    )
    return _llm(system, f"Facts:\n{json.dumps(context)}\n\nQuestion: {question}", max_tokens=300)


# --- replay ----------------------------------------------------------------------------------

def replay(seconds: float = 30, block=None, dry_run: bool = False) -> None:
    """Walk the season at demo speed; send an alert the day each milestone happens.

    By default alerts follow the first block to reach each milestone, so the phone buzzes
    twice (biofix, then spray window) rather than once per block.
    """
    records, weather = _season()
    events = [e for e in decide.replay(records, weather) if e["event"] in ALERT_EVENTS]
    block = _block(block)
    chosen, seen = [], set()
    for e in events:
        if (block and e["block"] == block) or (not block and e["event"] not in seen):
            chosen.append(e)
            seen.add(e["event"])

    print("Writing alerts with the local LLM...")
    queued = {}
    for e in chosen:
        queued.setdefault(e["as_of"], []).append(write_alert(e))
        print(f"  {e['as_of']} {e['block']} {e['event']}: {queued[e['as_of']][-1]}")

    days = season_days()
    step = seconds / len(days)
    print(f"\nReplaying {len(days)} days in {seconds:.0f}s...")
    for day in days:
        set_current_day(day)
        for text in queued.get(day.isoformat(), []):
            print(f"{day}  ", end="")
            alert.send(text, dry_run=dry_run)
        time.sleep(step)
    print("Replay done.")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--replay", action="store_true")
    p.add_argument("--seconds", type=float, default=30)
    p.add_argument("--block", help="alert on this block only, e.g. c")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--ask")
    p.add_argument("--as-of", help="YYYY-MM-DD; also moves the replay clock")
    p.add_argument("--status", action="store_true")
    args = p.parse_args()

    if args.as_of:
        set_current_day(date.fromisoformat(args.as_of))
    if args.replay:
        replay(args.seconds, args.block, args.dry_run)
    if args.ask:
        print(answer(args.ask))
    if args.status:
        print(json.dumps(get_status(), indent=1))


if __name__ == "__main__":
    main()
