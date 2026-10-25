import { fireEvent, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Schemas } from "@/api/client";
import { BankPolicyPage } from "@/features/bank-policy/BankPolicyPage";
import { mockApi, renderWithQuery } from "@/test/utils";
import { BANK_POLICY } from "@/texts";

const dist = (counts: number[]) =>
  (["A", "B", "C", "D", "E", "stop"] as const).map((grade, i) => ({
    grade,
    count: counts[i] ?? 0,
  }));

const OVERVIEW: Schemas["PolicyOverview"] = {
  model_version: "scorecard-2026.10-v1",
  policy_version: "2026.10-v1",
  grades: [
    { grade: "A", min_total: 90 },
    { grade: "B", min_total: 75 },
    { grade: "C", min_total: 60 },
    { grade: "D", min_total: 50 },
  ],
  lowest_grade: "E",
  factors: [
    {
      name: "dscr",
      max_points: 25,
      higher_is_better: true,
      steps: [
        { threshold: "2.0", points: 25 },
        { threshold: "1.25", points: 10 },
      ],
      floor_points: 0,
      passed_threshold: "1.25",
      unknown_points: 12,
    },
    {
      name: "bki_history",
      max_points: 20,
      higher_is_better: null,
      steps: [],
      floor_points: 0,
      passed_threshold: null,
      unknown_points: 10,
    },
  ],
  stop_factors: {
    current_overdue_days: 30,
    min_business_age_months: 6,
    max_missing_key_metrics: 1,
  },
  population: {
    companies: 240,
    distribution: dist([40, 71, 50, 41, 26, 12]),
    zones: { auto: 111, manual: 91, decline: 38 },
  },
};

const SAME: Schemas["PolicyWhatIf"] = {
  companies: 240,
  changed: 0,
  before: dist([40, 71, 50, 41, 26, 12]),
  after: dist([40, 71, 50, 41, 26, 12]),
  zones_before: { auto: 111, manual: 91, decline: 38 },
  zones_after: { auto: 111, manual: 91, decline: 38 },
  transitions: [],
};

describe("BankPolicyPage (XP7)", () => {
  it("shows the versions, the grade boundaries and the factor scales", async () => {
    mockApi({ "GET /api/bank/policy": OVERVIEW, "POST /api/bank/policy/what-if": SAME });
    renderWithQuery(<BankPolicyPage />);
    expect(await screen.findByText(/2026\.10-v1/)).toBeInTheDocument();
    const dscr = document.querySelector("[data-factor='dscr']") as HTMLElement;
    expect(dscr).toHaveTextContent("от 2 — 25 б.");
    expect(dscr).toHaveTextContent("ниже — 0 б.");
    expect(screen.getByText(BANK_POLICY.stopAge(6))).toBeInTheDocument();
    expect(await screen.findByText(BANK_POLICY.nothingChanged)).toBeInTheDocument();
  });

  it("recounts the population on other boundaries", async () => {
    let calls = 0;
    const fetchMock = mockApi({
      "GET /api/bank/policy": OVERVIEW,
      "POST /api/bank/policy/what-if": () => {
        calls += 1;
        return calls === 1
          ? SAME
          : {
              ...SAME,
              changed: 17,
              after: dist([40, 71, 67, 24, 26, 12]),
              transitions: [{ from_grade: "D", to_grade: "C", count: 17 }],
            };
      },
    });
    renderWithQuery(<BankPolicyPage />);
    expect(await screen.findByText(BANK_POLICY.nothingChanged)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/Грейд C/), { target: { value: "55" } });
    fireEvent.click(screen.getByRole("button", { name: BANK_POLICY.recount }));
    expect(await screen.findByText(BANK_POLICY.changed(17, 240))).toBeInTheDocument();
    expect(screen.getByText(BANK_POLICY.move("D", "C", 17))).toBeInTheDocument();
    const posts = fetchMock.mock.calls
      .map(([request]) => request as Request)
      .filter((request) => request.method === "POST");
    expect(await posts.at(-1)?.json()).toEqual({ grades: { A: 90, B: 75, C: 55, D: 50 } });
  });

  it("shows why the boundaries were refused", async () => {
    mockApi({
      "GET /api/bank/policy": OVERVIEW,
      "POST /api/bank/policy/what-if": [
        400,
        {
          error: {
            code: "invalid",
            message: "Пороги идут по убыванию: A выше B, B выше C, C выше D.",
          },
        },
      ],
    });
    renderWithQuery(<BankPolicyPage />);
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(/по убыванию/)).toBeInTheDocument();
  });
});
