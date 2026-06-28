import * as Plot from "@observablehq/plot";
import { fmtMonthShort, fmtShort } from "./format";
import type { Model } from "./inflation";
import type { AnnualRow, SeriesRow } from "./types";

// Chart palette, sourced from CSS custom properties so the charts follow the light/dark theme.
// refreshPalette() re-reads them before each render pass; the defaults are the light values.
let INK = "#1a1a1a";
let ACCENT = "#2a5c8a";
let MUTED = "#8a8a86";
let WARN = "#9a3b2e";
let OK = "#2f6b3a";
let PAPER = "#fafaf8";
let INK_RGB = "26, 26, 26";
let ACCENT_RGB = "42, 92, 138";

function cssVar(name: string, fallback: string): string {
  if (typeof document === "undefined") return fallback;
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
}

/** Re-read the chart palette from CSS custom properties (picks up the active light/dark theme). */
export function refreshPalette(): void {
  INK = cssVar("--ink", INK);
  ACCENT = cssVar("--accent", ACCENT);
  MUTED = cssVar("--chart-muted", MUTED);
  WARN = cssVar("--warn", WARN);
  OK = cssVar("--ok", OK);
  PAPER = cssVar("--paper", PAPER);
  INK_RGB = cssVar("--ink-rgb", INK_RGB);
  ACCENT_RGB = cssVar("--accent-rgb", ACCENT_RGB);
}

const inkA = (alpha: number | string) => `rgba(${INK_RGB}, ${alpha})`;
const SEG_COLOR: Record<string, () => string> = {
  gba: () => MUTED,
  sanluis: () => WARN,
  nacional: () => ACCENT,
};
const SEG_LABEL: Record<string, string> = {
  gba: "IPC-GBA (oficial, pre-intervención)",
  sanluis: "IPC San Luis (década intervenida)",
  nacional: "IPC Nacional (oficial)",
};

function clear(el: HTMLElement) {
  el.replaceChildren();
}

/** Decimal-year x coordinate for a month, e.g. "2003-07" → 2003.5. Robust across jsdom (no Dates). */
export function xOf(month: string): number {
  const [y, m] = month.split("-").map(Number);
  return y + (m - 1) / 12;
}

// Intervened-INDEC window (San Luis splice), marked on the long-run charts.
const INTERV_LO = 2007;
const INTERV_HI = 2016;

function intervenedMarks(yTop: number): Plot.Markish[] {
  return [
    Plot.ruleX([INTERV_LO, INTERV_HI], { stroke: WARN, strokeOpacity: 0.5, strokeDasharray: "3,3" }),
    Plot.text([{ x: (INTERV_LO + INTERV_HI) / 2, y: yTop }], {
      x: "x", y: "y", text: () => "INDEC intervenido", fill: WARN, fontSize: 10, dy: -2,
    }),
  ];
}

// ---------------------------------------------------------------------------
// Purchasing-power decay (Observable Plot): the worth, in pesos de hoy, of holding `amount`
// nominal pesos from `from` onward — it falls from the headline equivalent down to `amount`.
// ---------------------------------------------------------------------------
export function renderDecay(el: HTMLElement, model: Model, from: string, amount: number) {
  clear(el);
  const start = model.clampMonth(from);
  const data = model.rows
    .filter((r) => r.m >= start)
    .map((r) => ({ x: xOf(r.m), v: (amount * 100) / r.cpi, m: r.m }));
  const startV = data[0].v;
  const endV = data[data.length - 1].v;
  const plot = Plot.plot({
    width: el.clientWidth || 680,
    height: 300,
    marginLeft: 60,
    marginBottom: 40,
    x: { label: null, tickFormat: (d: number) => String(Math.round(d)) },
    y: { label: "↑ poder de compra (pesos de hoy)", grid: true, tickFormat: (d: number) => fmtShort(d) },
    style: { background: "transparent", color: INK, fontFamily: "inherit", fontSize: "12px" },
    marks: [
      Plot.areaY(data, { x: "x", y: "v", fill: ACCENT, fillOpacity: 0.08 }),
      Plot.lineY(data, { x: "x", y: "v", stroke: ACCENT, strokeWidth: 2 }),
      Plot.dot([data[0], data[data.length - 1]], { x: "x", y: "v", r: 4, fill: ACCENT, stroke: PAPER, strokeWidth: 1.5 }),
      Plot.text([{ x: data[0].x, y: startV }], {
        x: "x", y: "y", text: () => `valía ${fmtShort(startV)}`, dy: -10, dx: 4, textAnchor: "start", fill: ACCENT, fontWeight: 600, fontSize: 11,
      }),
      Plot.text([{ x: data[data.length - 1].x, y: endV }], {
        x: "x", y: "y", text: () => `hoy ${fmtShort(endV)}`, dy: -10, dx: -4, textAnchor: "end", fill: MUTED, fontSize: 11,
      }),
      Plot.ruleY([0], { stroke: INK, strokeOpacity: 0.2 }),
    ],
  });
  el.append(plot);
}

