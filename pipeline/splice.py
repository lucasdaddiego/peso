"""Splice the three CPI segments into one continuous monthly index (pure, offline).

The index is built by chaining month-over-month growth: each month's level is the previous
month's level times that month's growth, where the growth comes from whichever source "owns"
the month. Because each source covers the month *before* its ownership window starts, the
hand-off at a breakpoint is a clean one-month overlap with no gap and no double-count:

    gba       owns 1993-02 … 2006-12   (has 1993-01 …)
    sanluis   owns 2007-01 … 2016-12   (has 2006-12 …, so the 2007-01 hand-off is clean;
                                         also supplies the 2016-12 step into the national base)
    nacional  owns 2017-01 … vintage   (has 2016-12 …, the official base = its anchor)

The chained level is finally rebased so the vintage month = 100 → the index reads directly in
"pesos de hoy".
"""

from __future__ import annotations

from itertools import pairwise

from . import config


def enumerate_months(start: str, end: str) -> list[str]:
    """Ordered ['YYYY-MM', ...] inclusive of both endpoints."""
    sy, sm = int(start[:4]), int(start[5:7])
    ey, em = int(end[:4]), int(end[5:7])
    out: list[str] = []
    y, m = sy, sm
    while (y, m) <= (ey, em):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            m, y = 1, y + 1
    return out


def mom_source(month: str, gba: dict, sanluis: dict, nacional: dict) -> dict:
    """The series that owns the month-over-month growth *into* `month`."""
    if month <= config.SEG_A_END:
        return gba
    if month <= config.SEG_C_START:  # San Luis spans the intervened decade + the 2016-12 overlap
        return sanluis
    return nacional


def display_source(month: str) -> str:
    """Per-month provenance tag for the UI/artifact (the national base dic-2016 is tagged 'nacional')."""
    if month <= config.SEG_A_END:
        return "gba"
    if month <= config.SEG_B_END:
        return "sanluis"
    return "nacional"


def splice_index(gba: dict, sanluis: dict, nacional: dict) -> dict[str, float]:
    """Chain the three segments by MoM growth and rebase so the vintage month = 100."""
    months = enumerate_months(config.SERIES_START, config.DATA_VINTAGE)
    raw: dict[str, float] = {months[0]: 100.0}
    for prev, cur in pairwise(months):
        src = mom_source(cur, gba, sanluis, nacional)
        if cur not in src or prev not in src:
            raise ValueError(f"splice gap: {cur} (or {prev}) missing from its owning source")
        raw[cur] = raw[prev] * (src[cur] / src[prev])
    base = raw[config.DATA_VINTAGE]
    return {m: round(raw[m] / base * 100.0, 6) for m in months}


def monthly_inflation(index: dict[str, float], months: list[str]) -> dict[str, float]:
    """Month-over-month inflation (%). The first month has no predecessor → omitted."""
    out: dict[str, float] = {}
    for prev, cur in pairwise(months):
        out[cur] = round((index[cur] / index[prev] - 1.0) * 100.0, 4)
    return out


def annual_inflation(index: dict[str, float]) -> list[dict]:
    """Dec–Dec inflation (%) for every year whose December and the prior December are present."""
    out: list[dict] = []
    years = sorted({int(m[:4]) for m in index})
    for y in years:
        a, b = index.get(f"{y - 1}-12"), index.get(f"{y}-12")
        if a is None or b is None:
            continue
        out.append({"year": y, "pct": round((b / a - 1.0) * 100.0, 2), "source": display_source(f"{y}-12")})
    return out
