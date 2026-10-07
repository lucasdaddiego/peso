"""Data-maintenance helper, run monthly by .github/workflows/data-update.yml.

The series are vintage-pinned (config.DATA_VINTAGE), so a newly published month changes nothing
until someone bumps the pin. INDEC publishes the IPC of month M around the middle of month M+1;
this watch notices and proposes the bump.

Two modes:
  (default)  detect — is a month newer than the vintage published in the INDEC IPC Nacional series
             (the series that closes the splice)? Probes the datos.gob.ar API for its newest row
             (no full download) and emits GitHub step outputs. Also checks the pinned sources
             still answer, and relays a failed reproducibility check (HEALTH_OUTCOME) as an issue.
  --apply    bump   — rewrite DATA_VINTAGE and VINTAGE_LABEL in config.py to the newest published
             month. The workflow then runs `make data`.
  --pr-body  after the bump and `make data`: write the PR body from the rewritten pin, the
             PREV_VINTAGE and DATA_OUTCOME env vars, and the anchors the new vintage still needs.

When `make data` passes, the workflow pushes the bump straight to master (the push deploys); otherwise
it opens a draft PR. The bump is only mechanical. When the new vintage completes a calendar year (it covers a December
with no Dec–Dec anchor yet), `make data` fails on validate.missing_anchor_years until a human adds
that year's INDEC figure to config.INDEC_NACIONAL_ANNUAL; the PR body says which year.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections.abc import Callable

from . import config, validate

UA = "Mozilla/5.0 (peso data-watch)"
TIMEOUT = 60
PINNED_FIELDS = ("DATA_VINTAGE", "VINTAGE_LABEL")
MONTH_NAMES_ES = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)
MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def month_label(month: str) -> str:
    """'2026-08' -> 'agosto 2026' (the VINTAGE_LABEL convention)."""
    return f"{MONTH_NAMES_ES[int(month[5:7]) - 1]} {month[:4]}"


def latest_published_month(series_id: str = config.IPC_NACIONAL_ID) -> str | None:
    """The newest month ('YYYY-MM') the API holds for `series_id`, or None when it cannot be read.

    One row, newest first: the API's `sort=desc` + `limit=1`. A payload without `data` (an API
    error, a retired id) or with a malformed date reads as unreachable, never as "up to date".
    """
    url = f"{config.SERIES_API}?ids={series_id}&format=json&limit=1&sort=desc"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            payload = json.loads(resp.read())
    except urllib.error.URLError, OSError, ValueError:
        return None
    data = payload.get("data") if isinstance(payload, dict) else None
    if not data or not isinstance(data[0], list) or not data[0]:
        return None
    month = str(data[0][0])[:7]
    return month if MONTH_RE.match(month) else None


def issue_title(status: str) -> str:
    if status == "new_month":
        return f"Data: IPC {config.DATA_VINTAGE} is stale — bump the vintage"
    if status == "source_unreachable":
        return "Data: the INDEC IPC series on datos.gob.ar is unreachable"
    return f"Data: monthly reproducibility check failed (vintage {config.DATA_VINTAGE})"


def issue_body(status: str, latest: str | None, health_failed: bool) -> str:
    parts: list[str] = []
    if status == "source_unreachable":
        parts.append(
            f"The INDEC IPC Nacional series (`{config.IPC_NACIONAL_ID}`) did not answer on datos.gob.ar:\n\n"
            f"```\n{config.SERIES_API}?ids={config.IPC_NACIONAL_ID}\n```\n\n"
            "The id may have been retired or the API may be down. Verify `IPC_NACIONAL_ID` and "
            "`SERIES_API` in `pipeline/config.py`."
        )
    if health_failed:
        parts.append(
            "---\n"
            f"⚠️ The monthly reproducibility check (`make data` at vintage **{config.DATA_VINTAGE}**) "
            "**failed**: a source revised a past month, a fetch failed, or an anchor no longer "
            "reproduces. See the workflow run log for details."
            + (f" Newest published month: {latest}." if latest else "")
        )
    return "\n\n".join(parts) + "\n"


def pr_body(current: str, latest: str, missing_years: list[int], data_ok: bool) -> str:
    anchors = (
        "- [x] `make data` passed: the spliced series reproduces every anchor at the new vintage.\n"
        if data_ok
        else "- [ ] `make data` **failed** in the workflow; see its log. Run it locally and push the fix.\n"
    )
    if missing_years:
        years = ", ".join(str(y) for y in missing_years)
        anchors += (
            f"- [ ] The new vintage completes **{years}**: add `INDEC_NACIONAL_ANNUAL[{years}]` in "
            "`pipeline/config.py` with the Dec–Dec figure from INDEC's January IPC release "
            "(https://www.indec.gob.ar/indec/web/Nivel4-Tema-3-5-31), then run `make data` and push.\n"
        )
    return (
        f"Mechanical bump of the data vintage **{current} → {latest}**, applied automatically "
        f"(`DATA_VINTAGE`, `VINTAGE_LABEL`, both copies of `series.v1.json`).\n\n"
        "### Done by this PR\n"
        f'- `pipeline/config.py`: `DATA_VINTAGE = "{latest}"`, `VINTAGE_LABEL = "{month_label(latest)}"`\n'
        "- `data/series.v1.json` + `web/public/series.v1.json`: rebuilt by `make data`\n\n"
        "### Before merging (human)\n"
        f"{anchors}"
        "- [ ] Check the headline on the preview: the page must say «Datos hasta "
        f"{month_label(latest)}».\n\n"
        "> A PR opened with the workflow token does not trigger CI. Push an empty commit "
        "(`git commit --allow-empty -m 'ci'`) or close and reopen the PR to run the checks."
    )


def emit_outputs(outputs: dict[str, str]) -> None:
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if not gh_out:
        return
    with open(gh_out, "a", encoding="utf-8") as f:
        for key, value in outputs.items():
            f.write(f"{key}={value}\n")


def detect() -> int:
    latest = latest_published_month()
    health_failed = os.environ.get("HEALTH_OUTCOME", "") == "failure"

    if latest is None:
        status = "source_unreachable"
    elif latest > config.DATA_VINTAGE:
        status = "new_month"
    else:
        status = "up_to_date"

    # A PR handles a new month; issues are only for "go investigate" cases. A failed reproducibility
    # check is one of those even while a bump is pending: the bump PR does not report it, and the
    # health step is continue-on-error, so the run would otherwise stay green.
    needs_issue = status == "source_unreachable" or health_failed
    issue_status = "health_failed" if status == "new_month" else status
    body_file = os.environ.get("ISSUE_BODY_FILE", "ipc-watch-body.md")
    if needs_issue:
        with open(body_file, "w", encoding="utf-8") as f:
            f.write(issue_body(issue_status, latest, health_failed))

    emit_outputs(
        {
            "status": status,
            "needs_issue": str(needs_issue).lower(),
            "issue_title": issue_title(issue_status),
            "issue_body_file": body_file,
            "current_vintage": config.DATA_VINTAGE,
            "next_vintage": latest or "",
            "next_label": month_label(latest) if latest else "",
        }
    )

    print(f"[watch] pinned vintage : {config.DATA_VINTAGE}")
    print(f"[watch] newest month   : {latest or 'UNREACHABLE'}")
    print(f"[watch] health check   : {'failed' if health_failed else 'ok / n-a'}")
    print(f"[watch] status         : {status}  (issue={needs_issue})")
    return 0


def literal(replacement: str) -> Callable[[re.Match[str]], str]:
    """An re.sub replacement *callable*, which inserts `replacement` verbatim (a replacement string
    would re-read its backslash escapes)."""
    return lambda _m: replacement


def apply_bump() -> int:
    """Rewrite config.py's vintage pin to the newest published month."""
    latest = latest_published_month()
    if latest is None or latest <= config.DATA_VINTAGE:
        print(f"[apply] nothing newer than {config.DATA_VINTAGE} (newest: {latest}) — nothing to do.", file=sys.stderr)
        return 1

    values = {"DATA_VINTAGE": latest, "VINTAGE_LABEL": month_label(latest)}
    cfg_path = config.ROOT / "pipeline" / "config.py"
    text = cfg_path.read_text(encoding="utf-8")
    for name in PINNED_FIELDS:
        text, n = re.subn(rf'(?m)^{name} = ".*"$', literal(f'{name} = "{values[name]}"'), text)
        if n != 1:
            print(f"[apply] ERROR: expected exactly one '{name} = ...' line, found {n}.", file=sys.stderr)
            return 2
    cfg_path.write_text(text, encoding="utf-8")

    for name in PINNED_FIELDS:
        print(f"[apply] {name} = {values[name]!r}")
    missing = validate.missing_anchor_years(latest)
    if missing:
        print(f"[apply] anchors still needed for: {', '.join(map(str, missing))}")
    return 0


def write_pr_body() -> int:
    """Write the bump PR body. Runs after --apply and `make data`, so config holds the new pin."""
    prev = os.environ.get("PREV_VINTAGE", "?")
    data_ok = os.environ.get("DATA_OUTCOME", "success") == "success"
    missing = validate.missing_anchor_years(config.DATA_VINTAGE)
    body_file = os.environ.get("PR_BODY_FILE", "ipc-bump-pr-body.md")
    with open(body_file, "w", encoding="utf-8") as f:
        f.write(pr_body(prev, config.DATA_VINTAGE, missing, data_ok))
    print(f"[pr-body] {prev} → {config.DATA_VINTAGE}, make data {'passed' if data_ok else 'FAILED'}, wrote {body_file}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="IPC vintage watcher / bump helper")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="rewrite the vintage pin to the newest published month")
    mode.add_argument("--pr-body", action="store_true", help="write the bump PR body (after --apply and `make data`)")
    args = parser.parse_args()
    if args.apply:
        return apply_bump()
    if args.pr_body:
        return write_pr_body()
    return detect()


if __name__ == "__main__":
    raise SystemExit(main())
