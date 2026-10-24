import { describe, expect, it } from "vitest";

import type { Schemas } from "@/api/client";
import { checkFacts, checkMeaning } from "@/features/bank-application/checkFacts";
import { persona4Card } from "@/features/bank-application/fixtures";
import { CHECK_FIELD, CHECK_MEANING } from "@/texts";

type Check = Schemas["Check"];

/**
 * Every `data` key of docs/external/*.yaml (SRC8). A key added to a contract must get a label
 * here and in CHECK_FIELD, or the tab would hide it.
 */
const CONTRACT_KEYS = {
  egrul: [
    "registry_status",
    "unreliable_address",
    "unreliable_director",
    "pending_exclusion",
    "registered_at",
    "okved",
    "okved_name",
    "address",
    "director_name",
    "founders",
    "kpp",
  ],
  transparent_business: [
    "mass_address",
    "mass_director",
    "tax_arrears",
    "accounts_suspended",
    "employees",
    "tax_regime",
    "msp_category",
    "taxes_paid",
  ],
  bki: ["current_overdue_days", "past_overdue_max_days", "obligations"],
  bank_account: ["months", "period", "account_masked"],
} as const;

function check(source: Check["source"], status: Check["status"], data: Check["data"]): Check {
  return {
    source,
    status,
    summary: "",
    data,
    checked_at: "2026-10-20T09:30:10Z",
    received_at: "2026-10-20T09:30:10Z",
    response_sha256: "0".repeat(64),
    simulator_version: "datagen-2026.10-v1",
  };
}

/** Money and shares are printed with no-break spaces; compare them as plain ones. */
const plain = (value: string | string[]) =>
  Array.isArray(value) ? value.map((item) => item.replace(/\s/g, " ")) : value.replace(/\s/g, " ");

const byLabel = (facts: ReturnType<typeof checkFacts>) =>
  Object.fromEntries(facts.map((fact) => [fact.label, plain(fact.value)]));

