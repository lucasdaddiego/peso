// Shared test data: the real committed artifact (so charts/render code runs against realistic
// shapes). Vite resolves the JSON import at transform time. `clone()` returns a deep copy so a
// test can mutate edge cases without leaking into others.
import artifactJson from "../public/series.v1.json";
import { buildModel, type Model } from "../src/inflation";
import type { Artifact } from "../src/types";

export const ARTIFACT = artifactJson as unknown as Artifact;

export const clone = (): Artifact => structuredClone(ARTIFACT);

export const model = (): Model => buildModel(ARTIFACT);

/** A detached <div> with a non-zero width, since chart code reads `el.clientWidth || fallback`. */
export function mountEl(width = 680): HTMLElement {
  const el = document.createElement("div");
  Object.defineProperty(el, "clientWidth", { value: width, configurable: true });
  document.body.appendChild(el);
  return el;
}

/** A detached <div> whose clientWidth stays 0 (falsy) → exercises the `clientWidth || fallback` branch. */
export function mountZeroEl(): HTMLElement {
  const el = document.createElement("div");
  document.body.appendChild(el);
  return el;
}
