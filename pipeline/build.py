"""Load the raw snapshots, splice the CPI, assemble the FX series, emit the versioned artifact.

Output: a single provenance-stamped JSON (committed to data/ and web/public/) holding the monthly
spliced CPI index (= "pesos de hoy"), month-over-month and Dec–Dec inflation, and the monthly
official + blue exchange rates — everything the static web app needs to answer "what is X pesos
from month Y worth today?" with no further computation.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime

from . import config, load, splice

SCHEMA_VERSION = 1


def forward_fill(src: dict[str, float], months: list[str]) -> dict[str, float]:
    """Project a monthly series onto `months`, carrying the last known value over any gaps."""
    out: dict[str, float] = {}
    last: float | None = None
    for m in months:
        if m in src:
            last = src[m]
        if last is None:
            raise ValueError(f"no value at or before {m} to forward-fill from")
        out[m] = last
    return out


def build_blue(fx_official: dict[str, float], blue_raw: dict[str, float], months: list[str]) -> tuple[dict, dict]:
    """Monthly blue rate + an 'estimated' flag.

    Before the cepo cambiario (Bluelytics starts 2011-01) there was no meaningful parallel market,
    so blue := official and the month is flagged estimated. From 2011-01 on, use Bluelytics; carry
    the last real blue over any missing month (also flagged estimated) rather than collapsing it to
    the official rate, which would invent a fake convergence.
    """
    blue: dict[str, float] = {}
    estimated: dict[str, bool] = {}
    last_real: float | None = None
    for m in months:
        if m >= config.BLUE_FIRST_MONTH and m in blue_raw:
            blue[m] = blue_raw[m]
            estimated[m] = False
            last_real = blue_raw[m]
        elif m < config.BLUE_FIRST_MONTH:
            blue[m] = fx_official[m]
            estimated[m] = True
        else:
            blue[m] = last_real if last_real is not None else fx_official[m]
            estimated[m] = True
    return blue, estimated


def build() -> dict:
    gba = load.load_series_file(config.RAW_DIR / f"{config.IPC_GBA_ID}.json")
    sanluis = load.load_series_file(config.RAW_DIR / f"{config.IPC_SANLUIS_ID}.json")
    nacional = load.load_series_file(config.RAW_DIR / f"{config.IPC_NACIONAL_ID}.json")
    fx_off_raw = load.load_series_file(config.RAW_DIR / f"{config.FX_OFICIAL_ID}.json")
    blue_raw = load.load_bluelytics_file(config.RAW_DIR / "bluelytics_evolution.csv")

    months = splice.enumerate_months(config.SERIES_START, config.DATA_VINTAGE)
    index = splice.splice_index(gba, sanluis, nacional)
    mom = splice.monthly_inflation(index, months)
    annual = splice.annual_inflation(index)
    fx_official = forward_fill(fx_off_raw, months)
    fx_blue, fx_blue_est = build_blue(fx_official, blue_raw, months)

    series = [
        {
            "m": m,
            "cpi": index[m],
            "src": splice.display_source(m),
            "mom": mom.get(m),
            "off": round(fx_official[m], 4),
            "blue": round(fx_blue[m], 4),
            "blue_est": fx_blue_est[m],
        }
        for m in months
    ]

    cum_today = round(config.CUM_ANCHOR["pesos"] * 100.0 / index[config.CUM_ANCHOR["from_month"]], 2)

    artifact = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "currency": "ARS",
        "vintage": config.DATA_VINTAGE,
        "vintage_label": config.VINTAGE_LABEL,
        "base_month": config.DATA_VINTAGE,
        "start_month": config.SERIES_START,
        "source": {
            "ipc_segments": config.SEGMENTS,
            "fx_official": {
                "label": "Tipo de cambio de referencia BCRA (dólar billete)",
                "series_id": config.FX_OFICIAL_ID,
                "url": "https://www.bcra.gob.ar",
            },
            "fx_blue": {
                "label": "Dólar informal ('blue') — Bluelytics",
                "url": config.BLUELYTICS_CSV,
                "first_month": config.BLUE_FIRST_MONTH,
                "note": "Antes del cepo (2011) no había un mercado paralelo relevante; se usa el oficial.",
            },
            "api": config.SERIES_API,
        },
        "series": series,
        "annual_inflation": annual,
        "anchors": {
            "indec_nacional_annual": {str(k): v for k, v in config.INDEC_NACIONAL_ANNUAL.items()},
            "sanluis_annual": {str(k): v for k, v in config.SANLUIS_ANNUAL.items()},
            "gba_annual": {str(k): v for k, v in config.GBA_ANNUAL.items()},
            "cum": {**config.CUM_ANCHOR, "computed_today": cum_today},
        },
        "citation": config.CITATION,
    }

    payload = json.dumps(artifact, ensure_ascii=False, indent=2)
    for path in config.ARTIFACT_PATHS:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding="utf-8")
        print(f"[build] wrote {path} ({len(payload):,} bytes, {len(series)} months {months[0]}…{months[-1]})")
    return artifact


if __name__ == "__main__":
    try:
        build()
    except Exception as exc:
        print(f"[build] ERROR: {exc}", file=sys.stderr)
        raise
