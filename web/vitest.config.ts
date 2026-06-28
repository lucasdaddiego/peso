import { defineConfig } from "vitest/config";

// Tests run under jsdom (test/setup.ts polyfills the SVG/matchMedia gaps Observable Plot needs).
// Coverage gate is a hard 100% across src/ — types.ts is type-only (no emitted JS) so it's excluded.
export default defineConfig({
  test: {
    environment: "jsdom",
    setupFiles: ["./test/setup.ts"],
    include: ["test/**/*.test.ts"],
    coverage: {
      provider: "v8",
      include: ["src/**/*.ts"],
      exclude: ["src/types.ts"],
      reporter: ["text", "text-summary", "html"],
      thresholds: {
        lines: 100,
        functions: 100,
        branches: 100,
        statements: 100,
      },
    },
  },
});
