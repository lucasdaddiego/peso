"""Pinned configuration and verified reference data for the peso CPI/FX pipeline.

Single source of truth: the source series (datos.gob.ar / Bluelytics), the splice breakpoints,
the data vintage, and the official figures the build must reproduce. Every anchor here was
confirmed against the primary source in June 2026.

Why a *spliced* CPI. INDEC's consumer-price index was statistically intervened from roughly
2007 to 2015 (the "INDEC intervenido" era): official inflation was understated by a wide margin.
A purchasing-power tool that used the official numbers for that decade would badly overstate what
old pesos are worth today. So the index is built in three documented segments:

  A  1993-01 … 2006-12   INDEC IPC-GBA, official, PRE-intervention (trustworthy).
  B  2007-01 … 2016-11   IPC San Luis — a provincial index NOT under national intervention, the
                         credible "inflación verdadera" proxy for the intervened decade.
  C  2016-12 … vintage   INDEC IPC Nacional (base dic-2016), official, post-intervention.

The segments are chained by month-over-month growth at the breakpoints and rebased so the latest
month = 100, i.e. the index is expressed in "pesos de hoy". See docs/metodologia.md and the README.
"""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

# --------------------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
# The committed artifact lives in both data/ (provenance) and web/public/ (served by Vite).
ARTIFACT_PATHS = [DATA_DIR / "series.v1.json", ROOT / "web" / "public" / "series.v1.json"]

# --------------------------------------------------------------------------------------
# Data vintage. Every series is truncated to <= this month, so the build is reproducible
# regardless of when it runs: newly published months are ignored until the vintage is bumped.
# To update: bump DATA_VINTAGE to the latest COMPLETE month, run `make data`, commit.
# (2026-05 is the last complete month of the national IPC as of the June-2026 build.)
# --------------------------------------------------------------------------------------
DATA_VINTAGE = "2026-05"
VINTAGE_LABEL = "mayo 2026"

# --------------------------------------------------------------------------------------
# Source series (datos.gob.ar "series de tiempo" API). Each id is a real, documented series;
# the API returns [["YYYY-MM-DD", value], ...]. base_url + ?ids=<id> drives the fetch.
# --------------------------------------------------------------------------------------
SERIES_API = "https://apis.datos.gob.ar/series/api/series/"

# CPI segments. `level` series are monthly index levels; the splice only uses their MoM ratios,
# so the differing bases (abril-2008, 2014, dic-2016) don't matter — only the growth does.
IPC_GBA_ID = "97.2_ING_2008_M_17"  # INDEC IPC-GBA, base abril 2008 — segment A
IPC_SANLUIS_ID = "197.1_NIVEL_GENERAL_2014_0_13"  # IPC San Luis — segment B (intervened window)
IPC_NACIONAL_ID = "148.3_INIVELNAL_DICI_M_26"  # INDEC IPC Nacional, base dic-2016 — segment C
FX_OFICIAL_ID = "175.1_DR_ESTANSE_0_0_20"  # BCRA reference USD (billete), daily, from 1992

# Splice segment boundaries (inclusive). Months outside [START, vintage] are dropped.
SERIES_START = "1993-01"
SEG_A_END = "2006-12"  # last official pre-intervention GBA month
SEG_B_START = "2007-01"  # first intervened-era month -> switch to San Luis
SEG_B_END = "2016-11"  # last month before the national IPC base
SEG_C_START = "2016-12"  # INDEC IPC Nacional base month -> official again


# Human-readable provenance for each segment (shown in the app's methodology + the artifact).
class SegmentMeta(TypedDict):
    key: str
    start: str
    end: str
    label: str
    source: str
    series_id: str
    note: str


