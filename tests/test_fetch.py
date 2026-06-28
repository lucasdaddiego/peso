"""fetch_series paging, fetch() writing every snapshot, the urlopen wrapper, and the __main__
success + error->exit(1) paths. Never touches the network."""

from __future__ import annotations

import json
import runpy
import urllib.error
import urllib.request

import pytest

from pipeline import config, fetch

# runpy.run_module on an already-imported package warns harmlessly; ignore just that.
pytestmark = pytest.mark.filterwarnings("ignore:.*found in sys.modules:RuntimeWarning")


class _FakeResp:
    def __init__(self, data: bytes):
        self._data = data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self) -> bytes:
        return self._data


def test_get_wraps_urlopen(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=0: _FakeResp(b"HELLO"))
    assert fetch._get("https://example/x") == b"HELLO"


def test_fetch_series_pages(monkeypatch):
    monkeypatch.setattr(fetch, "_PAGE", 2)
    pages = [
        json.dumps({"data": [["2000-01-01", 1], ["2000-02-01", 2]]}).encode(),  # full page -> continue
        json.dumps({"data": [["2000-03-01", 3]]}).encode(),  # short page -> stop
    ]
    calls = iter(pages)
    monkeypatch.setattr(fetch, "_get", lambda url: next(calls))
    rows = fetch.fetch_series("any-id")
    assert rows == [["2000-01-01", 1], ["2000-02-01", 2], ["2000-03-01", 3]]


def _fake_get(url: str) -> bytes:
    if url.endswith(".csv"):
        return b"day,type,value_buy,value_sell\n2011-01-15,Blue,4,4\n"
    return json.dumps({"data": [["2016-12-01", 100.0]]}).encode()


def test_fetch_writes_all_snapshots(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(config, "RAW_DIR", tmp_path / "raw")  # doesn't exist -> mkdir(parents=True)
    monkeypatch.setattr(fetch, "_get", _fake_get)
    fetch.fetch()
    for sid in (config.IPC_GBA_ID, config.IPC_SANLUIS_ID, config.IPC_NACIONAL_ID, config.FX_OFICIAL_ID):
        assert (tmp_path / "raw" / f"{sid}.json").exists()
    assert (tmp_path / "raw" / "bluelytics_evolution.csv").exists()
    assert "bluelytics" in capsys.readouterr().out


# runpy re-executes the module fresh, rebinding fetch._get — only patches on the shared stdlib
# (urllib.request.urlopen) survive into the __main__ run, so the entrypoint tests patch there.
def _fake_urlopen(req, timeout=0):
    url = req.full_url if hasattr(req, "full_url") else req
    if url.endswith(".csv"):
        return _FakeResp(b"day,type,value_buy,value_sell\n2011-01-15,Blue,4,4\n")
    return _FakeResp(json.dumps({"data": [["2016-12-01", 100.0]]}).encode())


def test_main_success(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)
    runpy.run_module("pipeline.fetch", run_name="__main__")
    assert (tmp_path / "raw" / "bluelytics_evolution.csv").exists()


def test_main_error_exits_1(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(config, "RAW_DIR", tmp_path / "raw")

    def _raise(req, timeout=0):
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(urllib.request, "urlopen", _raise)
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("pipeline.fetch", run_name="__main__")
    assert exc.value.code == 1
    assert "ERROR" in capsys.readouterr().err
