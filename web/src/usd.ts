// Live dólar blue from dolarapi.com — display only, a "cotización de hoy" badge. The historical
// USD math always uses the committed monthly series, never this live value.

export interface BlueRate {
  venta: number;
}

export async function fetchBlue(): Promise<BlueRate | null> {
  try {
    // Bounded: an unresponsive host must resolve to null (no badge), not hang for minutes.
    const r = await fetch("https://dolarapi.com/v1/dolares/blue", { signal: AbortSignal.timeout(3000) });
    if (!r.ok) return null;
    const d = await r.json();
    // Guard the external shape: a missing/non-numeric rate must fall back to null, not NaN.
    if (typeof d?.venta !== "number" || !(d.venta > 0)) return null;
    return { venta: d.venta };
  } catch {
    return null;
  }
}
