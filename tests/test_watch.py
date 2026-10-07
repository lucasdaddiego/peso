"""The IPC vintage watch: month labels, the newest-month probe (urllib mocked), issue/PR text,
GitHub-output emission, detect() across every status x health combo, apply_bump (nothing newer /
success / missing field / missing anchor) and main()/__main__. Offline."""

from __future__ import annotations

import json
import runpy
import urllib.error
import urllib.request

import pytest

from pipeline import config, watch

# runpy.run_module on an already-imported package warns harmlessly; ignore just that.
pytestmark = pytest.mark.filterwarnings("ignore:.*found in sys.modules:RuntimeWarning")


class _FakeHTTP:
    def __init__(self, body: bytes):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self) -> bytes:
        return self._body


def _api(body) -> bytes:
    return json.dumps(body).encode()


# --- pure helpers ---


def test_month_label():
    assert watch.month_label("2026-08") == "agosto 2026"
    assert watch.month_label("2025-12") == "diciembre 2025"


# --- latest_published_month (mocked urllib) ---


def test_latest_published_month_reads_the_newest_row(monkeypatch):
    monkeypatch.setattr(
        urllib.request, "urlopen", lambda req, timeout=0: _FakeHTTP(_api({"data": [["2026-08-01", 12276.8]]}))
    )
    assert watch.latest_published_month() == "2026-08"


@pytest.mark.parametrize(
    "body",
    [
        {"errors": [{"error": "Serie inexistente"}]},  # API error payload: no `data`
        {"data": []},  # empty series
        {"data": [[]]},  # malformed row
        {"data": ["2026-08-01"]},  # row is not a list
        {"data": [["not-a-date", 1]]},  # malformed date
        [],  # not an object at all
    ],
)
def test_latest_published_month_rejects_bad_payloads(monkeypatch, body):
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=0: _FakeHTTP(_api(body)))
    assert watch.latest_published_month() is None


@pytest.mark.parametrize("exc", [urllib.error.URLError("down"), OSError("boom"), ValueError("bad json")])
def test_latest_published_month_network_or_parse_error(monkeypatch, exc):
    def _raise(req, timeout=0):
        raise exc

    monkeypatch.setattr(urllib.request, "urlopen", _raise)
    assert watch.latest_published_month() is None


# --- issue_title / issue_body / pr_body ---


def test_issue_title_all_statuses():
    assert "bump the vintage" in watch.issue_title("new_month")
    assert "unreachable" in watch.issue_title("source_unreachable")
    assert "reproducibility check failed" in watch.issue_title("up_to_date")


def test_issue_body_source_unreachable_with_health():
    body = watch.issue_body("source_unreachable", None, health_failed=True)
    assert config.IPC_NACIONAL_ID in body
    assert "did not answer" in body
    assert "reproducibility check" in body  # health section appended
    assert "Newest published month" not in body  # unknown here


def test_issue_body_health_only_names_the_newest_month():
    body = watch.issue_body("health_failed", "2026-08", health_failed=True)
    assert "did not answer" not in body
    assert "Newest published month: 2026-08" in body


def test_issue_body_up_to_date_without_health_is_empty():
    assert watch.issue_body("up_to_date", "2026-05", health_failed=False).strip() == ""


def test_pr_body_mentions_the_bump_and_the_missing_anchor():
    body = watch.pr_body("2026-05", "2026-12", [2026], data_ok=False)
    assert "2026-05 → 2026-12" in body
    assert 'VINTAGE_LABEL = "diciembre 2026"' in body
    assert "INDEC_NACIONAL_ANNUAL[2026]" in body
    assert "**failed** in the workflow" in body
    assert "does not trigger CI" in body


def test_pr_body_clean_bump():
    body = watch.pr_body("2026-05", "2026-08", [], data_ok=True)
    assert "[x] `make data` passed" in body
    assert "INDEC_NACIONAL_ANNUAL" not in body
    assert "Datos hasta agosto 2026" in body


# --- emit_outputs ---


def test_emit_outputs_no_env(monkeypatch):
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    watch.emit_outputs({"a": "1"})  # returns early, nothing to assert beyond no crash


def test_emit_outputs_writes(tmp_path, monkeypatch):
    gho = tmp_path / "out.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(gho))
    watch.emit_outputs({"a": "1", "b": "two"})
    assert gho.read_text() == "a=1\nb=two\n"


