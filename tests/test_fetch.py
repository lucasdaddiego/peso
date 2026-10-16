"""read_series paging + mixed-replica pages, fetch_series picking the most complete read + its two
failure modes (no `data` key, empty series), fetch() writing every
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


def test_read_series_pages(monkeypatch):
    monkeypatch.setattr(fetch, "_PAGE", 2)
    pages = [
        json.dumps({"count": 3, "data": [["2000-01-01", 1], ["2000-02-01", 2]]}).encode(),  # full page -> continue
        json.dumps({"count": 3, "data": [["2000-03-01", 3]]}).encode(),  # short page -> stop
    ]
    calls = iter(pages)
    monkeypatch.setattr(fetch, "_get", lambda url: next(calls))
    rows = fetch.read_series("any-id", "1950-01-01")
    assert rows == [["2000-01-01", 1], ["2000-02-01", 2], ["2000-03-01", 3]]


def test_read_series_rejects_pages_from_disagreeing_replicas(monkeypatch):
    monkeypatch.setattr(fetch, "_PAGE", 2)
    pages = iter(
        [
            json.dumps({"count": 3, "data": [["2000-01-01", 1], ["2000-02-01", 2]]}).encode(),
            json.dumps({"count": 2, "data": [["2000-04-01", 4]]}).encode(),  # a stale replica's page 2
        ]
    )
    monkeypatch.setattr(fetch, "_get", lambda url: next(pages))
    with pytest.raises(fetch.MixedRead, match="count=2"):
        fetch.read_series("any-id", "1950-01-01")


def _reads(*reads: list) -> object:
    """A fake _get that answers one single-page read per call, in order."""
    answers = iter(json.dumps({"count": len(r), "data": r}).encode() for r in reads)
    return lambda url: next(answers)


# The 2026-10-15 shapes, scaled down: an empty replica, one missing the first month with a null,
# and the healthy one. One read in three was stale, so a single read failed `make data` most days.
_HEALTHY = [["1993-01-01", 1.0], ["1993-02-01", 2.0], ["1993-03-01", 3.0]]
_STALE = [["1993-02-01", 2.0], ["1993-03-01", None]]


def test_fetch_series_keeps_the_most_complete_read(monkeypatch, capsys):
    monkeypatch.setattr(fetch, "_get", _reads([], _STALE, _HEALTHY, _STALE, *[[]] * (fetch.READS - 4)))
    assert fetch.fetch_series("any-id") == _HEALTHY
    assert "values per read [0, 1, 3, 1, 0," in capsys.readouterr().err


def test_each_read_has_its_own_url(monkeypatch):
    # The API caches by exact URL: a repeated URL repeats the stale answer, so every read and every
    # run must ask a URL of its own, with a start_date that filters nothing.
    urls: list[str] = []
    monkeypatch.setattr(fetch, "_get", lambda url: urls.append(url) or json.dumps({"data": _HEALTHY}).encode())
    fetch.fetch_series("any-id")
    assert len(urls) == fetch.READS == len(set(urls))
    years = [int(u.split("start_date=")[1][:4]) for u in urls]
    assert all(y < 1992 for y in years)
    dates = fetch.no_op_start_dates(len(fetch.NO_OP_START_YEARS))
    assert len(set(dates)) == len(dates)


def test_fetch_series_is_quiet_when_every_read_agrees(monkeypatch, capsys):
    monkeypatch.setattr(fetch, "_get", _reads(*[_HEALTHY] * fetch.READS))
    assert fetch.fetch_series("any-id") == _HEALTHY
    assert capsys.readouterr().err == ""


def test_fetch_series_discards_a_mixed_read(monkeypatch, capsys):
    monkeypatch.setattr(fetch, "_PAGE", 3)
    answers = iter(
        [json.dumps({"count": 4, "data": _HEALTHY}).encode(), json.dumps({"count": 1, "data": []}).encode()]
        + [json.dumps({"count": 2, "data": _HEALTHY[:2]}).encode()] * (fetch.READS - 1)
    )
    monkeypatch.setattr(fetch, "_get", lambda url: next(answers))
    assert fetch.fetch_series("any-id") == _HEALTHY[:2]
    assert "discarded a read" in capsys.readouterr().err


def test_fetch_series_fails_on_api_error_payload(monkeypatch):
    # datos.gob.ar answers a retired id with {"errors": [...]} and no `data`; this used to be saved
    # as [] and surface later as "splice gap: 1993-02". No second read: it is not replica skew.
    payload = {"errors": [{"error": "Serie inexistente: 999.9_NOPE"}], "failed_series": ["999.9_NOPE"]}
    calls: list[str] = []
    monkeypatch.setattr(fetch, "_get", lambda url: calls.append(url) or json.dumps(payload).encode())
    with pytest.raises(ValueError, match=r"no 'data' key.*Serie inexistente"):
        fetch.fetch_series("999.9_NOPE")
    assert len(calls) == 1


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


def test_fetch_asks_the_api_to_collapse_only_the_fx_series(tmp_path, monkeypatch):
    # Paging the daily FX series lost 2005-09…2011-03 on 2026-10-15 (page 2 started at 2011-03).
    # The API's monthly end-of-period collapse fits one page; the CPI series are monthly already.
    monkeypatch.setattr(config, "RAW_DIR", tmp_path / "raw")
    urls: list[str] = []
    monkeypatch.setattr(fetch, "_get", lambda url: urls.append(url) or _fake_get(url))
    fetch.fetch()
    collapsed = {u.split("ids=")[1].split("&")[0] for u in urls if config.FX_COLLAPSE in u}
    assert collapsed == {config.FX_OFICIAL_ID}
    assert "collapse_aggregation=end_of_period" in config.FX_COLLAPSE


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
