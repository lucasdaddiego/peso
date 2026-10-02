import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import indexHtml from "../index.html?raw";
import seriesUrl from "../public/series.v1.json?url";
import { ARTIFACT, clone } from "./fixture";

const BLUE = { venta: 1515, fechaActualizacion: "2026-06-28" };
const bodyHtml = new DOMParser().parseFromString(indexHtml, "text/html").body.innerHTML;

interface BootOpts {
  artifact?: unknown;
  blue?: unknown | null;
  search?: string;
  presetAmount?: string;
}

/** Mount the real index.html body, mock both fetches, import main.ts (auto-runs init), wait. */
async function boot(opts: BootOpts = {}) {
  const artifact = opts.artifact ?? ARTIFACT;
  const blue = opts.blue === undefined ? BLUE : opts.blue;
  document.body.innerHTML = bodyHtml;
  if (opts.presetAmount !== undefined) $i("amount-number").value = opts.presetAmount;
  window.history.replaceState(null, "", opts.search ?? "/");
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (String(url).includes("dolarapi")) {
        if (blue === null) return { ok: false, json: async () => ({}) };
        return { ok: true, json: async () => blue };
      }
      return { ok: true, json: async () => artifact };
    }),
  );
  vi.resetModules();
  const M = await import("../src/main");
  await vi.waitFor(() => {
    if (!document.getElementById("result")?.innerHTML) throw new Error("init not done");
  });
  return M;
}

const $ = (id: string) => document.getElementById(id) as HTMLElement;
const $i = (id: string) => document.getElementById(id) as HTMLInputElement;
const $s = (id: string) => document.getElementById(id) as HTMLSelectElement;
function setInput(id: string, v: string) {
  const el = $i(id);
  el.value = v;
  el.dispatchEvent(new Event("input"));
}
function setSelect(id: string, v: string) {
  const el = $s(id);
  el.value = v;
  el.dispatchEvent(new Event("change"));
}
/** Set the start month via the two selects. */
function setWhen(year: string, month: string) {
  $s("start-year").value = year;
  setSelect("start-month", month);
}

beforeEach(() => {
  Object.defineProperty(HTMLElement.prototype, "clientWidth", { value: 680, configurable: true });
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  document.body.innerHTML = "";
});

describe("init smoke", () => {
  it("boots, renders the headline, source badge, live-blue and footer", async () => {
    await boot();
    expect($("result").innerHTML).toContain("de hoy");
    expect($("source-badge").innerHTML).toContain("San Luis");
    expect($("site-footer").innerHTML).toContain("Bluelytics");
    expect($("chart-decay").innerHTML).toContain("svg");
    // the live badge lands after the page, not before it
    await vi.waitFor(() => {
      if (!$("live-blue").innerHTML.includes("blue hoy")) throw new Error("badge not painted");
    });
  });

  it("renders the whole page even when the live-blue fetch never settles", async () => {
    document.body.innerHTML = bodyHtml;
    window.history.replaceState(null, "", "/");
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (String(url).includes("dolarapi")) return new Promise(() => {}); // connected, never answers
        return { ok: true, json: async () => ARTIFACT };
      }),
    );
    vi.resetModules();
    await import("../src/main");
    await vi.waitFor(() => {
      if (!$("result").innerHTML) throw new Error("init not done");
    });
    expect($("result").innerHTML).toContain("de hoy");
    expect($("chart-decay").innerHTML).toContain("svg");
    expect($("live-blue").innerHTML).toBe(""); // only the badge is missing
  });

  it("loads the artifact from the bundler's asset URL, not the fixed public name", async () => {
    // The fixed /series.v1.json name stays the same across data refreshes, so a cached copy goes
    // stale. The ?url import makes Vite emit a content-hashed copy under /assets/ and hand back its URL.
    await boot();
    const urls = vi.mocked(fetch).mock.calls.map(([u]) => String(u));
    expect(urls).toContain(seriesUrl);
    expect(urls).not.toContain("/series.v1.json");
  });

  it("strips a stray query string on load", async () => {
    await boot({ search: "/?foo=bar" });
    expect(window.location.search).toBe("");
  });

  it("omits the live-blue badge when the rate is unavailable", async () => {
    await boot({ blue: null });
    expect($("live-blue").innerHTML).toBe("");
    expect($("result").innerHTML).toContain("de hoy");
  });

  it("shows an error and bails when the artifact fails to load", async () => {
    document.body.innerHTML = bodyHtml;
    window.history.replaceState(null, "", "/");
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (String(url).includes("dolarapi")) return { ok: true, json: async () => BLUE };
        return { ok: false, status: 404, json: async () => ({}) };
      }),
    );
    vi.resetModules();
    await import("../src/main");
    await vi.waitFor(() => {
      if (!$("source-badge").textContent?.includes("No se pudieron cargar")) throw new Error("not loaded");
    });
    expect($("result").innerHTML).toBe(""); // bailed before any render
  });
});

