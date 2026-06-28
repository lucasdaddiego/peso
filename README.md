# peso

[![Live demo](https://img.shields.io/badge/demo-live-F38020?logo=cloudflare&logoColor=white)](https://peso.pages.dev)
[![CI (web)](https://github.com/lucasdaddiego/peso/actions/workflows/ci.yml/badge.svg)](https://github.com/lucasdaddiego/peso/actions/workflows/ci.yml)
[![Python checks](https://github.com/lucasdaddiego/peso/actions/workflows/python.yml/badge.svg)](https://github.com/lucasdaddiego/peso/actions/workflows/python.yml)
[![Data reproduces INDEC/BCRA](https://github.com/lucasdaddiego/peso/actions/workflows/data.yml/badge.svg)](https://github.com/lucasdaddiego/peso/actions/workflows/data.yml)

[![Coverage 100%](https://img.shields.io/badge/coverage-100%25-brightgreen)](https://github.com/lucasdaddiego/peso/actions)
[![Python 3.14](https://img.shields.io/badge/python-3.14-3776AB?logo=python&logoColor=white)](pyproject.toml)
[![TypeScript](https://img.shields.io/badge/TypeScript-strict-3178C6?logo=typescript&logoColor=white)](web/tsconfig.json)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**What is X pesos from year Y worth today?** This tool answers it from **real INDEC and BCRA
data** — it downloads the official consumer-price and exchange-rate series, splices them into one
continuous monthly index, and converts any past peso amount into today's purchasing power, plus its
value in dollars at the official **and** blue (informal) rates. No eyeballed inflation, no single
broken series across the years the INDEC was intervened.

**▶ Try it live: [peso.pages.dev](https://peso.pages.dev)**

<!-- screenshot placeholder: drop docs/demo.png and uncomment once deployed
![peso — what is X pesos from year Y worth today?](docs/demo.png)
-->

> **Validated to the official figures.** The spliced index reproduces INDEC's published Dec–Dec
> inflation for 2017–2024 **to the decimal** (24.8 · 47.6 · 53.8 · 36.1 · 50.9 · 94.8 · 211.4 ·
> 117.8 %), the IPC-GBA 2002 collapse (40.9 %), and 1:1 convertibility FX — with an independent
> cross-check that **$1.000 of January 2003 ≈ $1.65M today**.

It has two parts:

1. **`pipeline/`** — an offline, reproducible Python pipeline (uv + pandas + numpy) that fetches the
   real source series, **splices** them, validates against known anchors, and emits one small,
   provenance-stamped JSON artifact.
2. **`web/`** — a static Vite + TypeScript site that reads that JSON and renders honest graphics
   (purchasing-power decay, the official-vs-blue dollar gap, annual/monthly inflation, the spliced
   index itself) plus the USD divergence — all lookups, no client-side statistics.

## What makes it "real"

- **The splice is the point.** INDEC's CPI was statistically intervened ~2007–2015, understating
  inflation badly. Using the official numbers for that decade would overstate what old pesos are
  worth. So the index stitches **IPC-GBA (1993–2006, official) → IPC San Luis (2007–2016, the
  credible provincial alternative) → IPC Nacional (2016–today, official)**, chained by
  month-over-month growth, and documents every breakpoint.
- **Two dollars, honestly.** Official (BCRA reference rate, from 1992) and blue (Bluelytics, from
  2011). Before the cepo there was no real parallel market, so blue is set equal to official and
  flagged as such — never faked.
- **Computed once, offline.** The frontend does no statistics: it looks up the precomputed monthly
  index and rates. Everything quantitative is in the committed artifact.
- **Provenance + a validation gate.** Each series is pinned by id; the build **fails** if it stops
  reproducing the official Dec–Dec figures, the convertibility peg, or the cumulative cross-check.
- **Vintage-pinned.** Every series is truncated to a fixed month, so the build is reproducible no
  matter when it runs.

## Quickstart

```bash
make setup        # uv sync (python deps) + npm install (web deps)
make data         # fetch → splice (build JSON) → validate (vs INDEC/BCRA)
make test         # python + web unit tests, each gated at 100% coverage
make lint         # ruff + mypy + tsc
make up           # vite dev server  →  http://localhost:5180
make build        # static bundle in web/dist/
make deploy       # publish web/dist/ to Cloudflare Pages (needs wrangler auth)
```

`make` (or `make help`) lists every target. `make data` fetches the INDEC IPC series (GBA, San
Luis, Nacional), the BCRA reference dollar and the Bluelytics history, writes
`data/series.v1.json` and `web/public/series.v1.json`, and asserts the reproduction of the official
numbers. The steps can also be run one at a time with `uv run python -m pipeline.{fetch,build,validate}`.

## How it works

```
datos.gob.ar (INDEC IPC ×3, BCRA dólar)  +  Bluelytics (blue)
   └─ pipeline/  fetch → splice (chain MoM, rebase to 100) → validate → emit
        └─ web/public/series.v1.json   (versioned, provenance-stamped)
             └─ web/  Vite + TS + Observable Plot  (lookups + honest charts only)
```

The equivalent today of `X` pesos of month `m` is simply `X × 100 / CPI[m]`, where the spliced
index is rebased so the latest month = 100. USD endpoints divide by that month's official or blue
rate.

## Methodology (short)

- **Splice.** IPC-GBA (1993–2006) · IPC San Luis (2007–2016, the intervened decade) · IPC Nacional
  (2016–today), chained by month-over-month growth with a one-month overlap at each breakpoint,
  rebased so today = 100.
- **FX.** BCRA reference dollar (official, from 1992) + Bluelytics (blue, from 2011; pre-cepo blue
  := official).
- **Validation.** Reproduces INDEC Dec–Dec 2017–2024, San Luis 2007–2015, GBA 2002, convertibility
  1:1, and a cumulative cross-check — or the build fails.
- Full notes: [`docs/metodologia.md`](docs/metodologia.md), and the "Metodología" section in the app.

## Project structure

```
pipeline/   config (pinned series + anchors) · fetch · load · splice · build · validate · artifact_check
tests/      pytest suite for pipeline/ — offline, synthetic fixtures, 100% statement+branch coverage
data/       series.v1.json   (raw/ is gitignored)
web/        index.html · src/{main,charts,inflation,format,usd,types}.ts · styles.css · test/ (vitest, 100%)
docs/       metodologia.md
```

## Tests & CI

Both layers are gated at **100% coverage** — statements **and** branches:

- **`pipeline/`** — `pytest` against tiny synthetic series (no network), 45 tests.
- **`web/src/`** — `vitest` + `jsdom`, every render path exercised against the committed artifact, 50 tests.

`make test` runs both; `make lint` runs `ruff` + `mypy` + `tsc`. Three GitHub Actions enforce it,
path-filtered so a web-only change never reaches for the data sources:

| Workflow | What it checks |
| --- | --- |
| `ci.yml` | web typecheck + `vitest` 100% gate + production build |
| `python.yml` | `ruff` + `mypy` + `pytest` 100% gate (offline, fast) |
| `data.yml` | the pipeline still reproduces INDEC/BCRA, and the committed artifact matches the rebuild |

## Reproducibility

The series are **vintage-pinned** in `pipeline/config.py` (`DATA_VINTAGE`): every month at or
before the vintage is fixed, so a fresh fetch reproduces the committed artifact even as the upstream
APIs append new months. To update to a newer month, bump `DATA_VINTAGE`, run `make data`, and commit
the regenerated JSON. If a source ever revises a *past* month, `data.yml` flags the drift.

## Deploy

Static bundle + one JSON → ideal for **Cloudflare Pages** (`web/dist/`, headers in
`web/public/_headers`). Published manually with `make deploy`.

## A note on the data

The rigorous spine — the spliced CPI and the official FX — is validated to published figures. The
one **judgement call** is using **IPC San Luis** for 2007–2015: it's a credible provincial
alternative to the discredited official series, but it's one choice among several (IPC Congreso,
CABA, other provinces) that tell the same story with slightly different numbers. The README and the
app surface this honestly; the alternative is documented and swappable in `config.py`.

## License

**Code:** [MIT](LICENSE). · **Data:** see [`NOTICE`](NOTICE).

> Elaboración propia en base a series oficiales del INDEC (IPC) y del BCRA (tipo de cambio), vía
> datos.gob.ar, empalmadas con el IPC de San Luis para el período de intervención del INDEC
> (2007–2015), y cotización informal histórica de Bluelytics.
