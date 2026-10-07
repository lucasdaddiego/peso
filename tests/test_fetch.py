"""fetch_series paging + its two failure modes (no `data` key, empty series), fetch() writing every
snapshot, the retrying urlopen wrapper, and the __main__ success + error->exit(1) paths. Never
touches the network, never sleeps (time.sleep is patched)."""

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


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """The backoff must never slow the suite down; record the delays instead."""
    delays: list[float] = []
    monkeypatch.setattr(fetch.time, "sleep", delays.append)
    return delays


def test_get_wraps_urlopen(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=0: _FakeResp(b"HELLO"))
    assert fetch._get("https://example/x") == b"HELLO"


def test_get_retries_with_backoff_then_succeeds(monkeypatch, _no_sleep, capsys):
    attempts = iter([urllib.error.URLError("reset"), TimeoutError("slow"), _FakeResp(b"OK")])

    def _urlopen(req, timeout=0):
        nxt = next(attempts)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt

    monkeypatch.setattr(urllib.request, "urlopen", _urlopen)
    assert fetch._get("https://example/x") == b"OK"
    assert _no_sleep == [2.0, 4.0]  # exponential: 2 s, then 4 s
    assert "attempt 1/3" in capsys.readouterr().err


def test_get_gives_up_after_three_attempts(monkeypatch, _no_sleep):
    calls = 0

    def _urlopen(req, timeout=0):
        nonlocal calls
        calls += 1
        raise urllib.error.HTTPError(req.full_url, 503, "unavailable", None, None)  # type: ignore[arg-type]

    monkeypatch.setattr(urllib.request, "urlopen", _urlopen)
    with pytest.raises(RuntimeError, match="failed after 3 attempts"):
        fetch._get("https://example/x")
    assert calls == 3
    assert _no_sleep == [2.0, 4.0]  # no sleep after the last attempt


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


def test_fetch_series_fails_on_api_error_payload(monkeypatch):
    # datos.gob.ar answers a retired id with {"errors": [...]} and no `data`; this used to be saved
    # as [] and surface later as "splice gap: 1993-02".
    payload = {"errors": [{"error": "Serie inexistente: 999.9_NOPE"}], "failed_series": ["999.9_NOPE"]}
    monkeypatch.setattr(fetch, "_get", lambda url: json.dumps(payload).encode())
    with pytest.raises(ValueError, match=r"no 'data' key.*Serie inexistente"):
        fetch.fetch_series("999.9_NOPE")


def test_fetch_series_fails_on_non_object_payload(monkeypatch):
    monkeypatch.setattr(fetch, "_get", lambda url: b"[]")
    with pytest.raises(ValueError, match="no 'data' key"):
        fetch.fetch_series("any-id")


def test_fetch_series_fails_on_empty_first_page(monkeypatch):
    monkeypatch.setattr(fetch, "_get", lambda url: json.dumps({"data": []}).encode())
    with pytest.raises(ValueError, match="empty series"):
        fetch.fetch_series("any-id")


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
# (urllib.request.urlopen, time.sleep) survive into the __main__ run, so the entrypoint tests patch there.
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
    monkeypatch.setattr("time.sleep", lambda s: None)  # the fresh module binds the real time.sleep

    def _raise(req, timeout=0):
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(urllib.request, "urlopen", _raise)
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("pipeline.fetch", run_name="__main__")
    assert exc.value.code == 1
    assert "ERROR" in capsys.readouterr().err
