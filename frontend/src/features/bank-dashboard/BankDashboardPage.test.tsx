import { screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { BankDashboardPage } from "@/features/bank-dashboard/BankDashboardPage";
import { mockApi, renderRoutes } from "@/test/utils";
import { BANK_DASHBOARD } from "@/texts";

const DASHBOARD = "GET /api/bank/dashboard";

function dashboard(extra: Record<string, unknown> = {}) {
  return {
    period_days: 30,
    total_applications: 12,
    by_status: [
      { status: "submitted", count: 0 },
      { status: "processing", count: 1 },
      { status: "manual_review", count: 3 },
      { status: "info_requested", count: 1 },
      { status: "offer", count: 2 },
      { status: "signing", count: 0 },
      { status: "signed", count: 0 },
      { status: "issued", count: 3 },
      { status: "declined", count: 2 },
      { status: "cancelled", count: 0 },
    ],
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

describe("BankDashboardPage — where the applications are now", () => {
  it("puts each application in one row: the groups add up to the period total", async () => {
    mockApi({ [DASHBOARD]: dashboard() });
    render();

    expect(await screen.findByRole("heading", { name: "Сводка", level: 1 })).toBeInTheDocument();
    const card = screen.getByLabelText("Где сейчас заявки");
    const group = (name: string) => within(card).getByRole("region", { name });
    const row = (key: string) => card.querySelector(`li[data-row="${key}"]`) as HTMLElement;

    expect(within(group("Ход за банком")).getByRole("heading")).toHaveTextContent("4");
    expect(within(group("Ход за клиентом")).getByRole("heading")).toHaveTextContent("3");
    expect(within(group("Выдача")).getByRole("heading")).toHaveTextContent("0");
    expect(within(group("Завершены")).getByRole("heading")).toHaveTextContent("5");
    // submitted and processing are one row: the system is checking them
    expect(row("checking")).toHaveTextContent("Проверяет система1 · 8 %");
    expect(row("manual_review")).toHaveTextContent("У сотрудника банка3 · 25 %");
    expect(row("offer")).toHaveTextContent("Ждём решения по предложению2 · 17 %");
    expect(row("cancelled")).toHaveTextContent("Клиент отозвал заявку0 · 0 %");
    expect(BANK_DASHBOARD.nowValue(1, 0)).toBe("1 · меньше 1 %");
    expect(screen.queryByText(/Воронка/)).not.toBeInTheDocument();
  });

  it("takes «Деньги выданы» from where the applications are now", async () => {
    mockApi({ [DASHBOARD]: dashboard() });
    render();

    const card = (await screen.findByText("Деньги выданы", { selector: "p" })).parentElement;
    expect(card).toHaveTextContent("Деньги выданы3");
  });
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
