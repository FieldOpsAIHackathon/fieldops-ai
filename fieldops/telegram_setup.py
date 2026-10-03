"""Set up the Telegram phone alert on this machine: check the bot token, find your chat, save both, send a test.

    python -m fieldops.telegram_setup

First create a bot: message @BotFather in Telegram, send /newbot, and copy the token. Then open your new
bot and press Start. The token is typed hidden and never printed. It is saved to ~/.config/fieldops.env,
readable only by you and outside the repo, which is where fieldops.alert looks for it.
"""
import getpass
import json
import os
import sys
import urllib.error
import urllib.request

from . import alert

API = "https://api.telegram.org"
TIMEOUT_S = 10
TOKEN_KEY, CHAT_KEY = "FIELDOPS_TELEGRAM_TOKEN", "FIELDOPS_TELEGRAM_CHAT_ID"


def _call(token: str, method: str) -> dict:
    """The token is part of the URL, so errors report a status or a type, never the address."""
    try:
        with urllib.request.urlopen(f"{API}/bot{token}/{method}", timeout=TIMEOUT_S) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Telegram answered {e.code} to {method}") from None
    except Exception as e:
        raise RuntimeError(f"could not reach Telegram ({type(e).__name__})") from None


def bot_username(token: str) -> str:
    try:
        return _call(token, "getMe")["result"]["username"]
    except RuntimeError as e:
        if "401" in str(e) or "404" in str(e):
            raise RuntimeError("Telegram rejected that token; copy it again from @BotFather") from None
        raise


def chats_seen(token: str) -> dict:
    """{chat_id: label} for everyone who has messaged the bot."""
    found = {}
    for update in _call(token, "getUpdates").get("result", []):
        chat = update.get("message", {}).get("chat")
        if chat:
            found[chat["id"]] = chat.get("title") or " ".join(
                filter(None, [chat.get("first_name"), chat.get("last_name")])) or chat.get("username") or "unnamed"
    return found


def read_env(path=None) -> dict:
    path = path or alert.ENV_FILE
    if not path.exists():
        return {}
    pairs = (line.split("=", 1) for line in path.read_text().splitlines() if "=" in line and not line.lstrip().startswith("#"))
    return {k.strip(): v.strip().strip('"').strip("'") for k, v in pairs}


def save_env(updates: dict, path=None) -> None:
    """Merge updates into the env file, keeping other keys, written owner-only and replaced atomically."""
    path = path or alert.ENV_FILE
    merged = {**read_env(path), **updates}
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.writelines(f"{k}={v}\n" for k, v in merged.items())
    os.replace(tmp, path)


def choose_chats(chats: dict) -> list:
    ids = list(chats)
    if len(ids) == 1:
        print(f"Found one chat: {chats[ids[0]]} ({ids[0]})")
        return ids
    for n, cid in enumerate(ids, 1):
        print(f"  {n}. {chats[cid]} ({cid})")
    picked = input("Which chats should get alerts? Numbers separated by commas, Enter for all: ").strip()
    if not picked:
        return ids
    return [ids[int(n) - 1] for n in picked.replace(" ", "").split(",") if n.isdigit() and 0 < int(n) <= len(ids)]


def main() -> int:
    if not sys.stdin.isatty():
        print("Run this in a terminal: it asks for the token with hidden input.", file=sys.stderr)
        return 2

    saved = read_env().get(TOKEN_KEY)
    prompt = "Bot token (Enter to keep the saved one): " if saved else "Bot token from @BotFather: "
    token = getpass.getpass(prompt).strip() or saved
    if not token:
        print("No token given.", file=sys.stderr)
        return 1
    try:
        name = bot_username(token)
        print(f"Token accepted for @{name}.")
        chats = chats_seen(token)
        while not chats:
            print(f"\nNo chats yet. Open Telegram, find @{name}, press Start and send it any message.")
            if input("Press Enter to look again, or q to quit: ").strip().lower() == "q":
                return 1
            chats = chats_seen(token)
        chosen = choose_chats(chats)
    except RuntimeError as e:
        print(f"Stopped: {e}", file=sys.stderr)
        return 1
    if not chosen:
        print("No chats chosen.", file=sys.stderr)
        return 1

    save_env({TOKEN_KEY: token, CHAT_KEY: ",".join(str(c) for c in chosen)})
    print(f"Saved to {alert.ENV_FILE} (only you can read it).")
    if os.environ.get(TOKEN_KEY) or os.environ.get(CHAT_KEY):
        print("Note: FIELDOPS_TELEGRAM_* is also set in your environment, and it takes priority over that file.")
    print("Sending a test message...")
    return 0 if alert.send("FieldOps test: if this buzzes, the phone path works.") else 1


if __name__ == "__main__":
    sys.exit(main())
