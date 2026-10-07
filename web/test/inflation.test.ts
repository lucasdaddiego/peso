import { describe, expect, it } from "vitest";
import { buildModel, monthsBetween, validationRows } from "../src/inflation";
import { ARTIFACT } from "./fixture";
import type { Artifact, SeriesRow } from "../src/types";

function row(m: string, cpi: number, off: number, blue: number): SeriesRow {
  return { m, cpi, src: "gba", mom: null, off, blue, blue_est: false };
}

const ART = {
  base_month: "2000-03",
  start_month: "2000-01",
  series: [row("2000-01", 25, 1, 1), row("2000-02", 50, 2, 3), row("2000-03", 100, 4, 8)],
} as unknown as Artifact;

describe("monthsBetween", () => {
  it("counts signed whole months", () => {
    expect(monthsBetween("2003-01", "2003-04")).toBe(3);
    expect(monthsBetween("2003-04", "2003-01")).toBe(-3);
    expect(monthsBetween("2003-01", "2003-01")).toBe(0);
  });
});

describe("model", () => {
  const m = buildModel(ART);

  it("clamps months into [first, last]", () => {
    expect(m.clampMonth("1999-12")).toBe("2000-01");
    expect(m.clampMonth("2099-01")).toBe("2000-03");
    expect(m.clampMonth("2000-02")).toBe("2000-02");
  });

  it("cpi looks up via the clamp", () => {
    expect(m.cpi("2000-02")).toBe(50);
    expect(m.cpi("1990-01")).toBe(25); // clamped to first month
  });

  it("equivalent: default-to-today and explicit target", () => {
    expect(m.equivalent(100, "2000-01")).toBe(400); // *100/25
    expect(m.equivalent(100, "2000-01", "2000-02")).toBe(200); // *50/25
  });

  it("cumulativePct", () => {
    expect(m.cumulativePct("2000-01")).toBe(300); // 100/25 - 1
  });

  it("annualisedPct is 0 for the same month and positive otherwise", () => {
    expect(m.annualisedPct("2000-03")).toBe(0); // n === 0 branch
    expect(m.annualisedPct("2000-01")).toBeGreaterThan(0);
  });

  it("usd converts at the chosen rate", () => {
    expect(m.usd(100, "2000-01", "off")).toBe(100);
    expect(m.usd(100, "2000-02", "blue")).toBeCloseTo(33.33, 1);
  });

  it("brechaPct is the blue-over-official gap", () => {
    expect(m.brechaPct("2000-02")).toBe(50); // 3/2 - 1
    expect(m.brechaPct("2000-01")).toBe(0);
  });
});

describe("validationRows", () => {
  it("matches present anchors and flags a missing one", () => {
    const rows = validationRows(ARTIFACT.annual_inflation, ARTIFACT.anchors.indec_nacional_annual);
    expect(rows.length).toBeGreaterThan(0);
    expect(rows.every((r) => r.ok)).toBe(true); // committed artifact reproduces every anchor
    expect(rows.map((r) => Number(r.year))).toEqual([...rows.map((r) => Number(r.year))].sort((x, y) => x - y));
    expect(rows.map((r) => r.year)).toContain("2025"); // one anchor per completed year, 2025 included

    const missing = validationRows([], { "2024": 117.8 });
    expect(missing[0].ok).toBe(false);
    expect(Number.isNaN(missing[0].ours)).toBe(true);
  });
});
