import { screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { BankDashboardPage } from "@/features/bank-dashboard/BankDashboardPage";
import { mockApi, renderRoutes } from "@/test/utils";

const DASHBOARD = "GET /api/bank/dashboard";

function dashboard(extra: Record<string, unknown> = {}) {
  return {
    period_days: 30,
    total_applications: 12,
    funnel: [{ stage: "submitted", count: 12 }],
    avg_hours_in_status: { manual_review: "18.50" },
    auto_decision_share: "0.7500",
    sla_hours: { submitted: 1, processing: 1, manual_review: 24, signed: 1 },
    sla_open_count: 3,
    overdue_count: 2,
    overdue_share: "0.6667",
    ...extra,
  };
}

function render() {
  return renderRoutes(
    [{ path: "/bank/dashboard", element: <BankDashboardPage /> }],
    "/bank/dashboard",
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("BankDashboardPage, SLA (XP4)", () => {
  it("shows the overdue share, the counts, the norms and a link to the filtered queue", async () => {
    mockApi({ [DASHBOARD]: dashboard() });
    render();

    const card = await screen.findByLabelText("Просрочено по нормативу");
    expect(within(card).getByText("66,7 %")).toBeInTheDocument();
    expect(within(card).getByText("2 из 3")).toBeInTheDocument();
    expect(
      within(card).getByText(/Нормативы: Отправлена — 1 ч, .*У сотрудника банка — 24 ч/),
    ).toBeInTheDocument();
    expect(
      within(card).getByRole("link", { name: "Показать просроченные в очереди" }),
    ).toHaveAttribute("href", "/bank?overdue=1");
  });

  it("says plainly when nothing waits for the bank", async () => {
    mockApi({
      [DASHBOARD]: dashboard({ sla_open_count: 0, overdue_count: 0, overdue_share: null }),
    });
    render();

    const card = await screen.findByLabelText("Просрочено по нормативу");
    expect(within(card).getByText("Сейчас нет заявок, которые ждут банк")).toBeInTheDocument();
    expect(within(card).queryByRole("link")).not.toBeInTheDocument();
  });
});

describe("BankDashboardPage — empty period (UX2)", () => {
  it("says there were no applications and offers a longer period", async () => {
    const fetchMock = mockApi({
      [DASHBOARD]: dashboard({ total_applications: 0, funnel: [], overdue_share: null }),
    });
    const router = render();

    expect(await screen.findByText("Заявок за период нет")).toBeInTheDocument();
    screen.getByRole("button", { name: "Показать за 90 дней" }).click();
    await vi.waitFor(() => expect(router.state.location.search).toBe("?days=90"));
    expect(fetchMock).toHaveBeenCalled();
  });
});