describe("checkFacts — every field is labelled (SRC6)", () => {
  it.each(Object.entries(CONTRACT_KEYS))("%s: every contract key has a label", (_, keys) => {
    // okved_name is shown inside «Вид деятельности (ОКВЭД)», not on its own.
    for (const key of keys.filter((key) => key !== "okved_name")) {
      expect(CHECK_FIELD[key], key).toBeTruthy();
    }
  });

  it("ЕГРЮЛ of persona 4: status, OKVED with its name, founders with shares, KPP", () => {
    const egrul = persona4Card().checks[0] as Check;
    const facts = byLabel(checkFacts(egrul));
    expect(facts["Статус в реестре"]).toBe("Действует");
    expect(facts["Вид деятельности (ОКВЭД)"]).toBe("31.09 — Производство прочей мебели");
    expect(facts.Учредители).toEqual([
      "Полякова Маргарита Олеговна (демо) — ИНН 000300000227, доля 50 %",
      "Виноградов Михаил Петрович (демо) — ИНН 000300000308, доля 30 %",
      "Григорьева Надежда Павловна (демо) — ИНН 000300000474, доля 20 %",
    ]);
    expect(facts.КПП).toBe("000101001");
    expect(facts["Отметка о недостоверности адреса"]).toBe("нет");
    expect(checkFacts(egrul).some((fact) => fact.risk)).toBe(false);
  });

  it("an ИП has no KPP — said in words, not «null»", () => {
    const facts = byLabel(
      checkFacts(check("egrul", "ok", { registry_status: "active", kpp: null })),
    );
    expect(facts.КПП).toBe("нет — у ИП КПП не бывает");
  });

  it("ЕГРЮЛ marks and liquidation are risks", () => {
    const facts = checkFacts(
      check("egrul", "warning", {
        registry_status: "liquidating",
        unreliable_address: true,
        unreliable_director: false,
        pending_exclusion: true,
      }),
    );
    expect(facts.filter((fact) => fact.risk).map((fact) => fact.label)).toEqual([
      "Статус в реестре",
      "Отметка о недостоверности адреса",
      "Предстоящее исключение из реестра",
    ]);
    expect(byLabel(facts)["Статус в реестре"]).toBe("Ликвидируется");
  });

  it("«Прозрачный бизнес» with the FNS profile and suspended accounts (e_accounts_suspended)", () => {
    const facts = checkFacts(
      check("transparent_business", "warning", {
        mass_address: false,
        mass_director: false,
        tax_arrears: "0.00",
        employees: 5,
        tax_regime: "usn_income_minus_expenses",
        msp_category: "micro",
        taxes_paid: "612000.00",
        accounts_suspended: true,
      }),
    );
    expect(byLabel(facts)).toEqual({
      "Массовый адрес регистрации": "нет",
      "Массовый руководитель": "нет",
      "Налоговая задолженность": "нет",
      "Приостановка операций по счетам": "да",
      "Численность сотрудников": "5 чел.",
      "Налоговый режим": "УСН «доходы минус расходы»",
      "Категория МСП": "Микропредприятие",
      "Уплачено налогов за год": "612 000 ₽",
    });
    expect(facts.filter((fact) => fact.risk).map((fact) => fact.label)).toEqual([
      "Приостановка операций по счетам",
    ]);
  });

  it("a tax debt is shown as money and is a risk", () => {
    const [, , debt] = checkFacts(
      check("transparent_business", "warning", {
        mass_address: false,
        mass_director: false,
        tax_arrears: "125000.00",
      }),
    );
    expect(debt?.risk).toBe(true);
    expect(plain(debt?.value ?? "")).toBe("125 000 ₽");
  });

  it("БКИ of persona 4: overdue in days, loans and leasing in words", () => {
    const bki = persona4Card().checks[2] as Check;
    const facts = checkFacts(bki);
    const lines = byLabel(facts);
    expect(lines["Текущая просрочка"]).toBe("нет");
    expect(lines["Самая долгая прошлая просрочка"]).toBe("10 дн.");
    const debts = lines["Действующие кредиты и лизинг"] as string[];
    expect(debts).toHaveLength(2);
    expect(debts[0]).toMatch(/^Кредит: платёж 600 000 ₽ в месяц, остаток 19 800 000 ₽, с /);
    expect(debts[1]).toMatch(/^Лизинг: платёж 400 000 ₽ в месяц/);
    expect(facts.some((fact) => fact.risk)).toBe(false); // 10 days in the past is not a risk
  });

  it("БКИ: a current overdue and a past one over 30 days are risks; no debts is «нет»", () => {
    const facts = checkFacts(
      check("bki", "failed", {
        current_overdue_days: 31,
        past_overdue_max_days: 31,
        obligations: [],
      }),
    );
    expect(byLabel(facts)["Действующие кредиты и лизинг"]).toBe("нет");
    expect(facts.filter((fact) => fact.risk)).toHaveLength(2);
  });

  it("the bank account: months of the statement, the last month and the masked number", () => {
    const facts = byLabel(
      checkFacts(
        check("bank_account", "ok", {
          period: "2026-09",
          months: 18,
          account_masked: "40802810••••••••0034",
        }),
      ),
    );
    expect(facts).toEqual({
      Выписка: "18 мес",
      "Последний месяц выписки": "2026-09",
      Счёт: "40802810••••••••0034",
    });
  });

  it("an unknown key or an adapter's own flag is not shown raw", () => {
    expect(checkFacts(check("egrul", "ok", { rating: "AAA" }))).toEqual([]);
    expect(checkFacts(check("bank_account", "unavailable", { not_connected: true }))).toEqual([]);
    expect(checkFacts(check("bki", "consent_missing", { consent_missing: true }))).toEqual([]);
  });
});

describe("checkMeaning — what the status means", () => {
  it.each([
    ["egrul", "ok", "Компания действует"],
    ["egrul", "warning", "ликвидируется — это отказ"],
    ["egrul", "not_found", "Компании нет в реестре — это отказ"],
    ["egrul", "failed", "Компании нет в реестре — это отказ"], // stored before SRC2
    ["transparent_business", "warning", "Приостановка операций по счетам — отказ"],
    ["bki", "warning", "это снижает баллы"],
    ["bki", "failed", "Текущая просрочка больше 30 дней — это отказ"],
    ["bki", "unavailable", "Это не отказ"],
    ["bki", "restricted", "сведения скрыты. Это не отказ"],
    ["bki", "consent_missing", "не дал согласие"],
    ["bank_account", "ok", "Выписка получена"],
  ] as const)("%s %s → «…%s…»", (source, status, text) => {
    expect(checkMeaning(check(source, status, {}))).toContain(text);
  });

  it("every status has a meaning of its own", () => {
    const statuses = Object.keys(CHECK_MEANING.status) as Check["status"][];
    expect(statuses).toHaveLength(7);
    for (const status of statuses) expect(CHECK_MEANING.status[status]).toBeTruthy();
  });

  it("an account the client did not connect says so", () => {
    expect(checkMeaning(check("bank_account", "unavailable", { not_connected: true }))).toBe(
      CHECK_MEANING.notConnected,
    );
  });
});
