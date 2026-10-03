"""Phone alert over Telegram. Never raises: a failed send is logged, not fatal to the demo.

    python -m fieldops.alert "Biofix reached on block C."      # send one message
    python -m fieldops.alert --dry-run "text"                   # log only

Credentials come from the environment, or from ~/.config/fieldops.env (KEY=VALUE lines),
which lives outside the repo so the token is never committed:
    FIELDOPS_TELEGRAM_TOKEN=123456:ABC...
    FIELDOPS_TELEGRAM_CHAT_ID=123456789
"""
import argparse
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ENV_FILE = Path.home() / ".config" / "fieldops.env"
LOG = Path(__file__).resolve().parent.parent / "data" / "alerts.jsonl"


def _settings() -> dict:
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                env[key.strip()] = value.strip().strip('"').strip("'")
    env.update({k: v for k, v in os.environ.items() if k.startswith("FIELDOPS_")})
    return env


def _log(entry: dict) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def last(n: int = 1) -> list:
    """The most recent n logged alerts, newest last."""
    if not LOG.exists():
        return []
    return [json.loads(line) for line in LOG.read_text().splitlines()[-n:] if line.strip()]


def send(text: str, dry_run: bool = False) -> bool:
    """Send text to the grower's phone. Returns True if Telegram accepted it."""
    entry = {"sent_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "text": text}
    cfg = _settings()
    token, chat = cfg.get("FIELDOPS_TELEGRAM_TOKEN"), cfg.get("FIELDOPS_TELEGRAM_CHAT_ID")
    if dry_run or not (token and chat):
        entry["delivered"] = False
        entry["reason"] = "dry run" if dry_run else f"no Telegram credentials (set them in {ENV_FILE})"
        _log(entry)
        print(f"[alert not sent: {entry['reason']}] {text}")
        return False

    body = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()
    try:
        with urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", body, timeout=10) as r:
            entry["delivered"] = json.load(r).get("ok", False)
    except Exception as e:  # offline, blocked, bad token: log it and keep the demo running
        entry["delivered"], entry["reason"] = False, type(e).__name__
    _log(entry)
    print(f"[alert {'sent' if entry['delivered'] else 'FAILED: ' + entry.get('reason', '?')}] {text}")
    return entry["delivered"]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("text")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    send(args.text, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
