"""Parse the raw snapshots in data/raw/ into clean monthly dicts (offline, pure).

datos.gob.ar series come as [["YYYY-MM-DD", value], ...]. CPI series are monthly (one row per
month); the FX series is daily, collapsed here to one rate per month (end of period — the last
business day's value). Bluelytics is a CSV of daily Oficial/Blue buy+sell rows.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from . import config


def month_key(date_str: str) -> str:
    """'2007-03-01' / '2007-03-15' → '2007-03'."""
    return date_str[:7]


def _truncate(month: str) -> bool:
    """Keep months within [SERIES_START, DATA_VINTAGE]. Earlier/later are dropped."""
    return config.SERIES_START <= month <= config.DATA_VINTAGE


def monthly_from_rows(rows: list[list]) -> dict[str, float]:
    """Collapse [date, value] rows to {month: value}, end-of-period (last non-null wins).

    Rows are chronological; for a monthly series there's one per month, for a daily series the
    last day of the month is taken. Null values are skipped. Months outside the vintage window
    are dropped here so every downstream consumer sees the same pinned range.
    """
    out: dict[str, float] = {}
    for date_str, value in rows:
        if value is None:
            continue
        m = month_key(date_str)
        if _truncate(m):
            out[m] = float(value)
    return out


def load_series_file(path: Path) -> dict[str, float]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    return monthly_from_rows(rows)


def bluelytics_from_rows(rows: list[dict]) -> dict[str, float]:
    """{month: blue venta} from Bluelytics CSV rows (type 'Blue'), end-of-period (last day wins).

    `rows` are dicts with day/type/value_sell; the file is chronological so later days overwrite.
    """
    out: dict[str, float] = {}
    for r in rows:
        if r.get("type") != "Blue":
            continue
        m = month_key(r["day"])
        if _truncate(m):
            out[m] = float(r["value_sell"])
    return out


def load_bluelytics_file(path: Path) -> dict[str, float]:
    with path.open(encoding="utf-8") as f:
        return bluelytics_from_rows(list(csv.DictReader(f)))
