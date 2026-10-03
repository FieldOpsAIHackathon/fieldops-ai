"""Per-crop pest list and thresholds, read from species.json."""
import json
from functools import lru_cache
from pathlib import Path

PATH = Path(__file__).with_name("species.json")


@lru_cache(maxsize=None)
def load(path: Path = PATH) -> dict:
    return json.loads(Path(path).read_text())


def normalize(name: str) -> str:
    return name.strip().lower().replace("-", "_").replace(" ", "_")
