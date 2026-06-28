"""diffs() across every node type (dict keys both ways, list length, bool-vs-int, numeric
tolerance, string, ignored keys) and main() (usage, identical, drift, >50 truncation, __main__)."""

from __future__ import annotations

import json
import runpy
import sys

import pytest

from pipeline import artifact_check as ac

# runpy.run_module on an already-imported package warns harmlessly; ignore just that.
pytestmark = pytest.mark.filterwarnings("ignore:.*found in sys.modules:RuntimeWarning")


def test_identical_within_tolerance_and_ignored_keys():
    old = {"a": 1.0000001, "b": [1, 2, 3], "generated_at": "X"}
    new = {"a": 1.0, "b": [1, 2, 3], "generated_at": "Y"}  # numeric within tol; generated_at ignored
    assert ac.diffs(old, new) == []


def test_numeric_beyond_tolerance():
    assert ac.diffs({"a": 1.0}, {"a": 2.0}) == ["/a: 1.0 != 2.0 (beyond tolerance)"]


def test_dict_key_presence_both_directions():
    out = ac.diffs({"a": 1, "x": 1}, {"a": 1, "y": 1})
    assert any("missing in rebuilt" in d for d in out)
    assert any("missing in committed" in d for d in out)


def test_list_length_mismatch():
    assert ac.diffs([1, 2], [1, 2, 3]) == [": list length 2 != 3"]


def test_bool_is_compared_exactly():
    assert ac.diffs({"f": True}, {"f": 1}) == ["/f: True != 1"]
    assert ac.diffs({"f": False}, {"f": False}) == []


def test_string_inequality():
    assert ac.diffs("a", "b") == [": 'a' != 'b'"]


def _run_main(monkeypatch, old, new, tmp_path):
    a, b = tmp_path / "old.json", tmp_path / "new.json"
    a.write_text(json.dumps(old), encoding="utf-8")
    b.write_text(json.dumps(new), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["prog", str(a), str(b)])
    return ac.main(sys.argv)


def test_main_usage_error():
    assert ac.main(["prog", "only-one"]) == 2


def test_main_ok(tmp_path, monkeypatch, capsys):
    assert _run_main(monkeypatch, {"a": 1}, {"a": 1}, tmp_path) == 0
    assert "OK" in capsys.readouterr().out


def test_main_drift_truncates_over_50(tmp_path, monkeypatch, capsys):
    old = {str(i): i for i in range(60)}
    new = {str(i): i + 1000 for i in range(60)}  # 60 differences -> truncated to 50
    assert _run_main(monkeypatch, old, new, tmp_path) == 1
    out = capsys.readouterr().out
    assert "and 10 more" in out


def test_main_module_entry(tmp_path, monkeypatch):
    a, b = tmp_path / "o.json", tmp_path / "n.json"
    a.write_text(json.dumps({"a": 1}), encoding="utf-8")
    b.write_text(json.dumps({"a": 2}), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["prog", str(a), str(b)])
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("pipeline.artifact_check", run_name="__main__")
    assert exc.value.code == 1