describe("start month", () => {
  it("shows the no-inflation copy when the start is the most recent month", async () => {
    await boot();
    setWhen(ARTIFACT.vintage.slice(0, 4), String(Number(ARTIFACT.vintage.slice(5))));
    expect($("headline-explain").innerHTML).toContain("mes más reciente");
  });

  it("clamps a month past the vintage back into range", async () => {
    await boot();
    setWhen("2026", "12"); // 2026-12 > vintage 2026-05 -> clamped
    expect($s("start-month").value).toBe(String(Number(ARTIFACT.vintage.slice(5))));
    expect($("headline-explain").innerHTML).toContain("mes más reciente");
  });

  it("names the source series for each splice segment", async () => {
    await boot();
    setWhen("2000", "1");
    expect($("headline-explain").innerHTML).toContain("IPC-GBA");
    setWhen("2010", "1");
    expect($("headline-explain").innerHTML).toContain("San Luis");
    setWhen("2020", "1");
    expect($("headline-explain").innerHTML).toContain("IPC Nacional");
  });
});

describe("USD section", () => {
  it("uses the estimated-blue copy for a pre-cepo month", async () => {
    await boot();
    setWhen("2003", "1"); // pre-2011 -> blue estimated
    expect($("usd-intro").innerHTML).toContain("no había dólar blue");
    expect($("usd-foot").innerHTML).toContain("arranca en 2011");
    expect($("chart-usd").innerHTML).toContain("US$");
  });

  it("shows the real blue and the then-brecha for a post-cepo month", async () => {
    await boot();
    setWhen("2015", "6"); // post-2011 -> real blue
    expect($("usd-intro").innerHTML).toContain("al blue");
    expect($("usd-intro").innerHTML).toContain("brecha");
    expect($("usd-foot").innerHTML).toContain("brecha era");
  });

  it("does not present a carried blue at the vintage as a real quote", async () => {
    const a = clone();
    a.series[a.series.length - 1].blue_est = true; // Bluelytics lagging the CPI -> carried rate
    await boot({ artifact: a });
    setWhen("2015", "6"); // post-cepo start, so only the "hoy" card is estimated
    expect($("usd-cards").innerHTML).toContain("—"); // hoy · blue is blanked, not quoted
    expect($("usd-intro").innerHTML).toContain("no hay cotización blue");
    expect($("usd-intro").innerHTML).not.toContain("brecha"); // no fabricated headline gap
  });

  it("does not narrate a carried post-cepo blue as a pre-cepo month", async () => {
    const a = clone();
    a.series[a.series.findIndex((r) => r.m === "2015-06")].blue_est = true; // Bluelytics gap -> carried quote
    await boot({ artifact: a });
    setWhen("2015", "6");
    expect($("usd-cards").innerHTML).toContain("—"); // entonces · blue is blanked, not quoted
    expect($("usd-intro").innerHTML).toContain("no hay cotización blue");
    expect($("usd-intro").innerHTML).not.toContain("no había dólar blue"); // that copy is pre-cepo only
    expect($("usd-foot").innerHTML).toContain("Sin cotización blue");
    expect($("usd-foot").innerHTML).not.toContain("arranca en 2011");
  });
});

