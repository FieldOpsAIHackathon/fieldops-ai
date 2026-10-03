"""Vision lane: count pests on a trap photo with the trained YOLO26 detector.

    bash fieldops/yolo/run.sh serve                       # HTTP service on 127.0.0.1:8767 (GPU container)
    curl --data-binary @card.jpg "localhost:8767/count?trap_id=block-c-04"
    bash fieldops/yolo/run.sh vision data/traps/*.jpg     # one-off, prints contract records

Deterministic: fixed weights and threshold. Every photo is saved with an annotated copy under
data/vision/, and its records are appended to data/vision/counts.jsonl. Records go into the store
only with --to-store, so a stray demo photo cannot move decide's spray dates.
"""
import argparse
import io
import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from PIL import Image

from .yolo.count import PESTS, count_result, load_model, records

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "vision"
PORT = 8767
MAX_BYTES = 15 * 1024 * 1024


def count_image(model, image: Image.Image, trap_id: str, to_store: bool = False) -> dict:
    # An uploaded photo is a point-in-time reading, so the upload is its origination date. We never
    # backdate one into the season: decide spans only days it has weather for, so a stored upload
    # cannot stretch or break the replay.
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    counts, annotated = count_result(model, image)
    recs = records(counts, trap_id, stamp)

    OUT.mkdir(parents=True, exist_ok=True)
    name = f"{stamp.replace(':', '')}_{trap_id}"
    image.convert("RGB").save(OUT / f"{name}.jpg", quality=90)
    annotated.save(OUT / f"{name}_boxes.jpg", quality=90)
    with (OUT / "counts.jsonl").open("a") as f:
        for r in recs:
            f.write(json.dumps(r) + "\n")
    if to_store:
        from . import store

        store.add(recs)

    total = sum(counts.values())
    summary = ", ".join(f"{n} {s.replace('_', ' ')}" for s, n in counts.items() if n) or "no pests"
    return {
        "trap_id": trap_id, "timestamp": stamp, "counts": counts, "total_pests": total,
        "summary": summary, "records": recs, "annotated_image": str((OUT / f"{name}_boxes.jpg").relative_to(ROOT)),
        "stored": to_store,
    }


def serve(model, to_store: bool) -> None:
    class Handler(BaseHTTPRequestHandler):
        def _reply(self, code, payload):
            body = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            url = urlparse(self.path)
            if url.path != "/count":
                return self._reply(404, {"error": "POST /count with the image as the body"})
            size = int(self.headers.get("Content-Length", 0))
            if not 0 < size <= MAX_BYTES:
                return self._reply(400, {"error": f"image must be 1 byte to {MAX_BYTES // 2**20} MB"})
            trap_id = parse_qs(url.query).get("trap_id", ["unknown-trap"])[0][:64]
            try:
                image = Image.open(io.BytesIO(self.rfile.read(size)))
                image.load()
            except Exception:
                return self._reply(400, {"error": "body is not an image"})
            self._reply(200, count_image(model, image, trap_id, to_store))

    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"vision service on http://127.0.0.1:{PORT}/count  (pests: {', '.join(PESTS)})", flush=True)
    server.serve_forever()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("images", nargs="*", type=Path)
    p.add_argument("--serve", action="store_true")
    p.add_argument("--weights", default="/work/models/fieldops-yolo26s-v2.pt")
    p.add_argument("--trap-id", default="block-c-04")
    p.add_argument("--to-store", action="store_true", help="also add the records to the SQLite store")
    args = p.parse_args()

    model = load_model(args.weights)
    if args.serve:
        return serve(model, args.to_store)
    for path in args.images:
        print(json.dumps(count_image(model, Image.open(path), args.trap_id, args.to_store), indent=1))


if __name__ == "__main__":
    main()
