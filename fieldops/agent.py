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
import re
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
    """The store if it holds data, else the committed seed CSV: the same rule decide uses."""
    from . import store
    from .season import load_csv

    records, weather = store.read()
    return (records, weather) if records and weather else load_csv()


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


def _approx(iso):
    """An estimated date, shown without a weekday because the estimate is good to a few days."""
    return f"{date.fromisoformat(iso):%b} {date.fromisoformat(iso).day}" if iso else None


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
            for key in ("biofix_date", "confirmed_on", "opened_on", "closed_on"):
                s[key + "_weekday"] = _weekday(s[key])
            s["projected_open_approx"] = _approx(s["projected_open"])
            blocks.append(s)
    return {
        "as_of": end.isoformat(),
        "species": species,
        "rules": {**{k: cfg[k] for k in decide.THRESHOLD_KEYS}, "method": "daily average, horizontal cutoffs"},
        "projection_note": "projected_open is an estimate: today's degree-days plus the 2016-2025 average "
                           "temperatures for each later date. Typically within a few days; not a forecast.",
        "blocks": blocks,
    }


def get_status(as_of=None) -> dict:
    """Everything the agent needs to explain the current situation, plus the last alert sent."""
    status = get_degree_days(as_of=as_of)
    status["last_alerts"] = alert.last(3)
    return status


def get_farm(as_of=None, species=DEFAULT_SPECIES) -> dict:
    """Mode 2: the whole farm, crispest form. Blocks ranked by urgency, one action each.

    Deliberately small: a phone reply should fit on a screen, so this carries the headline and the
    one number behind it, not the full verdict. Call /degree_days for a block's full reasoning.
    """
    full = get_degree_days(None, species, as_of)
    cfg = species_cfg.load()["species"][species]
    names = {b["id"]: b["name"] for b in species_cfg.load()["blocks"]}

    blocks = []
    for st in full["blocks"]:
        step = decide.next_step(st, cfg)
        blocks.append({
            "block": st["block"],
            "name": names.get(st["block"], st["block"]),
            "status": st["status"],
            "level": step["level"],
            "urgency": step["urgency"],
            "dd": round(st["dd"]),
            "headline": step["headline"],
            "detail": step["detail"],
            "line": f"{names.get(st['block'], st['block'])}: {step['headline']}. {step['detail']}",
        })
    blocks.sort(key=lambda b: (b["urgency"], b["block"]))

    acting = [b for b in blocks if b["level"] == "act"]
    prepping = [b for b in blocks if b["level"] == "prepare"]
    if acting:
        many = len(acting) > 1
        head = f"{len(acting)} block{'s' if many else ''} {'need' if many else 'needs'} spraying " \
               f"now: " + ", ".join(b["name"] for b in acting) + "."
    elif prepping:
        head = "Nothing to spray today. Coming up within three days: " \
               + ", ".join(b["name"] for b in prepping) + "."
    else:
        head = "Nothing to spray today and nothing due in the next three days."

    return {
        "as_of": full["as_of"],
        "species": species,
        "pest_name": cfg["display_name"],
        "summary": head,
        "needs_action": [b["block"] for b in acting],
        "blocks": blocks,
        "note": full.get("projection_note"),
    }


def get_block_report(block, as_of=None, species=DEFAULT_SPECIES, counts: dict = None) -> dict:
    """Mode 1: one block's state and next step, optionally alongside counts just read from a photo."""
    full = get_degree_days(block, species, as_of)
    if not full["blocks"]:
        return {"error": f"no such block: {block}"}
    st = full["blocks"][0]
    cfg = species_cfg.load()["species"][species]
    names = {b["id"]: b["name"] for b in species_cfg.load()["blocks"]}
    step = decide.next_step(st, cfg)
    name = names.get(st["block"], st["block"])

    out = {
        "as_of": full["as_of"], "block": st["block"], "name": name,
        "pest_name": cfg["display_name"], "status": st["status"], "level": step["level"],
        "dd": round(st["dd"]), "biofix_date": st["biofix_date"],
        "spray_opens_at_dd": cfg["spray_open_dd"],
        "projected_open": st.get("projected_open"),
        "headline": step["headline"], "detail": step["detail"],
        "line": f"{name}: {step['headline']}. {step['detail']}",
    }
    if counts:
        out["photo_counts"] = counts
    return out


