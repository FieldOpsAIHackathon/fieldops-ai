"""HTTP tool server for the OpenClaw agent in the NemoClaw sandbox. Standard library only.

    python -m fieldops.api

Listens on 127.0.0.1 and on the sandbox bridge (host.openshell.internal), never on the venue
network. Inside the sandbox:
    curl -s http://172.18.0.1:8765/status
    curl -s "http://172.18.0.1:8765/counts?block=c&days=14"
    curl -s "http://172.18.0.1:8765/degree_days?block=c"
    curl -s -X POST http://172.18.0.1:8765/alert -d '{"text": "..."}'

The dashboard on the host also POSTs {date, block_id, type} to /trigger when a banner fires; that route
is not in the sandbox policy, so OpenClaw cannot reach it.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import agent

PORT = 8765
HOSTS = ("127.0.0.1", "172.18.0.1")  # loopback + the OpenShell docker bridge (host.openshell.internal)
# A dashboard opened from disk sends Origin "null" (some browsers "file://"). Anything else is another site.
PAGE_ORIGINS = {"null", "file://"}
MAX_TRIGGER_BODY = 1024

GET_ROUTES = {
    "/status": lambda q: agent.get_status(q.get("as_of")),
    "/counts": lambda q: agent.get_counts(q.get("block"), q.get("species", agent.DEFAULT_SPECIES),
                                         int(q.get("days", 14)), q.get("as_of")),
    "/degree_days": lambda q: agent.get_degree_days(q.get("block"), q.get("species", agent.DEFAULT_SPECIES),
                                                   q.get("as_of")),
}


class Handler(BaseHTTPRequestHandler):
    def _reply(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlparse(self.path)
        route = GET_ROUTES.get(url.path)
        if not route:
            return self._reply(404, {"error": f"unknown path; try {sorted(GET_ROUTES)} or POST /alert"})
        query = {k: v[0] for k, v in parse_qs(url.query).items()}
        try:
            self._reply(200, route(query))
        except (KeyError, ValueError) as e:
            self._reply(400, {"error": str(e)})

    def do_POST(self):
        path = urlparse(self.path).path
        origin = self.headers.get("Origin")
        if path == "/trigger":
            return self._trigger(origin)
        if path != "/alert":
            return self._reply(404, {"error": "only POST /alert"})
        if origin is not None:  # browsers always send Origin, curl in the sandbox does not
            return self._reply(403, {"error": "/alert is not for browsers"})
        try:
            text = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))["text"].strip()
        except (ValueError, KeyError, AttributeError):
            return self._reply(400, {"error": 'body must be {"text": "..."}'})
        if not text or len(text) > 500:
            return self._reply(400, {"error": "text must be 1-500 characters"})
        self._reply(200, agent.send_alert(text))

    def _trigger(self, origin) -> None:
        """The dashboard names an event it just showed; the text comes from decide and the agent, never from here."""
        if origin is not None and origin not in PAGE_ORIGINS:
            return self._reply(403, {"error": "origin not allowed"})
        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 0 < length <= MAX_TRIGGER_BODY:
                raise ValueError("bad length")
            req = json.loads(self.rfile.read(length))
            day, block, kind = req["date"], req["block_id"], req["type"]
            event = agent.find_event(day, block, kind)
        except (ValueError, KeyError, TypeError):
            return self._reply(400, {"error": 'body must be {"date", "block_id", "type"}'})
        if event is None:
            return self._reply(404, {"error": "no such alertable event"})
        self._reply(202, {"queued": event["event"]})  # answer now; the LLM can take seconds
        threading.Thread(target=agent.deliver_event, args=(event,), daemon=True).start()


def main() -> None:
    servers = []
    for host in HOSTS:
        try:
            servers.append(ThreadingHTTPServer((host, PORT), Handler))
            print(f"FieldOps tools on http://{host}:{PORT}")
        except OSError as e:
            print(f"skipping {host}: {e}")
    for s in servers[1:]:
        threading.Thread(target=s.serve_forever, daemon=True).start()
    servers[0].serve_forever()


if __name__ == "__main__":
    main()
