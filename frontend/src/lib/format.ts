/**
 * Money, rates and dates for display (docs/frontend.md §5).
 * Money and rates are decimal STRINGS from the API ("2009314.00", "0.2400"); we never turn them
 * into floats — no arithmetic with money on the frontend, only string formatting.
 */

const NBSP = " ";
const MONEY_RE = /^(-?)(\d+)(?:\.(\d+))?$/;

function groupThousands(digits: string): string {
  return digits.replace(/\B(?=(\d{3})+(?!\d))/g, NBSP);
}

/** "2009314.00" → "2 009 314 ₽"; "189999.92" → "189 999,92 ₽". Kopecks only when non-zero. */
export function formatMoney(value: string | null | undefined, { currency = true } = {}): string {
  if (value === null || value === undefined || value === "") return "—";
  const match = MONEY_RE.exec(value.trim());
  if (!match) return value;
  const [, sign = "", intPart = "0", frac = ""] = match;
  const kopecks = frac.padEnd(2, "0").slice(0, 2);
  const body =
    groupThousands(intPart.replace(/^0+(?=\d)/, "")) + (kopecks === "00" ? "" : `,${kopecks}`);
  return `${sign ? "−" : ""}${body}${currency ? `${NBSP}₽` : ""}`;
}

/** Shift a decimal string's point by `places` (positive = ×10^places) without floats. */
function shiftDecimal(value: string, places: number): string | null {
  const match = MONEY_RE.exec(value.trim().replace(",", "."));
  if (!match) return null;
  const [, sign = "", intPart = "0", frac = ""] = match;
  let digits = intPart + frac;
  let point = intPart.length + places;
  if (point < 0) {
    digits = "0".repeat(-point) + digits;
    point = 0;
  }
  if (point > digits.length) digits = digits.padEnd(point, "0");
  const whole = digits.slice(0, point).replace(/^0+(?=\d)/, "") || "0";
  const rest = digits.slice(point).replace(/0+$/, "");
  return `${sign}${whole}${rest ? `.${rest}` : ""}`;
}

/** "0.2400" → "24 %"; "0.235" → "23,5 %". */
export function formatRate(value: string | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  const percent = shiftDecimal(value, 2);
  if (percent === null) return value;
  return `${percent.replace(".", ",")}${NBSP}%`;
}

/** What a person types as a rate in percent ("24", "23,5") → the API's annual fraction ("0.24"). */
export function percentToFraction(input: string): string | null {
  const cleaned = input.replace(/\s/g, "").replace("%", "");
  if (!/^\d+(?:[.,]\d+)?$/.test(cleaned)) return null;
  return shiftDecimal(cleaned, -2);
}

/** Decimal coefficient for display: "1.2500" → "1,25", "0.8000" → "0,8". */
export function formatDecimal(value: string | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  const normalized = shiftDecimal(value, 0);
  return normalized === null ? value : normalized.replace(".", ",").replace("-", "−");
}

/**
 * What a person types into a money field ("5 300 000", "1200,5") → API string ("5300000.00").
 * Returns null when it is not a valid amount.
 */
export function parseMoneyInput(input: string): string | null {
  const cleaned = input.replace(/[\s ₽]/g, "");
  const match = /^(\d+)(?:[.,](\d{0,2}))?$/.exec(cleaned);
  if (!match) return null;
  const [, intPart = "0", frac = ""] = match;
  return `${intPart.replace(/^0+(?=\d)/, "")}.${frac.padEnd(2, "0")}`;
}

/** Display form while typing: digits grouped, comma kept ("5300000,5" → "5 300 000,5"). */
export function formatMoneyInput(input: string): string {
  const cleaned = input.replace(/[^\d.,]/g, "").replace(".", ",");
  const [intPart = "", ...rest] = cleaned.split(",");
  const frac = rest.join("").slice(0, 2);
  const grouped = groupThousands(intPart.replace(/^0+(?=\d)/, ""));
  return cleaned.includes(",") ? `${grouped},${frac}` : grouped;
}

const dateFormatter = new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "long" });
const dateYearFormatter = new Intl.DateTimeFormat("ru-RU", {
  day: "numeric",
  month: "long",
  year: "numeric",
});
const timeFormatter = new Intl.DateTimeFormat("ru-RU", { hour: "2-digit", minute: "2-digit" });
const relative = new Intl.RelativeTimeFormat("ru-RU", { numeric: "auto" });

/** "14 октября" (with the year when it is not the current one). */
export function formatDate(iso: string | null | undefined, now = new Date()): string {
  if (!iso) return "—";
  const date = new Date(iso);
  return (date.getFullYear() === now.getFullYear() ? dateFormatter : dateYearFormatter).format(
    date,
  );
}

/** "14 октября, 10:12". */
export function formatDateTime(iso: string | null | undefined, now = new Date()): string {
  if (!iso) return "—";
  return `${formatDate(iso, now)}, ${timeFormatter.format(new Date(iso))}`;
}

/** "12 минут назад" within a day, otherwise "14 октября, 10:12". */
export function formatRelative(iso: string | null | undefined, now = new Date()): string {
  if (!iso) return "—";
  const seconds = Math.round((new Date(iso).getTime() - now.getTime()) / 1000);
  const abs = Math.abs(seconds);
  if (abs < 60) return "только что";
  if (abs < 3600) return relative.format(Math.round(seconds / 60), "minute");
  if (abs < 86400) return relative.format(Math.round(seconds / 3600), "hour");
  return formatDateTime(iso, now);
}

/** How to greet a person: «Анна Сергеевна» for «Фамилия Имя Отчество», else the first word. */
export function greetingName(fullName: string): string {
  const words = fullName
    .replace(/\(демо\)/giu, "")
    .split(/\s+/u)
    .filter(Boolean);
  return words.length === 3 ? `${words[1]} ${words[2]}` : (words[0] ?? "");
}
