import { afterEach, describe, expect, it, vi } from "vitest";
import * as charts from "../src/charts";
import { ARTIFACT, model, mountEl, mountZeroEl } from "./fixture";

const M = model();
const svg = (el: HTMLElement) => el.querySelector("svg");

afterEach(() => {
  vi.unstubAllGlobals();
  document.body.innerHTML = "";
});

describe("refreshPalette / cssVar", () => {
  it("falls back to defaults when CSS vars are empty (v falsy)", () => {
    expect(() => charts.refreshPalette()).not.toThrow();
  });

  it("reads a CSS custom property when present (v truthy)", () => {
    document.documentElement.style.setProperty("--ink", "#1a1a1a");
    expect(() => charts.refreshPalette()).not.toThrow();
    document.documentElement.style.removeProperty("--ink");
  });

  it("returns the fallback when document is undefined", () => {
    try {
      vi.stubGlobal("document", undefined);
      expect(() => charts.refreshPalette()).not.toThrow();
    } finally {
      vi.unstubAllGlobals();
    }
  });
});

describe("xOf", () => {
  it("maps a month to a decimal year", () => {
    expect(charts.xOf("2003-07")).toBeCloseTo(2003.5, 5);
    expect(charts.xOf("2000-01")).toBe(2000);
  });
});

describe("renderDecay", () => {
  it("renders from an old month (multi-point decay)", () => {
    const el = mountEl();
    charts.renderDecay(el, M, "1993-01", 1000);
    expect(svg(el)).toBeTruthy();
  });
  it("renders when the start is the vintage (single point) and with a zero-width container", () => {
    const el = mountZeroEl();
    charts.renderDecay(el, M, ARTIFACT.vintage, 1000);
    expect(svg(el)).toBeTruthy();
  });
});

describe("renderDollar / renderBrecha", () => {
  it("renders both dollar series and the brecha", () => {
    const a = mountEl();
    const b = mountEl();
    charts.renderDollar(a, M, "2011-06");
    charts.renderBrecha(b, ARTIFACT.series);
    expect(svg(a)).toBeTruthy();
    expect(svg(b)).toBeTruthy();
  });
});

describe("renderAnnual", () => {
  it("renders bars, highlighting a present year", () => {
    const el = mountEl();
    charts.renderAnnual(el, ARTIFACT.annual_inflation, 2023);
    expect(svg(el)).toBeTruthy();
  });
  it("renders with no matching highlight year", () => {
    const el = mountEl();
    charts.renderAnnual(el, ARTIFACT.annual_inflation, 1800);
    expect(svg(el)).toBeTruthy();
  });
});

describe("renderMonthly", () => {
  it("renders monthly bars across all three source colors (from 1993)", () => {
    const el = mountEl();
    charts.renderMonthly(el, ARTIFACT.series, "1993-01");
    expect(svg(el)).toBeTruthy();
  });
});

describe("renderIndex", () => {
  it("renders the spliced index with the start marked", () => {
    const el = mountEl();
    charts.renderIndex(el, M, "2003-01");
    expect(svg(el)).toBeTruthy();
  });
});

describe("renderUsdBars", () => {
  it("renders all kind/when combinations, plus a zero-length bar", () => {
    const el = mountEl();
    charts.renderUsdBars(el, [
      { label: "entonces · oficial", usd: 1000, kind: "off", when: "then" },
      { label: "entonces · blue", usd: 0, kind: "blue", when: "then" }, // zero -> Math.max(2,..) branch
      { label: "hoy · oficial", usd: 50, kind: "off", when: "now" },
      { label: "hoy · blue", usd: 45, kind: "blue", when: "now" },
    ]);
    expect(svg(el)).toBeTruthy();
    expect(el.innerHTML).toContain("US$");
  });
  it("uses the fallback width with a zero-width container", () => {
    const el = mountZeroEl();
    charts.renderUsdBars(el, [{ label: "x", usd: 10, kind: "off", when: "now" }]);
    expect(svg(el)).toBeTruthy();
  });
});

describe("zero-width containers", () => {
  it("every chart falls back to its default width when clientWidth is 0", () => {
    charts.renderDollar(mountZeroEl(), M, "2011-06");
    charts.renderBrecha(mountZeroEl(), ARTIFACT.series);
    charts.renderAnnual(mountZeroEl(), ARTIFACT.annual_inflation, 2023);
    charts.renderMonthly(mountZeroEl(), ARTIFACT.series, "2020-01");
    charts.renderIndex(mountZeroEl(), M, "2003-01");
    expect(document.querySelectorAll("svg").length).toBeGreaterThanOrEqual(5);
  });
});

describe("validationRows", () => {
  it("matches present anchors and flags a missing one", () => {
    const rows = charts.validationRows(ARTIFACT.annual_inflation, ARTIFACT.anchors.indec_nacional_annual);
    expect(rows.length).toBeGreaterThan(0);
    expect(rows.every((r) => r.ok)).toBe(true); // committed artifact reproduces every anchor
    expect(rows.map((r) => Number(r.year))).toEqual([...rows.map((r) => Number(r.year))].sort((x, y) => x - y));

    const missing = charts.validationRows([], { "2024": 117.8 });
    expect(missing[0].ok).toBe(false);
    expect(Number.isNaN(missing[0].ours)).toBe(true);
  });
});
