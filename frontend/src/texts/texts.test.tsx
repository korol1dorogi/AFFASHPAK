import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ReasonList } from "@/components/ReasonList";
import { METRIC, metricTitle, UNKNOWN_METRIC_TITLE } from "@/texts";

/**
 * Every Reason.metric the backend can return (22.10.2026). Update together with the backend:
 * - apps/scoring/factors.py — scorecard factors;
 * - apps/scoring/stop_factors.py — stop factors С1–С6;
 * - apps/scoring/review.py — ЕГРЮЛ marks that send the application to an officer;
 * - apps/recommendations/service.py — product fit, limits, score_total, dscr_after;
 * - apps/pipeline/decide.py, runner.py — unavailable sources and a failed automatic check.
 */
const BACKEND_METRICS = [
  // scoring factors
  "business_age_months",
  "dscr",
  "debt_to_ebitda",
  "revenue_trend",
  "counterparty_concentration",
  "bki_history",
  "transparent_business",
  // stop factors
  "registry_status",
  "egrul_found",
  "ebitda",
  "bki_current_overdue_days",
  "accounts_suspended",
  // registry marks → manual review (apps/scoring/review.py)
  "egrul_unreliable_address",
  "egrul_unreliable_director",
  "egrul_pending_exclusion",
  // recommendations
  "score_total",
  "product_requirements",
  "term_months",
  "amount_min",
  "amount_max",
  "overdraft_limit",
  "factoring_advance",
  "factoring_commission",
  "working_capital_need",
  "max_loan_by_dscr",
  "dscr_after",
  // pipeline
  "source_egrul",
  "source_transparent_business",
  "source_bki",
  "source_bank_account",
  "automatic_check",
] as const;

describe("metric texts", () => {
  it.each(BACKEND_METRICS)("%s has a plain title and a hint", (metric) => {
    const text = METRIC[metric];
    expect(text?.title).toBeTruthy();
    expect(text?.hint).toBeTruthy();
    expect(text?.title).not.toBe(metric);
  });

  it("has a text for missing_key_metrics before the backend returns it (decision-model.md §7)", () => {
    expect(METRIC.missing_key_metrics?.title).toBeTruthy();
    expect(METRIC.missing_key_metrics?.hint).toContain("Это не отказ");
  });

  it("never shows an unknown metric code to the client", () => {
    expect(metricTitle("brand_new_metric")).toBe(UNKNOWN_METRIC_TITLE);
    render(
      <ReasonList
        reasons={[
          {
            metric: "brand_new_metric",
            value: null,
            threshold: null,
            passed: true,
            message: "Пояснение от банка",
          },
        ]}
      />,
    );
    expect(screen.getByText(UNKNOWN_METRIC_TITLE)).toBeInTheDocument();
    expect(screen.queryByText("brand_new_metric")).toBeNull();
    expect(screen.getByText("Пояснение от банка")).toBeInTheDocument();
  });

  it("shows product_requirements in words on the match screen", () => {
    render(
      <ReasonList
        reasons={[
          {
            metric: "product_requirements",
            value: null,
            threshold: null,
            passed: true,
            message: "Правовая форма и возраст бизнеса подходят",
          },
        ]}
      />,
    );
    expect(screen.getByText("Требования продукта")).toBeInTheDocument();
    expect(screen.queryByText("product_requirements")).toBeNull();
  });
});
