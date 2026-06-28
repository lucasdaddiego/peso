import { describe, expect, it } from "vitest";
import {
  fmtARS, fmtMonth, fmtMonthShort, fmtNum, fmtPct, fmtPctBig, fmtShort, fmtUSD, fmtX, parseMoney,
} from "../src/format";

describe("format", () => {
  it("fmtARS / fmtNum round and group", () => {
    expect(fmtARS(1234567.8)).toBe("$1.234.568");
    expect(fmtNum(1000)).toBe("1.000");
  });

  it("fmtUSD picks decimals by magnitude", () => {
    expect(fmtUSD(12.34)).toContain(","); // < 100 -> one decimal
    expect(fmtUSD(1500)).toBe("US$1.500"); // >= 100 -> no decimals
  });

  it("fmtShort across magnitudes", () => {
    expect(fmtShort(2_500_000)).toBe("$2,5M");
    expect(fmtShort(12_000)).toBe("$12k");
    expect(fmtShort(500)).toBe("$500");
  });

  it("fmtX picks decimals by magnitude", () => {
    expect(fmtX(250)).toBe("250×");
    expect(fmtX(12.3)).toBe("12,3×");
    expect(fmtX(1.25)).toBe("1,25×");
  });

  it("fmtPct and fmtPctBig", () => {
    expect(fmtPct(53.8)).toBe("53,8%");
    expect(fmtPctBig(12345.6)).toBe("12.346%"); // large -> no decimals
    expect(fmtPctBig(53.8)).toBe("53,8%"); // small -> one decimal
  });

  it("fmtMonth / fmtMonthShort", () => {
    expect(fmtMonth("2003-01")).toBe("enero 2003");
    expect(fmtMonthShort("2016-12")).toBe("dic 16");
  });

  it("parseMoney strips separators and handles blanks", () => {
    expect(parseMoney("1.234.567")).toBe(1234567);
    expect(parseMoney("US$ 12,5")).toBe(125);
    expect(parseMoney("")).toBe(0);
  });
});
