import { screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Schemas } from "@/api/client";
import { ApplicationPage } from "@/features/applications/ApplicationPage";
import { mockApi, renderRoutes } from "@/test/utils";
import { APPROVAL_PLAN } from "@/texts";

/** Persona 5 (демо): grade E, 47 points; the backend's plan to grade C (scoring/plan.py). */
const PLAN: Schemas["ApprovalPlan"] = {
  current_total: 47,
  target_total: 60,
  target_grade: "C",
  steps: [
    {
      metric: "counterparty_concentration",
      current: "0.8000",
      target: "0.5",
      points: 7,
      message:
        "Найдите ещё покупателей, чтобы на крупнейшего приходилось не больше 50% поступлений (сейчас 80%)",
    },
    {
      metric: "revenue_trend",
      current: "0.8000",
      target: "0.9",
      points: 6,
      message: "Верните выручку хотя бы к 90% от прошлого года (сейчас 80%)",
    },
  ],
};

const IMPROVEMENTS = [
  "Снизьте платежи по текущим долгам или увеличьте остаток денег после расходов",
  "Снизьте долг до 3,5 годовой прибыли (EBITDA) и меньше",
  "Верните выручку хотя бы к уровню прошлого года",
  "Найдите ещё покупателей, чтобы на крупнейшего приходилось не больше 50% поступлений",
];

function declined(plan: Schemas["ApprovalPlan"] | null): Schemas["ApplicationDetail"] {
  return {
    id: 51,
    company_id: 5,
    need_type: "working_capital",
    purpose: "Закупка сырья (демо)",
    product_code: "working_capital_loan_basic",
    requested_amount: "3000000.00",
    term_months: 12,
    invoice_amount: null,
    collateral_description: null,
    status: "declined",
    version: 3,
    prefill_source: "recommendation",
    available_actions: [],
    created_at: "2026-10-23T09:00:00Z",
    submitted_at: "2026-10-23T09:05:00Z",
    status_changed_at: "2026-10-23T09:06:00Z",
    offer: null,
    open_info_requests: [],
    decision: {
      id: 9,
      application_id: 51,
      outcome: "declined",
      decided_by: "auto",
      is_preliminary: true,
      grade: "E",
      policy_version: "2026.10-v1",
      reasons: [
        {
          metric: "score_total",
          value: "47",
          threshold: "75",
          passed: false,
          message: "47 баллов из 100, это оценка E",
        },
      ],
      improvements: IMPROVEMENTS,
      comment: null,
      created_at: "2026-10-23T09:06:00Z",
      approval_plan: plan,
    },
  };
}

function open(detail: Schemas["ApplicationDetail"]) {
  mockApi({
    "GET /api/applications/51": detail,
    "GET /api/applications/51/events": [],
    "GET /api/applications/51/documents": [],
    "GET /api/products": [],
  });
  renderRoutes(
    [{ path: "/app/applications/:id", element: <ApplicationPage /> }],
    "/app/applications/51",
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("ApprovalPlan on a decline", () => {
  it("persona 5: two concrete steps with targets and points, from 47 to grade C", async () => {
    open(declined(PLAN));
    const plan = await screen.findByRole("region", { name: "Как получить одобрение" });
    expect(plan).toHaveTextContent(
      "Сейчас у заявки 47 баллов из 100, оценка риска — E. Если выполнить шаги ниже, наберётся " +
        "60 баллов и оценка станет C. Тогда заявку рассмотрит сотрудник банка.",
    );
    // «Оценка риска» is a term: the plan says what it means (UX2).
    expect(plan).toHaveTextContent("Оценка риска — буква от A до E по сумме баллов из 100");
    const steps = within(plan).getAllByRole("listitem");
    expect(steps).toHaveLength(2);
    expect(steps[0]).toHaveTextContent("Доля крупнейшего покупателя");
    expect(steps[0]).toHaveTextContent("+7 баллов");
    expect(steps[0]).toHaveTextContent(
      "Найдите ещё покупателей, чтобы на крупнейшего приходилось не больше 50% поступлений (сейчас 80%)",
    );
    expect(steps[1]).toHaveTextContent("+6 баллов");
    expect(steps[1]).toHaveTextContent(
      "Верните выручку хотя бы к 90% от прошлого года (сейчас 80%)",
    );
    // The plan comes first; all the advice («Что можно улучшить», scenario 5) stays below it.
    expect(screen.getByText("Что можно улучшить", { exact: true })).toBeInTheDocument();
    for (const text of IMPROVEMENTS) expect(screen.getByText(text)).toBeInTheDocument();
  });

  it("without a plan the general «что улучшить» stays", async () => {
    open(declined(null));
    expect(await screen.findByText("Что можно улучшить")).toBeInTheDocument();
    expect(screen.getByText(IMPROVEMENTS[0] as string)).toBeInTheDocument();
    expect(
      screen.queryByRole("region", { name: "Как получить одобрение" }),
    ).not.toBeInTheDocument();
  });
});

describe("APPROVAL_PLAN texts", () => {
  it.each([
    [1, "+1 балл"],
    [3, "+3 балла"],
    [7, "+7 баллов"],
    [11, "+11 баллов"],
    [12, "+12 баллов"],
    [21, "+21 балл"],
    [22, "+22 балла"],
  ])("%i points → %s", (n, text) => {
    expect(APPROVAL_PLAN.points(n)).toBe(text);
  });

  it("the summary declines the current total and names who decides at grade C or better", () => {
    expect(APPROVAL_PLAN.summary(51, "D", 60, "C")).toContain("Сейчас у заявки 51 балл из 100");
    expect(APPROVAL_PLAN.summary(52, "D", 76, "B")).toContain(
      "Сейчас у заявки 52 балла из 100, оценка риска — D. Если выполнить шаги ниже, наберётся " +
        "76 баллов и оценка станет B. Тогда банк сможет её одобрить.",
    );
  });
});
