"""Shared helpers for the VMC data pipeline. Standard library only."""

from __future__ import annotations

import csv
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "src" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

USER_AGENT = "vmc-growth-tracker/0.1 (+https://github.com/shashemi23/vmc-growth-tracker)"


def http(url: str, *, params: dict | None = None, data: dict | None = None,
         retries: int = 3, timeout: int = 120) -> bytes:
    """GET (params) or form-POST (data) with simple retry/backoff."""
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=body, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as err:  # noqa: BLE001 - retry on any network error
            last_err = err
            time.sleep(2 ** attempt * 2)
    raise RuntimeError(f"Request failed after {retries} attempts: {url}") from last_err


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    rows = sorted(rows, key=lambda r: tuple(str(r.get(f, "")) for f in fieldnames))
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
