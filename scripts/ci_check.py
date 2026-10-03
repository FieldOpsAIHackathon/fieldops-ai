"""Offline CI checks. Run from any directory: python3 scripts/ci_check.py.

Uses temporary SQLite/files and a loopback HTTP server. No model calls or alerts.
Requires Node only for JavaScript syntax checks; no Python packages required.
"""
import ast
import json
import subprocess
import sys
import tempfile
import threading
import urllib.request
from html.parser import HTMLParser
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fieldops import agent, api, decide, season, store  # noqa: E402


class Assets(HTMLParser):
    def __init__(self, page):
        super().__init__()
        self.page, self.inline, self.scripts = page, None, []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script" and not attrs.get("src") and attrs.get("type", "") in ("", "text/javascript", "module"):
            self.inline = []
        key = "href" if tag == "link" else "src"
        if tag not in ("script", "img", "link") or not attrs.get(key):
            return
        url = urlsplit(attrs[key])
        if url.scheme == "data":
            return
        assert not url.scheme and not url.netloc, f"external asset: {self.page}: {attrs[key]}"
        assert not url.path.startswith("/"), f"file:// incompatible asset: {attrs[key]}"
        target = (self.page.parent / unquote(url.path)).resolve()
        assert target.is_relative_to(ROOT) and target.is_file(), f"missing local asset: {target}"

    def handle_data(self, data):
        if self.inline is not None:
            self.inline.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self.inline is not None:
            self.scripts.append("".join(self.inline))
            self.inline = None


def check_assets(scratch):
    scripts = list((ROOT / "dashboard").rglob("*.js")) + list((ROOT / "pitch").rglob("*.js"))
    for page in [ROOT / "dashboard/index.html", ROOT / "pitch/index.html"]:
        parser = Assets(page)
        parser.feed(page.read_text())
        for i, script in enumerate(parser.scripts):
            target = scratch / f"{page.parent.name}-{i}.mjs"
            target.write_text(script)
            scripts.append(target)
    for script in scripts:
        subprocess.run(["node", "--check", str(script)], check=True, capture_output=True, text=True)
    print(f"PASS local HTML assets and {len(scripts)} JavaScript syntax checks")


def main():
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    for relative in filter(None, tracked):
        path = ROOT / relative
        if path.suffix == ".py":
            ast.parse(path.read_text(), filename=relative)
        assert not (path.name.startswith(".env") or path.suffix in {".db", ".sqlite", ".sqlite3", ".pem", ".key"}), f"runtime/secret file tracked: {relative}"
        assert relative not in {"data/alerts.jsonl", "data/replay_state.json", "dashboard/data/live.json"}, f"runtime file tracked: {relative}"
    print("PASS Python syntax and tracked runtime-file exclusions")
    decide.selftest()
    print("PASS decision engine self-tests")
    records, weather = season.load_csv()
    direct = decide.build_timeline(records, weather)
    decide.validate(direct)
    with tempfile.TemporaryDirectory(prefix="fieldops-ci-") as tmp:
        scratch = Path(tmp)
        db = scratch / "fieldops.db"
        store.load_season(season.CSV_PATH, db)
        first = store.read(db)
        store.load_season(season.CSV_PATH, db)
        assert store.read(db) == first, "season re-ingest changed store contents"
        assert len(first[0]) == len(records) and first[1] == weather
        assert decide.build_timeline(*first) == direct, "store replay differs from CSV replay"
        print(f"PASS SQLite idempotency and CSV/store parity ({len(records)} counts)")
        decide.write_timeline(direct, scratch)
        for stem in ("timeline", "sample_timeline"):
            path = ROOT / "dashboard/data" / stem
            timeline = json.loads(path.with_suffix(".json").read_text())
            decide.validate(timeline)
            js = path.with_suffix(".js").read_text()
            prefix = "window.FIELDOPS_TIMELINE = "
            assert js.startswith(prefix) and js.endswith(";\n")
            assert json.loads(js[len(prefix):-2]) == timeline, f"{stem} JS/JSON differ"
        for name in ("timeline.json", "timeline.js"):
            assert (scratch / name).read_bytes() == (ROOT / "dashboard/data" / name).read_bytes(), (
                f"stale {name}: run python3 -m fieldops.decide --csv --replay and commit both files")
        print(f"PASS committed replay matches engine ({len(direct['days'])} days, {len(direct['blocks'])} blocks)")
        # Serve only in this process on an ephemeral loopback port. Patch data reads
        # so CI never opens the user's real store or alert log.
        with patch.object(agent, "_season", return_value=first), patch.object(agent.alert, "last", return_value=[]):
            server = ThreadingHTTPServer(("127.0.0.1", 0), api.Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                event_day = next(d for d in direct["days"] if any(e["type"] == "spray_window_open" for e in d["events"]))
                url = f"http://127.0.0.1:{server.server_port}/status?as_of={event_day['date']}"
                with urllib.request.urlopen(url, timeout=5) as response:
                    status = json.load(response)
                assert status["as_of"] == event_day["date"]
                assert {s["block"] for s in status["blocks"]} == set(event_day["blocks"])
                for state in status["blocks"]:
                    expected = event_day["blocks"][state["block"]]
                    assert state["status"] == expected["status"] and state["dd"] == expected["dd_since_biofix"]
            finally:
                server.shutdown()
                server.server_close()
                thread.join()
        print("PASS HTTP /status -> agent -> decide agrees with spray-day timeline")
        check_assets(scratch)


if __name__ == "__main__":
    main()