# --- detect (status x health matrix) ---


def _run_detect(monkeypatch, tmp_path, *, latest, health=False):
    monkeypatch.setattr(config, "DATA_VINTAGE", "2026-05")
    monkeypatch.setattr(watch, "latest_published_month", lambda series_id=None: latest)
    body = tmp_path / "body.md"
    gho = tmp_path / "gh.txt"
    monkeypatch.setenv("ISSUE_BODY_FILE", str(body))
    monkeypatch.setenv("GITHUB_OUTPUT", str(gho))
    if health:
        monkeypatch.setenv("HEALTH_OUTCOME", "failure")
    else:
        monkeypatch.delenv("HEALTH_OUTCOME", raising=False)
    rc = watch.detect()
    outputs = dict(line.split("=", 1) for line in gho.read_text().splitlines())
    return rc, outputs, body


def test_detect_new_month(monkeypatch, tmp_path):
    rc, out, body = _run_detect(monkeypatch, tmp_path, latest="2026-08")
    assert rc == 0
    assert out["status"] == "new_month"
    assert out["next_vintage"] == "2026-08"
    assert out["next_label"] == "agosto 2026"
    assert out["needs_issue"] == "false"  # a PR handles the bump, not an issue
    assert not body.exists()


def test_detect_source_unreachable(monkeypatch, tmp_path):
    rc, out, body = _run_detect(monkeypatch, tmp_path, latest=None)
    assert rc == 0
    assert out["status"] == "source_unreachable"
    assert out["needs_issue"] == "true"
    assert out["next_vintage"] == "" and out["next_label"] == ""
    assert body.exists() and config.IPC_NACIONAL_ID in body.read_text()


def test_detect_up_to_date(monkeypatch, tmp_path):
    rc, out, body = _run_detect(monkeypatch, tmp_path, latest="2026-05")
    assert rc == 0
    assert out["status"] == "up_to_date"
    assert out["needs_issue"] == "false"
    assert not body.exists()


def test_detect_up_to_date_with_health_failure(monkeypatch, tmp_path):
    rc, out, body = _run_detect(monkeypatch, tmp_path, latest="2026-05", health=True)
    assert rc == 0
    assert out["status"] == "up_to_date"
    assert out["needs_issue"] == "true"  # health failure still raises an issue
    assert body.exists() and "reproducibility check" in body.read_text()


def test_detect_new_month_with_health_failure(monkeypatch, tmp_path):
    """A pending bump must not swallow a failed reproducibility check of the current vintage."""
    rc, out, body = _run_detect(monkeypatch, tmp_path, latest="2026-08", health=True)
    assert rc == 0
    assert out["status"] == "new_month"  # the PR step still runs
    assert out["needs_issue"] == "true"
    assert "reproducibility check failed" in out["issue_title"]
    assert body.exists() and "reproducibility check" in body.read_text()


# --- apply_bump ---

_CONFIG_TEMPLATE = """\
DATA_VINTAGE = "2026-05"
VINTAGE_LABEL = "mayo 2026"
"""


def _fake_config_root(tmp_path, template=_CONFIG_TEMPLATE):
    root = tmp_path / "root"
    (root / "pipeline").mkdir(parents=True)
    (root / "pipeline" / "config.py").write_text(template, encoding="utf-8")
    return root


def _apply_setup(tmp_path, monkeypatch, *, latest, template=_CONFIG_TEMPLATE):
    root = _fake_config_root(tmp_path, template)
    monkeypatch.setattr(config, "DATA_VINTAGE", "2026-05")
    monkeypatch.setattr(config, "ROOT", root)
    monkeypatch.setattr(watch, "latest_published_month", lambda series_id=None: latest)
    return root


@pytest.mark.parametrize("latest", [None, "2026-05", "2026-04"])
def test_apply_bump_nothing_newer(tmp_path, monkeypatch, capsys, latest):
    root = _apply_setup(tmp_path, monkeypatch, latest=latest)
    assert watch.apply_bump() == 1
    assert "nothing to do" in capsys.readouterr().err
    assert (root / "pipeline" / "config.py").read_text() == _CONFIG_TEMPLATE  # untouched


