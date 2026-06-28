import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchBlue } from "../src/usd";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("fetchBlue", () => {
  it("returns the rate on a valid response", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, json: async () => ({ venta: 1515 }) })));
    expect(await fetchBlue()).toEqual({ venta: 1515 });
  });

  it("returns null on a non-ok response", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: false, json: async () => ({}) })));
    expect(await fetchBlue()).toBeNull();
  });

  it("returns null on a bad shape (missing/non-positive venta)", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, json: async () => ({ venta: 0 }) })));
    expect(await fetchBlue()).toBeNull();
  });

  it("returns null when fetch throws", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new Error("offline"); }));
    expect(await fetchBlue()).toBeNull();
  });
});
