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

describe("decaySeries", () => {
  it("starts at the headline equivalent and decays to the nominal amount", () => {
    const d = charts.decaySeries(M, "1993-01", 1000);
    expect(d.length).toBe(M.rows.length);
    expect(d[0].m).toBe("1993-01");
    // 1.000 pesos de enero-1993 = 1000 * 100 / cpi[1993-01] (0.038975) pesos de hoy.
    expect(d[0].v).toBeCloseTo(2565747.27, 1);
    // …and by the vintage (cpi = 100) they are worth exactly their nominal selves.
    expect(d[d.length - 1].v).toBeCloseTo(1000, 6);
    expect(d[d.length - 1].v).toBeLessThan(d[0].v); // the curve falls, it does not rise
  });
});

describe("brechaSeries", () => {
  it("is the blue premium over the official rate, signed", () => {
    const b = charts.brechaSeries(ARTIFACT.series);
    const i = ARTIFACT.series.findIndex((r) => r.m === "2020-10");
    expect(b[i].x).toBeCloseTo(charts.xOf("2020-10"), 6);
    expect(b[i].pct).toBeCloseTo(87.69, 2); // blue 147,00 vs oficial 78,32
    // A blue *below* the official rate reads negative — the ratio is not inverted.
    expect(charts.brechaSeries([{ ...ARTIFACT.series[0], off: 100, blue: 50 }])[0].pct).toBeCloseTo(-50, 6);
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
  it("scales every bar against the largest value on a shared axis", () => {
    const el = mountEl(680);
    charts.renderUsdBars(el, [
      { label: "a", usd: 1000, kind: "off", when: "then" },
      { label: "b", usd: 500, kind: "blue", when: "now" },
    ]);
    // Track = width − labelW(150) − 70 = 460px: the max fills it, half the dollars = half the bar.
    const widths = [...el.querySelectorAll("rect")].map((r) => Number(r.getAttribute("width")));
    expect(widths[0]).toBeCloseTo(460, 1);
    expect(widths[1]).toBeCloseTo(230, 1);
    expect(el.textContent).toContain("US$1.000");
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