def test_apply_bump_success(tmp_path, monkeypatch, capsys):
    root = _apply_setup(tmp_path, monkeypatch, latest="2026-08")
    assert watch.apply_bump() == 0
    rewritten = (root / "pipeline" / "config.py").read_text()
    assert 'DATA_VINTAGE = "2026-08"' in rewritten
    assert 'VINTAGE_LABEL = "agosto 2026"' in rewritten
    compile(rewritten, "config.py", "exec")  # still importable Python
    assert "anchors still needed" not in capsys.readouterr().out  # 2025 is anchored, 2026 incomplete


def test_apply_bump_crossing_a_year_end_names_the_anchor(tmp_path, monkeypatch, capsys):
    _apply_setup(tmp_path, monkeypatch, latest="2027-01")
    assert watch.apply_bump() == 0
    assert "anchors still needed for: 2026" in capsys.readouterr().out


def test_apply_bump_missing_field_returns_2(tmp_path, monkeypatch, capsys):
    _apply_setup(tmp_path, monkeypatch, latest="2026-08", template='DATA_VINTAGE = "2026-05"\n')  # no label line
    assert watch.apply_bump() == 2
    assert "expected exactly one 'VINTAGE_LABEL" in capsys.readouterr().err


# --- write_pr_body (after --apply + make data: config already holds the new pin) ---


def test_write_pr_body_clean_bump(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(config, "DATA_VINTAGE", "2026-08")
    monkeypatch.setenv("PREV_VINTAGE", "2026-05")
    monkeypatch.delenv("DATA_OUTCOME", raising=False)  # unset reads as success
    monkeypatch.setenv("PR_BODY_FILE", str(tmp_path / "pr.md"))
    assert watch.write_pr_body() == 0
    pr = (tmp_path / "pr.md").read_text()
    assert "2026-05 → 2026-08" in pr
    assert "[x] `make data` passed" in pr
    assert "INDEC_NACIONAL_ANNUAL" not in pr
    assert "make data passed" in capsys.readouterr().out


def test_write_pr_body_failed_build_and_missing_anchor(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_VINTAGE", "2027-01")
    monkeypatch.setenv("PREV_VINTAGE", "2026-05")
    monkeypatch.setenv("DATA_OUTCOME", "failure")
    monkeypatch.setenv("PR_BODY_FILE", str(tmp_path / "pr.md"))
    assert watch.write_pr_body() == 0
    pr = (tmp_path / "pr.md").read_text()
    assert "INDEC_NACIONAL_ANNUAL[2026]" in pr
    assert "**failed** in the workflow" in pr


# --- main() dispatch + __main__ ---


def test_main_detect(monkeypatch):
    monkeypatch.setattr("sys.argv", ["watch"])
    monkeypatch.setattr(watch, "detect", lambda: 0)
    monkeypatch.setattr(watch, "apply_bump", lambda: pytest.fail("apply_bump must not run"))
    assert watch.main() == 0


def test_main_apply(monkeypatch):
    monkeypatch.setattr("sys.argv", ["watch", "--apply"])
    monkeypatch.setattr(watch, "apply_bump", lambda: 7)
    monkeypatch.setattr(watch, "detect", lambda: pytest.fail("detect must not run"))
    assert watch.main() == 7


def test_main_pr_body(monkeypatch):
    monkeypatch.setattr("sys.argv", ["watch", "--pr-body"])
    monkeypatch.setattr(watch, "write_pr_body", lambda: 3)
    monkeypatch.setattr(watch, "detect", lambda: pytest.fail("detect must not run"))
    assert watch.main() == 3


def test_dunder_main_runs_detect(monkeypatch, tmp_path):
    # __main__ -> main() -> detect(); keep it offline by mocking urlopen (newest month == vintage ->
    # up_to_date -> no issue body written) and unsetting GITHUB_OUTPUT.
    monkeypatch.setattr("sys.argv", ["watch"])
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda req, timeout=0: _FakeHTTP(_api({"data": [[f"{config.DATA_VINTAGE}-01", 1.0]]})),
    )
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    monkeypatch.delenv("HEALTH_OUTCOME", raising=False)
    monkeypatch.setenv("ISSUE_BODY_FILE", str(tmp_path / "body.md"))
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("pipeline.watch", run_name="__main__")
    assert exc.value.code == 0
