// jsdom doesn't implement the layout/SVG APIs Observable Plot (via D3) reaches for, nor
// matchMedia. We stub just enough that real Plot renders deterministically in tests — so the
// chart code (including the inline accessor callbacks Plot invokes) is genuinely exercised.
import { beforeAll } from "vitest";

beforeAll(() => {
  const svgProto = (globalThis as unknown as { SVGElement: { prototype: Record<string, unknown> } }).SVGElement
    ?.prototype;
  if (svgProto) {
    if (!svgProto.getBBox) {
      svgProto.getBBox = () => ({ x: 0, y: 0, width: 0, height: 0 });
    }
    if (!svgProto.getComputedTextLength) {
      svgProto.getComputedTextLength = () => 0;
    }
    if (!svgProto.getCTM) {
      svgProto.getCTM = () => null;
    }
  }

  // The sticky bar calls scrollIntoView; jsdom doesn't implement it.
  if (!Element.prototype.scrollIntoView) {
    Element.prototype.scrollIntoView = () => {};
  }

  // main.ts subscribes to the dark-mode media query; jsdom has no matchMedia.
  if (!window.matchMedia) {
    window.matchMedia = (query: string) =>
      ({
        matches: false,
        media: query,
        onchange: null,
        addEventListener: () => {},
        removeEventListener: () => {},
        addListener: () => {},
        removeListener: () => {},
        dispatchEvent: () => false,
      }) as unknown as MediaQueryList;
  }
});
