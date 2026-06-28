"""The splice math: month enumeration, MoM ownership + display tagging, chaining/rebasing,
and the monthly/annual inflation derivations. Pure and offline."""

from __future__ import annotations

import pytest

from pipeline import splice
from tests.conftest import GBA, NACIONAL, SANLUIS


def test_enumerate_months_rollover_and_single():
    assert splice.enumerate_months("2005-11", "2006-02") == ["2005-11", "2005-12", "2006-01", "2006-02"]
    assert splice.enumerate_months("2005-06", "2005-06") == ["2005-06"]


def test_mom_source_picks_the_owning_series(tiny_window):
    assert splice.mom_source("2005-02", GBA, SANLUIS, NACIONAL) is GBA      # <= SEG_A_END
    assert splice.mom_source("2005-04", GBA, SANLUIS, NACIONAL) is SANLUIS  # intervened window
    assert splice.mom_source("2005-06", GBA, SANLUIS, NACIONAL) is SANLUIS  # the 2016-12-style overlap
    assert splice.mom_source("2005-07", GBA, SANLUIS, NACIONAL) is NACIONAL  # official again


def test_display_source_tags(tiny_window):
    assert splice.display_source("2005-03") == "gba"
    assert splice.display_source("2005-05") == "sanluis"
    # the overlap month: San Luis supplies its MoM, but it's tagged with the national base.
    assert splice.display_source("2005-06") == "nacional"


def test_splice_index_chains_and_rebases(tiny_window):
    idx = splice.splice_index(GBA, SANLUIS, NACIONAL)
    assert idx["2005-08"] == 100.0  # vintage rebased to 100
    assert idx["2005-01"] == pytest.approx(56.32, abs=0.05)
    months = splice.enumerate_months("2005-01", "2005-08")
    vals = [idx[m] for m in months]
    assert vals == sorted(vals)  # strictly increasing in this synthetic series


def test_splice_index_raises_on_gap(tiny_window):
    holed = {k: v for k, v in SANLUIS.items() if k != "2005-04"}
    with pytest.raises(ValueError, match="splice gap"):
        splice.splice_index(GBA, holed, NACIONAL)


def test_monthly_inflation():
    months = ["2005-01", "2005-02", "2005-03"]
    idx = {"2005-01": 100.0, "2005-02": 110.0, "2005-03": 121.0}
    mom = splice.monthly_inflation(idx, months)
    assert "2005-01" not in mom  # first month has no predecessor
    assert mom["2005-02"] == pytest.approx(10.0)
    assert mom["2005-03"] == pytest.approx(10.0)


def test_annual_inflation_dec_to_dec_with_missing_endpoint():
    idx = {"2018-12": 100.0, "2019-12": 150.0, "2020-12": 300.0, "2021-06": 400.0}
    out = splice.annual_inflation(idx)
    years = {r["year"]: r["pct"] for r in out}
    assert years[2019] == pytest.approx(50.0)
    assert years[2020] == pytest.approx(100.0)
    # 2021 has no December (only 2021-06) -> skipped; 2018 has no prior December -> skipped.
    assert 2021 not in years and 2018 not in years
