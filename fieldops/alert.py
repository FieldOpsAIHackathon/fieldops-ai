"""Phone alert. Telegram if configured, console otherwise; never raises.

    python -m fieldops.alert "Biofix reached on Block C."

Set FIELDOPS_TG_TOKEN and FIELDOPS_TG_CHAT_ID to send to a phone. Without them the text is printed,
so a replay never dies because the alert channel is down.
"""
import json
import os
import sys
import urllib.request

TIMEOUT_S = 8


def send(text: str) -> bool:
    """Return True only if Telegram accepted the message."""
    token, chat_id = os.environ.get("FIELDOPS_TG_TOKEN"), os.environ.get("FIELDOPS_TG_CHAT_ID")
    if not (token and chat_id):
        print(f"[alert, not sent: FIELDOPS_TG_TOKEN / FIELDOPS_TG_CHAT_ID unset] {text}")
        return False

    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=json.dumps({"chat_id": chat_id, "text": text}).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            return resp.status == 200
    except Exception as e:  # the token is in the URL, so report only the exception type
        print(f"[alert failed: {type(e).__name__}] {text}")
        return False


if __name__ == "__main__":
    message = " ".join(sys.argv[1:]) or "FieldOps test alert"
    print("sent" if send(message) else "not sent")
