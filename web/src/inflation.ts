import type { Artifact, SeriesRow } from "./types";

/** Whole months from `a` to `b` ("YYYY-MM"), signed. monthsBetween("2003-01","2003-04") === 3. */
export function monthsBetween(a: string, b: string): number {
  const [ay, am] = a.split("-").map(Number);
  const [by, bm] = b.split("-").map(Number);
  return (by - ay) * 12 + (bm - am);
}

export interface Model {
  rows: SeriesRow[];
  byMonth: Map<string, SeriesRow>;
  firstMonth: string;
  lastMonth: string; // = vintage, where cpi === 100
  /** Clamp a requested month into the available [first, last] range. */
  clampMonth(m: string): string;
  row(m: string): SeriesRow;
  cpi(m: string): number;
  /** Value of `amount` pesos of `from` expressed in pesos of `to` (default: today/vintage). */
  equivalent(amount: number, from: string, to?: string): number;
  /** Cumulative inflation % between two months (default to today). */
  cumulativePct(from: string, to?: string): number;
  /** Annualised (compound) inflation % between two months. 0 when they're the same month. */
  annualisedPct(from: string, to?: string): number;
  /** `amount` pesos converted to USD at that month's official or blue rate. */
  usd(amount: number, m: string, kind: "off" | "blue"): number;
  /** Blue-vs-official gap ("brecha") at a month, in %. */
  brechaPct(m: string): number;
}

export function buildModel(art: Artifact): Model {
  const rows = art.series;
  const byMonth = new Map(rows.map((r) => [r.m, r]));
  const firstMonth = rows[0].m;
  const lastMonth = art.base_month;

  const clampMonth = (m: string): string => (m < firstMonth ? firstMonth : m > lastMonth ? lastMonth : m);
  const row = (m: string): SeriesRow => byMonth.get(clampMonth(m))!;
  const cpi = (m: string): number => row(m).cpi;

  const equivalent = (amount: number, from: string, to: string = lastMonth): number =>
    amount * (cpi(to) / cpi(from));

  const cumulativePct = (from: string, to: string = lastMonth): number => (cpi(to) / cpi(from) - 1) * 100;

  const annualisedPct = (from: string, to: string = lastMonth): number => {
    const n = monthsBetween(clampMonth(from), clampMonth(to));
    if (n === 0) return 0;
    return (Math.pow(cpi(to) / cpi(from), 12 / n) - 1) * 100;
  };

  const usd = (amount: number, m: string, kind: "off" | "blue"): number => {
    const r = row(m);
    const rate = kind === "off" ? r.off : r.blue;
    return amount / rate;
  };

  const brechaPct = (m: string): number => {
    const r = row(m);
    return (r.blue / r.off - 1) * 100;
  };

  return {
    rows, byMonth, firstMonth, lastMonth,
    clampMonth, row, cpi, equivalent, cumulativePct, annualisedPct, usd, brechaPct,
  };
}
