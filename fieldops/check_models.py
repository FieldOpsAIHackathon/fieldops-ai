"""Smoke test: do the local LLM and VLM load and answer? Run this first on the GB10.

    python -m fieldops.check_models

Needs an OpenAI-compatible server (vLLM, Ollama, llama.cpp). The LLM endpoint and model are the ones in
agent.py. The vision model defaults to the same server and model; override with FIELDOPS_VLM_URL (the
base, ending in /v1) and FIELDOPS_VLM_MODEL if it is a different one.
The first call can be slow because the server loads the model.
"""
import base64
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

from . import agent

ROOT = Path(__file__).resolve().parent.parent
IMAGE = ROOT / "data" / "traps" / "trap_03_codling012.jpg"
LLM_BASE = agent.LLM_URL.rsplit("/chat/completions", 1)[0]
VLM_URL = os.environ.get("FIELDOPS_VLM_URL", LLM_BASE)
VLM_MODEL = os.environ.get("FIELDOPS_VLM_MODEL", agent.LLM_MODEL)
TIMEOUT_S = 180


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.load(resp)


def _chat(base: str, model: str, content) -> str:
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps({"model": model, "temperature": 0, "max_tokens": 300,
                         "chat_template_kwargs": {"enable_thinking": False},
                         "messages": [{"role": "user", "content": content}]}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        return json.load(resp)["choices"][0]["message"]["content"].strip()


def _run(label: str, fn) -> bool:
    start = time.time()
    try:
        reply = fn()
    except Exception as e:
        print(f"FAIL  {label}: {type(e).__name__}: {e}")
        return False
    print(f"ok    {label} ({time.time() - start:.1f}s): {reply[:300]}")
    return True


def _truth() -> str:
    manifest = json.loads((IMAGE.parent / "manifest.json").read_text())
    entry = next(m for m in manifest if m["file"] == IMAGE.name)
    return ", ".join(f"{c['species']}={c['count']}" for c in entry["counts"])


def main() -> int:
    for label, url in (("LLM", LLM_BASE), ("VLM", VLM_URL)):
        try:
            ids = [m["id"] for m in _get(f"{url}/models")["data"]]
            print(f"{label} server {url} lists: {', '.join(ids) or '(none)'}")
        except Exception as e:
            print(f"{label} server {url} not reachable ({type(e).__name__}); model names unknown")

    image = "data:image/jpeg;base64," + base64.b64encode(IMAGE.read_bytes()).decode()
    vision_prompt = [
        {"type": "text", "text": "This is a sticky insect trap. Count the moths by species and reply "
         'with JSON only, like {"codling_moth": 3, "oriental_fruit_moth": 1}.'},
        {"type": "image_url", "image_url": {"url": image}},
    ]
    print(f"\nground truth for {IMAGE.name}: {_truth()}\n")

    results = [
        _run(f"LLM {agent.LLM_MODEL}", lambda: _chat(LLM_BASE, agent.LLM_MODEL, "Reply with the single word: ready")),
        _run(f"VLM {VLM_MODEL}", lambda: _chat(VLM_URL, VLM_MODEL, vision_prompt)),
    ]
    print("\nboth models answered" if all(results) else "\nat least one model did not answer")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