// ---------------------------------------------------------------------------
// Official vs blue dollar over time (Observable Plot, log y), with the start month marked.
// ---------------------------------------------------------------------------
export function renderDollar(el: HTMLElement, model: Model, from: string) {
  clear(el);
  const OFF = "Oficial";
  const BLUE = "Blue (informal)";
  const data: { x: number; rate: number; serie: string }[] = [];
  for (const r of model.rows) {
    data.push({ x: xOf(r.m), rate: r.off, serie: OFF });
    data.push({ x: xOf(r.m), rate: r.blue, serie: BLUE });
  }
  const startX = xOf(model.clampMonth(from));
  const hi = Math.max(...model.rows.map((r) => r.blue));
  const plot = Plot.plot({
    width: el.clientWidth || 680,
    height: 320,
    marginLeft: 56,
    marginBottom: 40,
    x: { label: null, tickFormat: (d: number) => String(Math.round(d)) },
    y: { type: "log", label: "↑ pesos por dólar (log)", grid: true, tickFormat: (d: number) => fmtShort(d) },
    color: { domain: [OFF, BLUE], range: [inkA(0.55), WARN], legend: true },
    style: { background: "transparent", color: INK, fontFamily: "inherit", fontSize: "11px" },
    marks: [
      ...intervenedMarks(hi),
      Plot.line(data, { x: "x", y: "rate", stroke: "serie", strokeWidth: 1.8 }),
      Plot.ruleX([startX], { stroke: ACCENT, strokeWidth: 2, strokeDasharray: "3,2" }),
      Plot.text([{ x: startX, y: hi }], { x: "x", y: "y", text: () => fmtMonthShort(model.clampMonth(from)), fill: ACCENT, fontSize: 10, fontWeight: 700, dy: -2, textAnchor: "middle" }),
    ],
  });
  el.append(plot);
}

// ---------------------------------------------------------------------------
// Brecha (blue/official − 1) over time (custom SVG area) — the parallel-market premium.
// ---------------------------------------------------------------------------
export function renderBrecha(el: HTMLElement, rows: SeriesRow[]) {
  clear(el);
  const data = rows.map((r) => ({ x: xOf(r.m), pct: (r.blue / r.off - 1) * 100 }));
  const hi = Math.max(...data.map((d) => d.pct), 10);
  const plot = Plot.plot({
    width: el.clientWidth || 680,
    height: 220,
    marginLeft: 48,
    marginBottom: 40,
    x: { label: null, tickFormat: (d: number) => String(Math.round(d)) },
    y: { label: "↑ brecha cambiaria", grid: true, domain: [0, hi * 1.05], tickFormat: (d: number) => `${Math.round(d)}%` },
    style: { background: "transparent", color: INK, fontFamily: "inherit", fontSize: "11px" },
    marks: [
      Plot.areaY(data, { x: "x", y: "pct", fill: WARN, fillOpacity: 0.14 }),
      Plot.lineY(data, { x: "x", y: "pct", stroke: WARN, strokeWidth: 1.6 }),
      Plot.ruleY([0], { stroke: INK, strokeOpacity: 0.2 }),
    ],
  });
  el.append(plot);
}

// ---------------------------------------------------------------------------
// Annual (Dec–Dec) inflation bars, colored by which source produced each year.
// ---------------------------------------------------------------------------
export function renderAnnual(el: HTMLElement, annual: AnnualRow[], highlightYear: number) {
  clear(el);
  // Pre-map the source key to its human label so the legend reads well without a tickFormat callback.
  const data = annual.map((a) => ({ ...a, serie: SEG_LABEL[a.source], you: a.year === highlightYear }));
  const plot = Plot.plot({
    width: el.clientWidth || 680,
    height: 300,
    marginLeft: 48,
    marginBottom: 44,
    x: { label: null, tickFormat: (d: number) => String(d), tickRotate: -45 },
    y: { label: "↑ inflación anual (dic–dic)", grid: true, tickFormat: (d: number) => `${d}%` },
    color: { domain: Object.values(SEG_LABEL), range: [MUTED, WARN, ACCENT], legend: true },
    style: { background: "transparent", color: INK, fontFamily: "inherit", fontSize: "11px" },
    marks: [
      Plot.barY(data, { x: "year", y: "pct", fill: "serie", inset: 0.5 }),
      Plot.barY(data.filter((d) => d.you), { x: "year", y: "pct", fill: "none", stroke: INK, strokeWidth: 1.5, inset: 0.5 }),
      Plot.ruleY([0], { stroke: INK, strokeOpacity: 0.25 }),
    ],
  });
  el.append(plot);
}

