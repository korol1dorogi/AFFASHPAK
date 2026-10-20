import { describe, expect, it } from "vitest";

import {
  formatDate,
  formatDecimal,
  formatMoney,
  formatMoneyInput,
  formatRate,
  formatRelative,
  greetingName,
  parseMoneyInput,
  percentToFraction,
} from "./format";

const sp = (text: string) => text.replace(/ /g, " ");

describe("formatMoney", () => {
  it.each([
    ["2009314.00", "2 009 314 ₽"],
    ["189999.92", "189 999,92 ₽"],
    ["900000", "900 000 ₽"],
    ["0.50", "0,50 ₽"],
    ["-1500.00", "−1 500 ₽"],
    ["100000000.10", "100 000 000,10 ₽"],
  ])("%s → %s", (value, expected) => {
    expect(formatMoney(value)).toBe(sp(expected));
  });

  it("shows a dash for missing values and keeps garbage as is", () => {
    expect(formatMoney(null)).toBe("—");
    expect(formatMoney("abc")).toBe("abc");
  });

  it("can omit the currency", () => {
    expect(formatMoney("5300000.00", { currency: false })).toBe(sp("5 300 000"));
  });
});

describe("rates", () => {
  it.each([
    ["0.2400", "24 %"],
    ["0.235", "23,5 %"],
    ["0.2", "20 %"],
    ["1.25", "125 %"],
    ["0.005", "0,5 %"],
  ])("formatRate(%s) → %s", (value, expected) => {
    expect(formatRate(value)).toBe(sp(expected));
  });

  it.each([
    ["24", "0.24"],
    ["23,5", "0.235"],
    ["0,5", "0.005"],
    ["100", "1"],
  ])("percentToFraction(%s) → %s", (input, expected) => {
    expect(percentToFraction(input)).toBe(expected);
  });

  it("rejects non-numbers", () => {
    expect(percentToFraction("двадцать")).toBeNull();
  });
});

describe("formatDecimal", () => {
  it.each([
    ["1.2500", "1,25"],
    ["0.8000", "0,8"],
    ["6.0000", "6"],
  ])("%s → %s", (value, expected) => {
    expect(formatDecimal(value)).toBe(expected);
  });
});

describe("money input", () => {
  it.each([
    ["5 300 000", "5300000.00"],
    ["1200,5", "1200.50"],
    ["900000.00", "900000.00"],
    ["007", "7.00"],
  ])("parseMoneyInput(%s) → %s", (input, expected) => {
    expect(parseMoneyInput(input)).toBe(expected);
  });

  it.each(["", "12,345", "1.2.3", "сто"])("parseMoneyInput(%s) → null", (input) => {
    expect(parseMoneyInput(input)).toBeNull();
  });

  it("groups digits while typing", () => {
    expect(formatMoneyInput("5300000")).toBe(sp("5 300 000"));
    expect(formatMoneyInput("5300000,5")).toBe(sp("5 300 000,5"));
    expect(formatMoneyInput("12a3")).toBe("123");
  });
});

describe("dates", () => {
  const now = new Date("2026-10-20T12:00:00+03:00");

  it("omits the year for the current year", () => {
    expect(formatDate("2026-10-14T07:12:00Z", now)).toBe("14 октября");
    expect(formatDate("2025-10-14T07:12:00Z", now)).toMatch(/2025/);
  });

  it("is relative within a day", () => {
    expect(formatRelative("2026-10-20T08:48:00Z", now)).toBe("12 минут назад");
    expect(formatRelative("2026-10-20T08:59:40Z", now)).toBe("только что");
  });
});

describe("greetingName", () => {
  it("greets by first name and patronymic, or by the first word", () => {
    expect(greetingName("Лаврова Анна Сергеевна (демо)")).toBe("Анна Сергеевна");
    expect(greetingName("Анна Демо")).toBe("Анна");
    expect(greetingName("Ирина")).toBe("Ирина");
    expect(greetingName("")).toBe("");
  });
});
