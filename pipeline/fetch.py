"""Download the source series into data/raw/ (idempotent).

Three datos.gob.ar time-series (two CPI segments + the official FX) as JSON, and the Bluelytics
historical CSV for the informal ("blue") dollar. The datos.gob.ar API caps a response at 5000
rows, so a longer series is paged; the daily FX series is fetched collapsed to monthly
(config.FX_COLLAPSE), which fits one page. Network lives only here; everything downstream parses the
saved snapshots, so the rest of the pipeline (and the whole test suite) runs offline.

Every request is retried (RETRIES attempts, exponential backoff): data.yml hits datos.gob.ar and
Bluelytics on every pipeline PR, and a transient 5xx or reset must not fail the gate. An API error
payload fails loudly here, with the API's own message, instead of surfacing downstream as a
"splice gap" that hides the cause (a retired series id, a schema change).

datos.gob.ar also answers from replicas that are not always in sync. On 2026-10-15 about one answer
in three came from a replica that held fewer rows: San Luis empty, IPC-GBA without 1993-01 and with
98 null values, the IPC Nacional one month short, the BCRA rate with 7,647 of its 8,336 values.
Each such answer is complete in itself (its `count` agrees with its rows), so one read cannot be
trusted. The API also caches every answer by its exact URL, so asking the same URL again returns
the same stale answer. fetch_series therefore reads a series READS times, each read under its own
URL (a different no-op `start_date`), and keeps the most complete read; see there.
"""

from __future__ import annotations

import json
import random
import sys
import time
import urllib.request

from . import config

_HEADERS = {"User-Agent": "Mozilla/5.0 (peso data pipeline)"}
_PAGE = 5000  # datos.gob.ar hard cap per request
RETRIES = 3
BACKOFF_S = 2.0  # 2 s, then 4 s between attempts
# Independent full reads per series; the most complete one wins (replica skew). On 2026-10-15 up to
# 3 reads in 5 were stale, so 8 reads leave well under a 1 % chance that every read is stale.
READS = 8
# `start_date` years that filter nothing: every pinned series starts in 1992 or later. A fresh year per
# read (and per run) gives each read a URL the API has not cached yet.
NO_OP_START_YEARS = range(1900, 1990)


class MixedRead(ValueError):
    """The pages of one read report different totals: they came from replicas that disagree."""


def _get(url: str) -> bytes:
    """GET `url`, retrying a failed attempt with exponential backoff; raises after RETRIES."""
    last: Exception | None = None
    for attempt in range(1, RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=120) as resp:
                return resp.read()
        except OSError as exc:  # URLError/HTTPError, timeouts and resets are all OSError subclasses
            last = exc
            if attempt < RETRIES:
                delay = BACKOFF_S * 2 ** (attempt - 1)
                print(
                    f"[fetch]   attempt {attempt}/{RETRIES} failed ({exc}); retrying in {delay:.0f}s", file=sys.stderr
                )
                time.sleep(delay)
    raise RuntimeError(f"GET {url} failed after {RETRIES} attempts: {last}") from last


def _values(rows: list[list]) -> int:
    """Non-null values in a read (a healthy series may hold nulls, e.g. a month with no datum)."""
    return sum(1 for r in rows if len(r) > 1 and r[1] is not None)


def no_op_start_dates(n: int) -> list[str]:
    """`n` distinct `start_date` values that filter nothing (see NO_OP_START_YEARS)."""
    return [f"{y}-01-01" for y in random.sample(NO_OP_START_YEARS, n)]


def read_series(series_id: str, start_date: str, query: str = "") -> list[list]:
    """One full read of a datos.gob.ar series as [["YYYY-MM-DD", value], ...], paging past the cap.

    `query` is appended to every page URL (config.FX_COLLAPSE for the daily FX series).
    Fails when the API answers without a `data` key (its error payload is `{"errors": [...]}`): a
    retired id or a schema change, not a stale replica, so there is no point in reading again.
    Raises MixedRead when two pages report a different `count` (the pages came from replicas that
    disagree, so their rows do not line up).
    """
    rows: list[list] = []
    start = 0
    total = None
    while True:
        url = (
            f"{config.SERIES_API}?ids={series_id}&format=json&start_date={start_date}{query}"
            f"&limit={_PAGE}&start={start}"
        )
        payload = json.loads(_get(url))
        if not isinstance(payload, dict) or "data" not in payload:
            detail = payload.get("errors", payload) if isinstance(payload, dict) else payload
            raise ValueError(f"{series_id}: API response has no 'data' key — {json.dumps(detail, ensure_ascii=False)}")
        count = payload.get("count")
        if start == 0:
            total = count
        elif count != total:
            raise MixedRead(f"{series_id}: page at {start} reports count={count}, the first page {total}")
        data = payload["data"]
        rows.extend(data)
        if len(data) < _PAGE:
            break
        start += _PAGE
    return rows


def fetch_series(series_id: str, query: str = "") -> list[list]:
    """The most complete of READS reads of a series (replica skew, see the module docstring).

    A stale replica only ever held fewer values, so the read with the most non-null values wins.
    Fails when every read is empty: an empty series used to be written to disk as `[]`, and the
    build then died on a "splice gap" far from the real cause.
    """
    best: list[list] = []
    seen: list[int] = []
    for start_date in no_op_start_dates(READS):
        try:
            rows = read_series(series_id, start_date, query)
        except MixedRead as exc:
            print(f"[fetch]   discarded a read: {exc}", file=sys.stderr)
            continue
        seen.append(_values(rows))
        if _values(rows) > _values(best):
            best = rows
    if len(set(seen)) > 1:
        print(f"[fetch]   replicas disagree on {series_id}: values per read {seen}; kept {max(seen)}", file=sys.stderr)
    if not best:
        raise ValueError(f"{series_id}: API returned an empty series in {READS} reads (or only mixed reads)")
    return best


def fetch() -> None:
    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    for series_id in (config.IPC_GBA_ID, config.IPC_SANLUIS_ID, config.IPC_NACIONAL_ID, config.FX_OFICIAL_ID):
        dest = config.RAW_DIR / f"{series_id}.json"
        print(f"[fetch] {series_id} …")
        rows = fetch_series(series_id, config.FX_COLLAPSE if series_id == config.FX_OFICIAL_ID else "")
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
