import type { Schemas } from "@/api/client";
import { formatDate, formatMoney, formatRate } from "@/lib/format";
import { CHECK_FIELD, CHECK_MEANING, REGISTRY_STATUS, CHECK_VALUE as V } from "@/texts";

type Check = Schemas["Check"];

/** One labelled line of a source answer: a word for every code, a list for founders and debts. */
export interface CheckFact {
  key: string;
  label: string;
  value: string | string[];
  /** A sign of risk (a mark, a debt, an overdue): shown with a word, not only a colour. */
  risk: boolean;
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);
const text = (value: unknown) => (typeof value === "string" ? value : "");
const count = (value: unknown) => (typeof value === "number" ? value : 0);
const yesNo = (value: unknown) => (value === true ? V.yes : V.no);
const positive = (money: unknown) => Number(text(money)) > 0;

/** Keys of docs/external/*.yaml in display order; okved_name goes with okved. */
const ORDER = Object.keys(CHECK_FIELD);

function fact(key: string, data: Record<string, unknown>): CheckFact | null {
  const raw = data[key];
  const line = (value: string | string[], risk = false) => ({
    key,
    label: CHECK_FIELD[key] as string,
    value,
    risk,
  });
  switch (key) {
    case "registry_status": {
      const status = text(raw) as Schemas["RegistryStatus"];
      return line(REGISTRY_STATUS[status] ?? text(raw), status !== "active");
    }
    case "registered_at":
      return line(formatDate(text(raw)));
    case "okved":
      return line([text(raw), text(data.okved_name)].filter(Boolean).join(" — "));
    case "kpp":
      return line(raw === null ? V.noKpp : text(raw));
    case "unreliable_address":
    case "unreliable_director":
    case "pending_exclusion":
    case "mass_address":
    case "mass_director":
    case "accounts_suspended":
      return line(yesNo(raw), raw === true);
    case "tax_arrears":
      return line(positive(raw) ? formatMoney(text(raw)) : V.no, positive(raw));
    case "taxes_paid":
      return line(formatMoney(text(raw)));
    case "employees":
      return line(V.people(count(raw)));
    case "tax_regime":
      return line(V.taxRegime[text(raw)] ?? text(raw));
    case "msp_category":
      return line(V.mspCategory[text(raw)] ?? text(raw));
    case "current_overdue_days":
      return line(count(raw) ? V.days(count(raw)) : V.no, count(raw) > 0);
    case "past_overdue_max_days":
      return line(count(raw) ? V.days(count(raw)) : V.no, count(raw) > 30);
    case "months":
      return line(V.months(count(raw)));
    case "founders": {
      const founders = Array.isArray(raw) ? raw.filter(isRecord) : [];
      return line(
        founders.map((item) =>
          V.founder(text(item.name), text(item.inn), formatRate(text(item.share))),
        ),
      );
    }
    case "obligations": {
      const debts = Array.isArray(raw) ? raw.filter(isRecord) : [];
      return line(
        debts.length
          ? debts.map((item) =>
              V.obligation(
                V.obligationKind[text(item.kind)] ?? text(item.kind),
                formatMoney(text(item.monthly_payment)),
                formatMoney(text(item.balance)),
                formatDate(text(item.opened_at)),
              ),
            )
          : V.no,
      );
    }
    default:
      return typeof raw === "string" || typeof raw === "number" ? line(String(raw)) : null;
  }
}

/**
 * The answer of a source as labelled lines (SRC6). Only keys the contracts know are shown:
 * an unknown key would be a technical one, so it is left out rather than printed raw.
 */
export function checkFacts(check: Check): CheckFact[] {
  const data = check.data;
  return ORDER.filter((key) => key in data)
    .map((key) => fact(key, data))
    .filter((item): item is CheckFact => item !== null);
}

/** «Что это значит» for the status of this source. */
export function checkMeaning(check: Check): string {
  if (check.data.not_connected === true) return CHECK_MEANING.notConnected;
  return CHECK_MEANING.bySource[check.source]?.[check.status] ?? CHECK_MEANING.status[check.status];
}
