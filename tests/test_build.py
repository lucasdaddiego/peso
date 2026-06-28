"""forward_fill, build_blue (all four branches), and build() end-to-end on the synthetic raw
snapshots, plus the __main__ success + error-reraise paths. Offline."""

from __future__ import annotations

import json
import runpy

import pytest

from pipeline import build, config

# runpy.run_module on an already-imported package warns harmlessly; ignore just that.
pytestmark = pytest.mark.filterwarnings("ignore:.*found in sys.modules:RuntimeWarning")


def test_forward_fill_carries_over_gaps():
    src = {"2005-01": 10.0, "2005-03": 30.0}
    out = build.forward_fill(src, ["2005-01", "2005-02", "2005-03", "2005-04"])
    assert out == {"2005-01": 10.0, "2005-02": 10.0, "2005-03": 30.0, "2005-04": 30.0}


def test_forward_fill_raises_without_a_prior_value():
    with pytest.raises(ValueError, match="forward-fill"):
        build.forward_fill({"2005-02": 5.0}, ["2005-01", "2005-02"])


def test_build_blue_all_branches(tiny_window):
    months = ["2005-04", "2005-05", "2005-06", "2005-07"]
    official = {"2005-04": 2.0, "2005-05": 2.5, "2005-06": 3.0, "2005-07": 3.2}
    # BLUE_FIRST_MONTH == 2005-05; 2005-05 missing from blue_raw -> "no real yet" -> official fallback;
    # 2005-06 present -> real; 2005-07 missing but a real exists -> carry.
    blue_raw = {"2005-06": 4.0}
    blue, est = build.build_blue(official, blue_raw, months)
    assert blue == {"2005-04": 2.0, "2005-05": 2.5, "2005-06": 4.0, "2005-07": 4.0}
    assert est == {"2005-04": True, "2005-05": True, "2005-06": False, "2005-07": True}


def test_build_end_to_end(tiny_raw):
    art = build.build()
    assert set(art) == {
        "schema_version",
        "generated_at",
        "currency",
        "vintage",
        "vintage_label",
        "base_month",
        "start_month",
        "source",
        "series",
        "annual_inflation",
        "anchors",
        "citation",
    }
    series = art["series"]
    assert [r["m"] for r in series] == [
        "2005-01",
        "2005-02",
        "2005-03",
        "2005-04",
        "2005-05",
        "2005-06",
        "2005-07",
        "2005-08",
    ]
    assert series[0]["mom"] is None  # first month, no MoM
    assert {r["m"]: r["src"] for r in series}["2005-06"] == "nacional"
    # the base month is exactly 100, and the blue flags follow the cutover/carry logic.
    assert next(r for r in series if r["m"] == art["base_month"])["cpi"] == 100.0
    est = {r["m"]: r["blue_est"] for r in series}
    assert est["2005-04"] is True and est["2005-05"] is False and est["2005-06"] is True
    assert art["anchors"]["cum"]["computed_today"] > 0
    # Both copies written and parseable.
    for p in config.ARTIFACT_PATHS:
        assert json.loads(p.read_text(encoding="utf-8"))["schema_version"] == build.SCHEMA_VERSION


def test_build_main_success(tiny_raw):
    runpy.run_module("pipeline.build", run_name="__main__")
    assert config.ARTIFACT_PATHS[0].exists()


def test_build_main_error_reraises(tmp_path, monkeypatch):
    # Point RAW_DIR at an empty dir so build() fails reading the first snapshot, and __main__ reraises.
    monkeypatch.setattr(config, "RAW_DIR", tmp_path / "empty")
    with pytest.raises(FileNotFoundError):
        runpy.run_module("pipeline.build", run_name="__main__")
