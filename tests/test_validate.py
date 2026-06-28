"""Gate.check (rel/absolute, pass/fail, expected==0) and validate() against a hand-built artifact:
the HARD-gate PASS path, the FAIL -> sys.exit(1) path, and the __main__ entry. Offline."""

from __future__ import annotations

import json
import runpy

import pytest

from pipeline import config, validate

# runpy.run_module on an already-imported package warns harmlessly; ignore just that.
pytestmark = pytest.mark.filterwarnings("ignore:.*found in sys.modules:RuntimeWarning")


def _artifact(*, annual, cum_today=1000.0):
    return {
        "base_month": "2000-01",
        "series": [
            {"m": "2000-01", "cpi": 100.0, "off": 1.0, "blue": 1.0},  # convertibility + base month
            {"m": "2020-12", "cpi": 5.0, "off": 80.0, "blue": 140.0},
        ],
        "annual_inflation": annual,
        "anchors": {"cum": {"computed_today": cum_today}},
    }


def _setup(tmp_path, monkeypatch, *, annual, cum_today=1000.0):
    art_path = tmp_path / "art.json"
    art_path.write_text(json.dumps(_artifact(annual=annual, cum_today=cum_today)), encoding="utf-8")
    monkeypatch.setattr(config, "ARTIFACT_PATHS", [art_path])
    monkeypatch.setattr(config, "INDEC_NACIONAL_ANNUAL", {2020: 36.1})
    monkeypatch.setattr(config, "SANLUIS_ANNUAL", {2010: 27.0})
    monkeypatch.setattr(config, "GBA_ANNUAL", {2002: 40.9})
    monkeypatch.setattr(config, "CUM_ANCHOR",
                        {"from_month": "2003-01", "pesos": 1000.0, "expect_today_approx": 1000.0, "rel_tol": 0.1})


_GOOD = [{"year": 2020, "pct": 36.1}, {"year": 2010, "pct": 27.0}, {"year": 2002, "pct": 40.9}]


# --- Gate.check unit coverage ---

def test_gate_absolute_pass_and_fail(capsys):
    g = validate.Gate()
    assert g.check("a", 1.0, 1.0, 0.5) is True
    assert g.check("b", 10.0, 1.0, 0.5) is False
    assert g.failures == 1
    out = capsys.readouterr().out
    assert "PASS" in out and "FAIL" in out


def test_gate_relative_pass_and_zero_expected(capsys):
    g = validate.Gate()
    assert g.check("a", 1.01, 1.0, 0.05, rel=True) is True
    assert g.check("b", 5.0, 0.0, 0.05, rel=True) is False  # expected==0 short-circuits to fail
    assert g.failures == 1


# --- validate() integration ---

def test_validate_passes(tmp_path, monkeypatch, capsys):
    _setup(tmp_path, monkeypatch, annual=_GOOD)
    validate.validate()
    assert "VALIDACIÓN OK" in capsys.readouterr().out


def test_validate_fails_exits_1(tmp_path, monkeypatch, capsys):
    bad = [{"year": 2020, "pct": 99.0}, {"year": 2010, "pct": 27.0}, {"year": 2002, "pct": 40.9}]
    _setup(tmp_path, monkeypatch, annual=bad)
    with pytest.raises(SystemExit) as exc:
        validate.validate()
    assert exc.value.code == 1
    assert "VALIDACIÓN FALLIDA" in capsys.readouterr().out


def test_validate_fails_on_non_positive_index(tmp_path, monkeypatch, capsys):
    art_path = tmp_path / "art.json"
    art = _artifact(annual=_GOOD)
    art["series"].append({"m": "2021-01", "cpi": 0.0, "off": 90.0, "blue": 180.0})  # non-positive
    art_path.write_text(json.dumps(art), encoding="utf-8")
    monkeypatch.setattr(config, "ARTIFACT_PATHS", [art_path])
    monkeypatch.setattr(config, "INDEC_NACIONAL_ANNUAL", {2020: 36.1})
    monkeypatch.setattr(config, "SANLUIS_ANNUAL", {2010: 27.0})
    monkeypatch.setattr(config, "GBA_ANNUAL", {2002: 40.9})
    monkeypatch.setattr(config, "CUM_ANCHOR",
                        {"from_month": "2003-01", "pesos": 1000.0, "expect_today_approx": 1000.0, "rel_tol": 0.1})
    with pytest.raises(SystemExit) as exc:
        validate.validate()
    assert exc.value.code == 1
    assert "no positivos" in capsys.readouterr().out


def test_validate_main(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, annual=_GOOD)
    runpy.run_module("pipeline.validate", run_name="__main__")  # PASS path, no exit
