const arsFmt = new Intl.NumberFormat("es-AR", { maximumFractionDigits: 0 });

export function fmtARS(n: number): string {
  return "$" + arsFmt.format(Math.round(n));
}

export function fmtUSD(n: number): string {
  // USD endpoints can be small (a few dollars) or large; keep one decimal under 100.
  const digits = Math.abs(n) < 100 ? 1 : 0;
  return "US$" + n.toLocaleString("es-AR", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function fmtNum(n: number): string {
  return arsFmt.format(Math.round(n));
}

/** Compact money for axis ticks: $120k, $1,2M. */
export function fmtShort(n: number): string {
  if (n >= 1_000_000) return "$" + (n / 1_000_000).toLocaleString("es-AR", { maximumFractionDigits: 1 }) + "M";
  if (n >= 1_000) return "$" + Math.round(n / 1_000) + "k";
  return "$" + Math.round(n);
}

/** A multiplier like 12,3×. */
export function fmtX(n: number): string {
  const d = n >= 100 ? 0 : n >= 10 ? 1 : 2;
  return n.toLocaleString("es-AR", { maximumFractionDigits: d }) + "×";
}

export function fmtPct(n: number, decimals = 1): string {
  return n.toLocaleString("es-AR", { minimumFractionDigits: decimals, maximumFractionDigits: decimals }) + "%";
}

/** Cumulative inflation can run to tens of thousands of percent — no decimals once it's large. */
export function fmtPctBig(n: number): string {
  if (Math.abs(n) >= 1000) return Math.round(n).toLocaleString("es-AR") + "%";
  return fmtPct(n);
}

export const MESES = [
  "enero", "febrero", "marzo", "abril", "mayo", "junio",
  "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
];

/** "2003-01" → "enero 2003". */
export function fmtMonth(m: string): string {
  const [y, mm] = m.split("-");
  return `${MESES[parseInt(mm, 10) - 1]} ${y}`;
}

/** "2003-01" → "ene 2003" (compact, for axis ticks). */
export function fmtMonthShort(m: string): string {
  const [y, mm] = m.split("-");
  return `${MESES[parseInt(mm, 10) - 1].slice(0, 3)} ${y.slice(2)}`;
}

/** Parse "790.000" / "1.200.000" / "790000" → 790000. */
export function parseMoney(s: string): number {
  const digits = s.replace(/[^\d]/g, "");
  return digits ? parseInt(digits, 10) : 0;
}
