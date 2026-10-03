"""Local listener the dashboard calls when a spray banner fires. It phrases the alert and texts the phone.

    python -m fieldops.trigger          # listen on 127.0.0.1:8765
    curl -X POST localhost:8765/alert -d '{"date":"2026-06-04","block_id":"block-c","type":"spray_window_open"}'

Loopback only. A request just names an event; the message text comes from the timeline and the
agent, never from the request, so this cannot be used to send arbitrary text.
"""
import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import agent, alert

MAX_BODY = 1024
# A page opened from disk sends Origin "null" (some browsers send "file://" or nothing).
ALLOWED_ORIGINS = {None, "null", "file://"}


def find_event(tl: dict, day: str, block_id: str, event_type: str):
    for entry in tl["days"]:
        if entry["date"] == day:
            for e in entry["events"]:
                if e["block_id"] == block_id and e["type"] == event_type:
                    return e
    return None


def deliver(tl: dict, day: str, event: dict) -> None:
    text = agent.write_alert(tl, day, event)
    print("[trigger] alert:", text)
    print("[trigger]", "sent" if alert.send(text) else "not sent")


class Handler(BaseHTTPRequestHandler):
    timeline_path = agent.TIMELINE

    def _reply(self, code: int, body: bytes = b"") -> None:
        self.send_response(code)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._reply(204)

    def do_GET(self):
        self._reply(200, b"ok") if self.path == "/health" else self._reply(404)

    def do_POST(self):
        if self.path != "/alert":
            return self._reply(404)
        if self.headers.get("Origin") not in ALLOWED_ORIGINS:
            return self._reply(403)
        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 0 < length <= MAX_BODY:
                raise ValueError("bad length")
            req = json.loads(self.rfile.read(length))
            tl = json.loads(self.timeline_path.read_text())
            event = find_event(tl, req["date"], req["block_id"], req["type"])
        except (ValueError, KeyError, TypeError, OSError):
            return self._reply(400)
        if event is None:
            return self._reply(404)
        self._reply(202)  # answer now; the LLM can take seconds
        threading.Thread(target=deliver, args=(tl, req["date"], event), daemon=True).start()

    def log_message(self, fmt, *args):
        print("[trigger]", fmt % args)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--timeline", type=Path, default=agent.TIMELINE)
    args = p.parse_args()

    Handler.timeline_path = args.timeline
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"[trigger] listening on http://127.0.0.1:{args.port}  (timeline: {args.timeline})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
