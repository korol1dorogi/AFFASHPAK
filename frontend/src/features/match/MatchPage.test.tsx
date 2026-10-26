import { fireEvent, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Schemas } from "@/api/client";
import { MatchPage } from "@/features/match/MatchPage";
import { mockApi, renderRoutes } from "@/test/utils";

/** Persona 1 (демо): an overdraft of 900 000 ₽ from the statement's turnover. */
const RESULT: Schemas["RecommendationResult"] = {
  need_type: "cash_gap",
  is_preliminary: true,
  stop_factors: [],
  offers: [
    {
      rank: 1,
      product: {
        code: "overdraft_basic",
        kind: "overdraft",
        name: "Овердрафт для бизнеса (демо)",
        description: "",
        rate_min: "0.20",
        rate_max: "0.30",
        term_min_months: 1,
        term_max_months: 12,
        amount_min: "100000.00",
        amount_max: "10000000.00",
        is_revolving: true,
        collateral_required: false,
        params: {},
        requirements: { min_business_age_months: 6, legal_forms: ["ip", "ooo"] },
        required_documents: [],
      },
      amount: "900000.00",
      term_months: 12,
      rate: "0.2400",
      monthly_payment: null,
      fits: true,
      reasons: [
        {
          metric: "overdraft_limit",
          value: "900000.00",
          threshold: null,
          passed: true,
          message: "30% от среднемесячных поступлений 3 000 000 ₽",
        },
      ],
    },
    {
      rank: 2,
      product: {
        code: "working_capital_loan_basic",
        kind: "working_capital_loan",
        name: "Кредит на пополнение оборотных средств (демо)",
        description: "",
        rate_min: "0.22",
        rate_max: "0.30",
        term_min_months: 3,
        term_max_months: 24,
        amount_min: "300000.00",
        amount_max: "30000000.00",
        is_revolving: false,
        collateral_required: false,
        params: {},
        requirements: { min_business_age_months: 6, legal_forms: ["ip", "ooo"] },
        required_documents: [],
      },
      amount: "1500000.00",
      term_months: 12,
      rate: "0.2400",
      monthly_payment: "141838.45",
      fits: true,
      reasons: [],
    },
  ],
};

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("MatchPage — where the amounts come from (SRC7)", () => {
  it("the amount, the payment and the reasons' amounts are counted", async () => {
    mockApi({ "POST /api/recommendations": RESULT });
    renderRoutes([{ path: "/app/match", element: <MatchPage /> }], "/app/match?need=cash_gap");
    fireEvent.click(screen.getByRole("button", { name: "Подобрать продукт" }));

    const overdraft = await screen.findByRole("article", { name: "Овердрафт для бизнеса (демо)" });
    const amount = within(overdraft).getAllByText("900 000 ₽")[0];
    expect(amount?.parentElement).toHaveTextContent("900 000 ₽расчёт");
    const reasons = within(overdraft).getByRole("list", { name: "Обоснование" });
    expect(within(reasons).getByText("расчёт")).toBeInTheDocument();

    const loan = screen.getByRole("article", {
      name: "Кредит на пополнение оборотных средств (демо)",
    });
    expect(within(loan).getByText("1 500 000 ₽").parentElement).toHaveTextContent(
      "1 500 000 ₽расчёт",
    );
    expect(within(loan).getByText("141 838,45 ₽").parentElement).toHaveTextContent(
      "платёж 141 838,45 ₽расчёт",
    );
  });
});

describe("MatchPage — the result is announced (UX2)", () => {
  it("a polite live region says how many options were found", async () => {
    mockApi({ "POST /api/recommendations": RESULT });
    renderRoutes([{ path: "/app/match", element: <MatchPage /> }], "/app/match?need=cash_gap");
    fireEvent.click(screen.getByRole("button", { name: "Подобрать продукт" }));
    await screen.findByRole("article", { name: "Овердрафт для бизнеса (демо)" });
    expect(screen.getByText("Подобрано продуктов: 2", { selector: "[aria-live]" })).toHaveAttribute(
      "aria-live",
      "polite",
    );
  });
});