SEGMENTS: list[SegmentMeta] = [
    {
        "key": "gba",
        "start": SERIES_START,
        "end": SEG_A_END,
        "label": "INDEC IPC-GBA (oficial, pre-intervención)",
        "source": "INDEC — IPC Gran Buenos Aires, base abril 2008",
        "series_id": IPC_GBA_ID,
        "note": "Serie oficial confiable, anterior a la intervención del INDEC.",
    },
    {
        "key": "sanluis",
        "start": SEG_B_START,
        "end": SEG_B_END,
        "label": "IPC San Luis (alternativa provincial, INDEC intervenido)",
        "source": "Dirección Provincial de Estadística y Censos de San Luis",
        "series_id": IPC_SANLUIS_ID,
        "note": "Durante 2007–2015 el INDEC nacional fue intervenido y subdeclaró la inflación. "
        "San Luis, fuera de esa intervención, es uno de los índices provinciales usados "
        "como referencia creíble ('inflación verdadera').",
    },
    {
        "key": "nacional",
        "start": SEG_C_START,
        "end": DATA_VINTAGE,
        "label": "INDEC IPC Nacional (oficial, base dic-2016)",
        "source": "INDEC — IPC Nacional, base diciembre 2016",
        "series_id": IPC_NACIONAL_ID,
        "note": "Serie oficial nacional, posterior a la normalización del INDEC.",
    },
]

# --------------------------------------------------------------------------------------
# FX. Official = BCRA reference USD (datos.gob.ar, daily from 1992). Blue/informal =
# Bluelytics historical (daily from 2011). Before the cepo cambiario (late 2011) there was
# no meaningful parallel market, so blue is set equal to the official rate for those months.
# --------------------------------------------------------------------------------------
BLUELYTICS_CSV = "https://api.bluelytics.com.ar/v2/evolution.csv"
BLUE_FIRST_MONTH = "2011-01"  # earliest Bluelytics blue datum; earlier months: blue := official
FX_AGGREGATION = "month_end"  # use the last business-day rate of each month

# --------------------------------------------------------------------------------------
# Validation anchors — the build MUST reproduce these (within tolerance) or it fails.
# Inflación interanual diciembre–diciembre (%).
# --------------------------------------------------------------------------------------
# Official INDEC IPC Nacional, Dec–Dec (published headline figures). Segment C must reproduce these.
INDEC_NACIONAL_ANNUAL = {
    2017: 24.8,
    2018: 47.6,
    2019: 53.8,
    2020: 36.1,
    2021: 50.9,
    2022: 94.8,
    2023: 211.4,
    2024: 117.8,
}

# San Luis Dec–Dec for the intervened decade (segment B reproduces these directly). The point is
# the GAP vs the discredited official figures (which claimed ~10%/yr in 2008–2015).
SANLUIS_ANNUAL = {
    2007: 21.5,
    2008: 20.6,
    2009: 18.5,
    2010: 27.0,
    2011: 23.3,
    2012: 23.0,
    2013: 31.9,
    2014: 39.0,
    2015: 31.6,
}

# Pre-intervention GBA anchors. 2002 = the convertibility collapse (~41%); 1996–2001 = the
# convertibility years of ~zero inflation / mild deflation.
GBA_ANNUAL = {2002: 40.9}
CONVERTIBILITY_FX = 1.0  # 1 peso = 1 USD, Jan-1992 … Dec-2001
CONVERTIBILITY_FX_TOL = 0.03  # daily ref rate hovers ~0.99–1.00


# A hand-computed cumulative cross-check, independent of the per-year anchors: $1.000 de enero-2003
# en pesos de la vintage. Derived once from the spliced index and pinned so a future change that
# silently breaks the chaining is caught. Tolerance is generous (the splice can shift slightly when
# a source revises a back-month); a gross error (wrong chaining) is orders of magnitude off.
class CumAnchor(TypedDict):
    from_month: str
    pesos: float
    expect_today_approx: float
    rel_tol: float


CUM_ANCHOR: CumAnchor = {
    "from_month": "2003-01",
    "pesos": 1000.0,
    "expect_today_approx": 1648923.0,  # ≈ pesos de la vintage; cross-checked at build time
    "rel_tol": 0.08,
}

CITATION = (
    "Elaboración propia en base a series oficiales del INDEC (IPC) y del BCRA (tipo de cambio), "
    "vía datos.gob.ar, empalmadas con el IPC de San Luis para el período de intervención del INDEC "
    "(2007–2015), y cotización informal histórica de Bluelytics. Fuentes: INDEC (www.indec.gob.ar), "
    "BCRA (www.bcra.gob.ar), datos.gob.ar, bluelytics.com.ar."
)
