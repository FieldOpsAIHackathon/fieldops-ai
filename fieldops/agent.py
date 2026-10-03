"""Phrase a decision for the grower with a local LLM. It never computes anything.

    python -m fieldops.agent            # show the facts, the fallback text, and the LLM text
    python -m fieldops.agent --send     # ...and send the result through fieldops.alert

Talks to any local OpenAI-compatible server (Ollama, vLLM, llama.cpp). Configure with
FIELDOPS_LLM_URL (default http://localhost:11434/v1) and FIELDOPS_LLM_MODEL.
If the model is down, slow, or invents a number, the timeline's own templated message is used.
"""
import argparse
import json
import os
import re
import urllib.request
from datetime import date
from pathlib import Path

from . import alert

TIMELINE = Path(__file__).resolve().parent.parent / "dashboard" / "data" / "timeline.json"
LLM_URL = os.environ.get("FIELDOPS_LLM_URL", "http://localhost:11434/v1")
LLM_MODEL = os.environ.get("FIELDOPS_LLM_MODEL", "llama3.1")
TIMEOUT_S = 20
MAX_CHARS = 280

PROMPT = (
    "You write one text message to an apple grower. Use one or two short plain sentences, no "
    "markdown, no emoji. Use ONLY the facts below, copy dates and numbers exactly, and do not "
    "calculate anything. Say what happened and, if it is a spray window, that it is time to act.\n\n"
    "Facts:\n{facts}"
)


def _day(d: str) -> str:
    return f"{date.fromisoformat(d):%A %B} {date.fromisoformat(d).day}"


def facts(tl: dict, day: str, event: dict) -> dict:
    """Everything the LLM may mention, taken from the timeline. Weekdays are precomputed here."""
    entry = next(x for x in tl["days"] if x["date"] == day)
    block = entry["blocks"][event["block_id"]]
    name = next(b["name"] for b in tl["blocks"] if b["id"] == event["block_id"])
    out = {
        "event": event["type"],
        "block": name,
        "pest": tl["farm"]["pest_name"],
        "today": _day(day),
        "moths_today": entry["counts"][event["block_id"]],
        "biofix_date": _day(block["biofix_date"]) if block["biofix_date"] else None,
        "degree_days_since_biofix": round(block["dd_since_biofix"]),
        "spray_opens_at_degree_days": tl["thresholds"]["spray_open_dd"],
    }
    return {k: v for k, v in out.items() if v is not None}


def _numbers(text: str) -> set:
    return set(re.findall(r"\d+", text))


def acceptable(text: str, fact_text: str) -> bool:
    """Reject empty, long, or number-inventing output; digits in the answer must appear in the facts."""
    return bool(text) and len(text) <= MAX_CHARS and _numbers(text) <= _numbers(fact_text)


def ask_llm(prompt: str) -> str:
    req = urllib.request.Request(
        f"{LLM_URL}/chat/completions",
        data=json.dumps({"model": LLM_MODEL, "temperature": 0.2,
                         "messages": [{"role": "user", "content": prompt}]}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        return json.load(resp)["choices"][0]["message"]["content"].strip()


def write_alert(tl: dict, day: str, event: dict) -> str:
    """LLM wording if it passes the checks, otherwise the timeline's templated message."""
    fact_text = json.dumps(facts(tl, day, event), indent=1)
    try:
        text = ask_llm(PROMPT.format(facts=fact_text))
    except Exception as e:
        print(f"[agent: LLM unavailable ({type(e).__name__}), using template]")
        return event["message"]
    if not acceptable(text, fact_text):
        print("[agent: LLM text failed the checks, using template]")
        return event["message"]
    return text


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--timeline", type=Path, default=TIMELINE)
    p.add_argument("--block", default="block-c")
    p.add_argument("--event", default="spray_window_open")
    p.add_argument("--send", action="store_true")
    args = p.parse_args()

    tl = json.loads(args.timeline.read_text())
    day, event = next(
        (x["date"], e) for x in tl["days"] for e in x["events"]
        if e["block_id"] == args.block and e["type"] == args.event
    )
    print("facts:", json.dumps(facts(tl, day, event)))
    print("template:", event["message"])
    text = write_alert(tl, day, event)
    print("alert:", text)
    if args.send:
        print("sent" if alert.send(text) else "not sent")


if __name__ == "__main__":
    main()