def send_alert(text: str) -> dict:
    return {"delivered": alert.send(text)}


def find_event(day: str, block: str, kind: str):
    """The decide event for (date, block, kind) if it is one we alert on, else None. kind is a timeline
    type ("biofix", "spray_window_open") or an agent event name."""
    name = decide.EVENT_NAMES.get(kind, kind)
    if name not in ALERT_EVENTS:
        return None
    records, weather = _season()
    return next((e for e in decide.replay(records, weather)
                 if e["as_of"] == day and e["block"] == block and e["event"] == name), None)


def deliver_event(event: dict, dry_run: bool = False) -> None:
    """Phrase one event, move the replay clock to its day (so the tools answer as of then), and send it."""
    set_current_day(date.fromisoformat(event["as_of"]))
    text = write_alert(event)
    print(f"[agent] {event['as_of']} {event['block']} {event['event']}: {text}")
    alert.send(text, dry_run=dry_run)


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
    "number or date. Refer to the block by its letter, e.g. 'block C'. If the facts include "
    "spray_window_expected_around, say the window is expected to open 'around' that date; it is an "
    "estimate, so do not give it a weekday."
)


def _template(d: dict) -> str:
    block = f"block {d['block'].split('-')[-1].upper()}"
    if d["event"] == "biofix_confirmed":
        text = f"Biofix reached on {block}: codling moth flight confirmed, degree-day clock started."
        if d.get("projected_open"):
            text += f" Spray window expected to open around {_approx(d['projected_open'])}."
        return text
    if d["event"] == "spray_window_open":
        return f"Spray window is open on {block}: {d['dd']:.0f} degree-days since biofix. Spray now."
    return f"Spray window closed on {block} at {d['dd']:.0f} degree-days."


def _numbers(text: str) -> set:
    return set(re.findall(r"\d+", text))


# Capitalised only, so the verb "may" is not read as the month.
_DATE_WORDS = re.compile(
    r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|Mon|Tue|Wed|Thu|Fri|Sat|Sun|"
    r"January|February|March|April|May|June|July|August|September|October|November|December|"
    r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b")


def _date_words(text: str) -> set:
    return set(_DATE_WORDS.findall(text))


_WEEKDAY_DATE = re.compile(
    r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),? [A-Z][a-z]+\.? \d{1,2}\b")


def _weekday_dates_stated(text: str, fact_text: str) -> bool:
    """Every 'Thursday Jun 4' in the text must appear exactly so in the facts, or the weekday may be wrong."""
    return all(m.replace(",", "").replace(".", "") in fact_text for m in _WEEKDAY_DATE.findall(text))


def write_alert(decision: dict) -> str:
    """Turn one decide event into a grower-facing sentence. Falls back to a template.

    The model's text is used only if every number, weekday and month name in it appears in the facts it
    was given, and every weekday-with-date appears there with the same pairing.
    """
    facts = {
        "event": decision["event"],
        "block": decision["block"],
        "pest": species_cfg.load()["species"][decision["species"]]["display_name"],
        "today": _weekday(decision["as_of"]),
        "biofix_date": _weekday(decision["biofix_date"]),
        "degree_days_since_biofix": round(decision["dd"]),
    }
    if decision["event"] == "biofix_confirmed" and decision.get("projected_open"):
        facts["spray_window_expected_around"] = _approx(decision["projected_open"])
    fact_text = json.dumps(facts)
    try:
        text = _llm(ALERT_SYSTEM, fact_text, max_tokens=120)
        if (text and len(text) < 400 and _numbers(text) <= _numbers(fact_text)
                and _date_words(text) <= _date_words(fact_text) and _weekday_dates_stated(text, fact_text)):
            return text
        print("[llm text failed the checks; using template]")
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