// ---------------------------------------------------------------------------
// Monthly inflation bars (MoM %), for the chosen window onward.
// ---------------------------------------------------------------------------
export function renderMonthly(el: HTMLElement, rows: SeriesRow[], from: string) {
  clear(el);
  const data = rows
    .filter((r) => r.m >= from && r.mom !== null)
    .map((r) => ({ x: xOf(r.m), mom: r.mom as number, src: r.src }));
  const plot = Plot.plot({
    width: el.clientWidth || 680,
    height: 260,
    marginLeft: 44,
    marginBottom: 40,
    x: { label: null, tickFormat: (d: number) => String(Math.round(d)) },
    y: { label: "↑ inflación mensual", grid: true, tickFormat: (d: number) => `${d}%` },
    style: { background: "transparent", color: INK, fontFamily: "inherit", fontSize: "11px" },
    marks: [
      Plot.barY(data, { x: "x", y: "mom", fill: (d: { src: string }) => SEG_COLOR[d.src](), inset: 0.2 }),
      Plot.ruleY([0], { stroke: INK, strokeOpacity: 0.25 }),
    ],
  });
  el.append(plot);
}

// ---------------------------------------------------------------------------
// The spliced CPI index itself (log y), full span, segments colored, the splice on show.
// ---------------------------------------------------------------------------
export function renderIndex(el: HTMLElement, model: Model, from: string) {
  clear(el);
  const data = model.rows.map((r) => ({ x: xOf(r.m), cpi: r.cpi, serie: r.src }));
  const startX = xOf(model.clampMonth(from));
  const plot = Plot.plot({
    width: el.clientWidth || 680,
    height: 300,
    marginLeft: 52,
    marginBottom: 40,
    x: { label: null, tickFormat: (d: number) => String(Math.round(d)) },
    y: { type: "log", label: "↑ índice (hoy = 100, log)", grid: true, tickFormat: (d: number) => String(d) },
    color: { domain: ["gba", "sanluis", "nacional"], range: [MUTED, WARN, ACCENT] },
    style: { background: "transparent", color: INK, fontFamily: "inherit", fontSize: "11px" },
    marks: [
      ...intervenedMarks(100),
      Plot.line(data, { x: "x", y: "cpi", stroke: "serie", strokeWidth: 2, z: null }),
      Plot.ruleX([startX], { stroke: ACCENT, strokeWidth: 2, strokeDasharray: "3,2" }),
      Plot.dot([{ x: startX, y: model.cpi(from) }], { x: "x", y: "y", r: 4, fill: ACCENT, stroke: PAPER, strokeWidth: 1.5 }),
    ],
  });
  el.append(plot);
}

// ---------------------------------------------------------------------------
// USD endpoints (custom SVG): your amount as dollars then vs the equivalent now, at both rates.
// Four bars (then-official, then-blue, now-official, now-blue) sharing one USD scale.
// ---------------------------------------------------------------------------
export function renderUsdBars(el: HTMLElement, bars: { label: string; usd: number; kind: "off" | "blue"; when: "then" | "now" }[]) {
  clear(el);
  const max = Math.max(...bars.map((b) => b.usd), 1);
  const w = el.clientWidth || 680;
  const rowH = 34;
  const labelW = 150;
  const x = (v: number) => labelW + (v / max) * (w - labelW - 70);
  let s = `<svg viewBox="0 0 ${w} ${bars.length * rowH + 6}" width="100%" height="${bars.length * rowH + 6}" font-family="inherit" style="display:block">`;
  bars.forEach((b, i) => {
    const y = i * rowH + 4;
    const col = b.kind === "blue" ? WARN : inkA(0.55);
    const bw = Math.max(2, x(b.usd) - labelW);
    s += `<text x="0" y="${y + rowH / 2 + 1}" font-size="11" fill="${INK}">${b.label}</text>`;
    s += `<rect x="${labelW}" y="${y + 6}" width="${bw.toFixed(1)}" height="${rowH - 14}" rx="2" fill="${col}" fill-opacity="${b.when === "then" ? 0.55 : 1}"/>`;
    s += `<text x="${(labelW + bw + 6).toFixed(1)}" y="${y + rowH / 2 + 1}" font-size="11" font-weight="700" fill="${col}">US$${Math.round(b.usd).toLocaleString("es-AR")}</text>`;
  });
  s += `</svg>`;
  el.innerHTML = s;
}

// ---------------------------------------------------------------------------
// Validation table (methodology): each anchor year, the official figure vs our reproduction.
// ---------------------------------------------------------------------------
export function validationRows(annual: AnnualRow[], anchors: Record<string, number>): { year: string; official: number; ours: number; ok: boolean }[] {
  const byYear = new Map(annual.map((a) => [a.year, a.pct]));
  return Object.entries(anchors)
    .map(([y, official]) => {
      const ours = byYear.get(Number(y)) ?? NaN;
      return { year: y, official, ours, ok: Math.abs(ours - official) <= 0.2 };
    })
    .sort((a, b) => Number(a.year) - Number(b.year));
}
