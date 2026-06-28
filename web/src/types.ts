// Mirrors the pipeline artifact (schema_version 1).

export type SegmentKey = "gba" | "sanluis" | "nacional";

export interface SeriesRow {
  m: string; // "YYYY-MM"
  cpi: number; // spliced index, vintage month = 100
  src: SegmentKey;
  mom: number | null; // month-over-month inflation %, null for the first month
  off: number; // official ARS per USD
  blue: number; // informal ("blue") ARS per USD
  blue_est: boolean; // true where blue was estimated (pre-cepo := official, or a carried gap)
}

export interface AnnualRow {
  year: number;
  pct: number; // Dec–Dec inflation %
  source: SegmentKey;
}

export interface Segment {
  key: SegmentKey;
  start: string;
  end: string;
  label: string;
  source: string;
  series_id: string;
  note: string;
}

export interface CumAnchor {
  from_month: string;
  pesos: number;
  expect_today_approx: number;
  rel_tol: number;
  computed_today: number;
}

export interface Artifact {
  schema_version: number;
  generated_at: string;
  currency: string;
  vintage: string;
  vintage_label: string;
  base_month: string;
  start_month: string;
  source: {
    ipc_segments: Segment[];
    fx_official: { label: string; series_id: string; url: string };
    fx_blue: { label: string; url: string; first_month: string; note: string };
    api: string;
  };
  series: SeriesRow[];
  annual_inflation: AnnualRow[];
  anchors: {
    indec_nacional_annual: Record<string, number>;
    sanluis_annual: Record<string, number>;
    gba_annual: Record<string, number>;
    cum: CumAnchor;
  };
  citation: string;
}
