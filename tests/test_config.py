"""Invariants on the pinned config: the splice window is ordered, the segments tile it, and the
validation anchors are well-formed. These guard against a careless edit to the source of truth."""

from __future__ import annotations

from pipeline import config


def test_splice_window_is_ordered():
    assert config.SERIES_START < config.SEG_A_END < config.SEG_B_END < config.SEG_C_START <= config.DATA_VINTAGE
    assert config.SERIES_START <= config.BLUE_FIRST_MONTH <= config.DATA_VINTAGE


def test_segments_cover_the_window_in_order():
    keys = [s["key"] for s in config.SEGMENTS]
    assert keys == ["gba", "sanluis", "nacional"]
    assert config.SEGMENTS[0]["start"] == config.SERIES_START
    assert config.SEGMENTS[-1]["end"] == config.DATA_VINTAGE
    # each segment carries provenance the UI/methodology renders
    for s in config.SEGMENTS:
        assert s["source"] and s["label"] and s["note"]


def test_anchor_years_land_in_the_right_segments():
    assert max(config.GBA_ANNUAL) <= 2006
    assert all(2007 <= y <= 2015 for y in config.SANLUIS_ANNUAL)
    assert all(y >= 2017 for y in config.INDEC_NACIONAL_ANNUAL)


def test_cum_anchor_shape():
    c = config.CUM_ANCHOR
    assert set(c) == {"from_month", "pesos", "expect_today_approx", "rel_tol"}
    assert c["pesos"] > 0 and c["expect_today_approx"] > 0 and 0 < c["rel_tol"] < 1


def test_citation_mentions_the_sources():
    for token in ("INDEC", "BCRA", "San Luis", "Bluelytics"):
        assert token in config.CITATION
