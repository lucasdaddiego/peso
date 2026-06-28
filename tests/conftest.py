"""Shared fixtures + tiny synthetic CPI/FX series.

Everything here is offline and deterministic. The real splice spans 401 months (1993→2026); the
tests instead monkeypatch the config window down to a handful of months in 2005 and feed in
hand-built source series, so every branch of the splice/build is exercised without the network
and without the real fetched snapshots.

The tiny window (`tiny_window`) is laid out to hit all three splice segments and the one-month
overlap at each breakpoint:

    2005-01            base of the chain (no MoM)
    2005-02 … 2005-03  owned by GBA            (display: gba)
    2005-04 … 2005-06  owned by San Luis       (display: sanluis up to 2005-05, then nacional)
    2005-07 … 2005-08  owned by INDEC Nacional (display: nacional)   2005-08 = vintage = 100
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# The app sets [tool.uv] package = false, so `pipeline` is never installed. Put the repo root on
# sys.path so the suite imports the in-tree package, like the Makefile's `python -m pipeline.*`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from pipeline import config


def series_json(values: dict[str, float], day: str = "01") -> str:
    """Render {month: value} as the datos.gob.ar [['YYYY-MM-DD', value], ...] JSON shape."""
    return json.dumps([[f"{m}-{day}", v] for m, v in values.items()])


def bluelytics_csv(blue: dict[str, float], oficial: dict[str, float] | None = None) -> str:
    """Render monthly blue/oficial dicts as a Bluelytics evolution.csv (one day per month)."""
    lines = ["day,type,value_buy,value_sell"]
    for m, v in (oficial or {}).items():
        lines.append(f"{m}-15,Oficial,{v},{v}")
    for m, v in blue.items():
        lines.append(f"{m}-15,Blue,{v - 5},{v}")
    return "\n".join(lines) + "\n"


# Synthetic source series for the tiny window. Index levels are arbitrary (only their MoM ratios
# matter); each owning source covers the month *before* its window so the hand-off has no gap.
GBA = {"2005-01": 100.0, "2005-02": 110.0, "2005-03": 121.0}
SANLUIS = {"2005-03": 200.0, "2005-04": 220.0, "2005-05": 231.0, "2005-06": 242.55}
NACIONAL = {"2005-06": 50.0, "2005-07": 55.0, "2005-08": 60.5}
FX_OFICIAL = {  # daily-shaped monthly; convertibility-ish then a jump
    "2005-01": 1.0, "2005-02": 1.0, "2005-03": 1.0, "2005-04": 2.0,
    "2005-05": 2.5, "2005-06": 3.0, "2005-07": 3.2, "2005-08": 3.4,
}
BLUE = {"2005-05": 3.0, "2005-07": 4.5, "2005-08": 5.0}  # missing 2005-06 → carry; starts 2005-05


@pytest.fixture
def tiny_window(monkeypatch):
    """Shrink the config splice window to the 2005 toy span (and the blue cutover)."""
    monkeypatch.setattr(config, "SERIES_START", "2005-01")
    monkeypatch.setattr(config, "SEG_A_END", "2005-03")
    monkeypatch.setattr(config, "SEG_B_END", "2005-05")
    monkeypatch.setattr(config, "SEG_C_START", "2005-06")
    monkeypatch.setattr(config, "DATA_VINTAGE", "2005-08")
    monkeypatch.setattr(config, "BLUE_FIRST_MONTH", "2005-05")
    # The real cumulative cross-check anchors on 2003-01, outside this window — repoint it inside.
    monkeypatch.setattr(config, "CUM_ANCHOR",
                        {"from_month": "2005-02", "pesos": 1000.0, "expect_today_approx": 1614.0, "rel_tol": 0.1})
    return config


@pytest.fixture
def tiny_raw(tmp_path, monkeypatch, tiny_window):
    """A tmp data/raw with the synthetic snapshots, config paths pointed at tmp. build() runs offline."""
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / f"{config.IPC_GBA_ID}.json").write_text(series_json(GBA), encoding="utf-8")
    (raw / f"{config.IPC_SANLUIS_ID}.json").write_text(series_json(SANLUIS), encoding="utf-8")
    (raw / f"{config.IPC_NACIONAL_ID}.json").write_text(series_json(NACIONAL), encoding="utf-8")
    (raw / f"{config.FX_OFICIAL_ID}.json").write_text(series_json(FX_OFICIAL, day="15"), encoding="utf-8")
    (raw / "bluelytics_evolution.csv").write_text(bluelytics_csv(BLUE), encoding="utf-8")
    monkeypatch.setattr(config, "RAW_DIR", raw)
    monkeypatch.setattr(config, "ARTIFACT_PATHS", [tmp_path / "data" / "series.v1.json",
                                                   tmp_path / "web" / "public" / "series.v1.json"])
    return raw
