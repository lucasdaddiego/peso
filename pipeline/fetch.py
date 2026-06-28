"""Download the source series into data/raw/ (idempotent).

Three datos.gob.ar time-series (two CPI segments + the official FX) as JSON, and the Bluelytics
historical CSV for the informal ("blue") dollar. The datos.gob.ar API caps a response at 5000
rows, so the daily FX series is paged. Network lives only here; everything downstream parses the
saved snapshots, so the rest of the pipeline (and the whole test suite) runs offline.
"""

from __future__ import annotations

import json
import sys
import urllib.request

from . import config

_HEADERS = {"User-Agent": "Mozilla/5.0 (peso data pipeline)"}
_PAGE = 5000  # datos.gob.ar hard cap per request


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def fetch_series(series_id: str) -> list[list]:
    """Fetch a full datos.gob.ar series as [["YYYY-MM-DD", value], ...], paging past the 5000 cap."""
    rows: list[list] = []
    start = 0
    while True:
        url = f"{config.SERIES_API}?ids={series_id}&format=json&limit={_PAGE}&start={start}"
        payload = json.loads(_get(url))
        data = payload.get("data", [])
        rows.extend(data)
        if len(data) < _PAGE:
            break
        start += _PAGE
    return rows


def fetch() -> None:
    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    for series_id in (config.IPC_GBA_ID, config.IPC_SANLUIS_ID, config.IPC_NACIONAL_ID, config.FX_OFICIAL_ID):
        dest = config.RAW_DIR / f"{series_id}.json"
        print(f"[fetch] {series_id} …")
        rows = fetch_series(series_id)
        dest.write_text(json.dumps(rows), encoding="utf-8")
        print(f"[fetch]   {len(rows):,} rows → {dest.name}")

    print("[fetch] bluelytics evolution.csv …")
    blue = config.RAW_DIR / "bluelytics_evolution.csv"
    blue.write_bytes(_get(config.BLUELYTICS_CSV))
    print(f"[fetch]   → {blue.name} ({blue.stat().st_size:,} bytes)")


if __name__ == "__main__":
    try:
        fetch()
    except Exception as exc:  # noqa: BLE001
        print(f"[fetch] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