describe("inflation toggle", () => {
  it("switches between annual and monthly, exposing the active state via aria-pressed", async () => {
    await boot();
    const monthly = document.querySelector('[data-freq="monthly"]') as HTMLButtonElement;
    const annual = document.querySelector('[data-freq="annual"]') as HTMLButtonElement;
    expect(annual.getAttribute("aria-pressed")).toBe("true");
    monthly.click();
    expect($("infl-caption").textContent).toContain("mensual");
    expect($("chart-infl").innerHTML).toContain("svg");
    expect(monthly.getAttribute("aria-pressed")).toBe("true");
    expect(annual.getAttribute("aria-pressed")).toBe("false");
    annual.click();
    expect($("infl-caption").textContent).toContain("interanual");
    expect(annual.getAttribute("aria-pressed")).toBe("true");
    expect(monthly.getAttribute("aria-pressed")).toBe("false");
  });
});

describe("amount control", () => {
  it("reformats and recomputes on input, and tolerates zero", async () => {
    await boot();
    setInput("amount-number", "1000000");
    expect($i("amount-number").value).toBe("1.000.000");
    expect($("result").innerHTML).toContain("de hoy");
    setInput("amount-number", "0");
    expect($("result").innerHTML).toContain("de hoy");
    setInput("amount-number", "abc"); // no digits -> formatted "" branch
    expect($i("amount-number").value).toBe("");
  });
});

describe("methodology", () => {
  it("describes the FX aggregation the pipeline actually uses", async () => {
    await boot();
    // load.monthly_from_rows keeps the last daily value of the month; it does not average.
    expect($("methodology-body").innerHTML).toContain("fin de mes");
    expect($("methodology-body").innerHTML).not.toContain("promedia");
  });

  it("marks a mismatch when an anchor year is not reproduced", async () => {
    const a = clone();
    a.anchors.indec_nacional_annual = { "2024": 50 }; // real 2024 ≈ 118 -> ✗
    await boot({ artifact: a });
    expect($("methodology-body").innerHTML).toContain("✗");
  });
});

describe("window events", () => {
  it("hides/shows the sticky bar on scroll and scrolls up on click", async () => {
    await boot();
    const headline = $("headline");
    headline.getBoundingClientRect = () => ({ bottom: 100 }) as DOMRect;
    window.dispatchEvent(new Event("scroll"));
    expect($("sticky-bar").hidden).toBe(true);
    headline.getBoundingClientRect = () => ({ bottom: 0 }) as DOMRect;
    window.dispatchEvent(new Event("scroll"));
    expect($("sticky-bar").hidden).toBe(false);
    const scroll = vi.spyOn(Element.prototype, "scrollIntoView");
    $("sticky-bar").click();
    expect(scroll).toHaveBeenCalledTimes(1);
    // "Editar" is a real button (keyboard-reachable); its click bubbles to the bar's handler.
    ($("sticky-bar").querySelector("button.sticky-edit") as HTMLButtonElement).click();
    expect(scroll).toHaveBeenCalledTimes(2);
  });

  it("re-renders visuals on resize (debounced)", async () => {
    await boot();
    window.dispatchEvent(new Event("resize"));
    await new Promise((r) => setTimeout(r, 200));
    expect($("chart-index").innerHTML).toContain("svg");
  });

  it("re-renders on a dark-mode change", async () => {
    let handler: (() => void) | undefined;
    vi.stubGlobal("matchMedia", () => ({
      matches: false,
      addEventListener: (_: string, cb: () => void) => {
        handler = cb;
      },
    }));
    await boot();
    expect(handler).toBeTypeOf("function");
    handler?.();
    expect($("result").innerHTML).toContain("de hoy");
  });
});

describe("exported helpers", () => {
  it("reformatWithCaret tolerates a null caret position", async () => {
    const M = await boot();
    const inp = document.createElement("input");
    inp.value = "1234567";
    Object.defineProperty(inp, "selectionStart", { value: null, configurable: true });
    M.reformatWithCaret(inp);
    expect(inp.value).toBe("1.234.567");
  });
});
