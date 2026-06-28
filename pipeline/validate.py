"""Validation gate: assert the spliced series still reproduces the figures it must.

HARD checks (build fails on any miss):
  • INDEC IPC Nacional Dec–Dec inflation, 2017–2024 (the official headline numbers).
  • IPC San Luis Dec–Dec, 2007–2015 (the intervened-decade alternative the splice uses).
  • INDEC IPC-GBA 2002 (the convertibility-collapse year) and convertibility-era FX ≈ 1:1.
  • A cumulative purchasing-power cross-check ($1.000 de 2003 → pesos de la vintage).
"""

from __future__ import annotations

import json
import sys

from . import config

RESET, RED, GREEN, DIM = "\033[0m", "\033[31m", "\033[32m", "\033[2m"


class Gate:
    def __init__(self) -> None:
        self.failures = 0

    def check(self, name: str, got: float, expected: float, tol: float, *, rel: bool = False, unit: str = "") -> bool:
        if rel:
            ok = expected != 0 and abs(got - expected) / abs(expected) <= tol
            tol_s = f"±{tol:.0%}"
        else:
            ok = abs(got - expected) <= tol
            tol_s = f"±{tol}{unit}"
        tag = f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"
        print(f"  [{tag}] {name:<40} got={got:>12,.2f}  esperado={expected:>12,.2f}  ({tol_s})")
        if not ok:
            self.failures += 1
        return ok


def validate() -> None:
    art = json.loads(config.ARTIFACT_PATHS[0].read_text(encoding="utf-8"))
    annual = {row["year"]: row["pct"] for row in art["annual_inflation"]}
    by_month = {row["m"]: row for row in art["series"]}
    g = Gate()

    print("\n=== HARD GATE: IPC Nacional (INDEC) Dec–Dec — la serie oficial debe reproducirse ===")
    for year, exp in config.INDEC_NACIONAL_ANNUAL.items():
        g.check(f"Inflación {year} (oficial)", annual.get(year, float("nan")), exp, 0.2, unit="pp")

    print("\n=== HARD GATE: IPC San Luis Dec–Dec (década intervenida) ===")
    for year, exp in config.SANLUIS_ANNUAL.items():
        g.check(f"Inflación {year} (San Luis)", annual.get(year, float("nan")), exp, 0.2, unit="pp")

    print("\n=== HARD GATE: pre-intervención y convertibilidad ===")
    for year, exp in config.GBA_ANNUAL.items():
        g.check(f"Inflación {year} (IPC-GBA)", annual.get(year, float("nan")), exp, 0.2, unit="pp")
    # Convertibility: 1 peso = 1 USD across 1993–2001 (the official ref rate hovers ~1.00).
    conv = [r["off"] for m, r in by_month.items() if "1993-01" <= m <= "2001-12"]
    worst = max(abs(x - config.CONVERTIBILITY_FX) for x in conv)
    g.check(
        "Tipo de cambio en convertibilidad",
        config.CONVERTIBILITY_FX + worst,
        config.CONVERTIBILITY_FX,
        config.CONVERTIBILITY_FX_TOL,
    )

    print("\n=== HARD GATE: poder de compra acumulado (cross-check independiente) ===")
    cum = art["anchors"]["cum"]
    g.check(
        f"${config.CUM_ANCHOR['pesos']:,.0f} de {config.CUM_ANCHOR['from_month']} → hoy",
        cum["computed_today"],
        config.CUM_ANCHOR["expect_today_approx"],
        config.CUM_ANCHOR["rel_tol"],
        rel=True,
    )

    # Structural sanity: base month is exactly 100 and the index is strictly positive throughout.
    base = by_month[art["base_month"]]["cpi"]
    g.check("Índice en el mes base = 100", base, 100.0, 0.001)
    if not all(r["cpi"] > 0 for r in art["series"]):
        print(f"  [{RED}FAIL{RESET}] índice con valores no positivos")
        g.failures += 1

    print()
    if g.failures:
        print(f"{RED}VALIDACIÓN FALLIDA — {g.failures} chequeo(s) no pasaron.{RESET}")
        sys.exit(1)
    print(f"{GREEN}VALIDACIÓN OK — la serie reproduce las cifras oficiales del INDEC, San Luis y BCRA.{RESET}")


if __name__ == "__main__":
    validate()
