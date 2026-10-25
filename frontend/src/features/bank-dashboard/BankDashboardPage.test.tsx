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

describe("BankDashboardPage — in work now and the period's results", () => {
  it("splits the period into work by who has to act and results; together the total", async () => {
    mockApi({ [DASHBOARD]: dashboard() });
    render();

    expect(await screen.findByRole("heading", { name: "Сводка", level: 1 })).toBeInTheDocument();
    const work = screen.getByLabelText("В работе сейчас");
    const results = screen.getByLabelText("Итоги за период");
    const row = (card: HTMLElement, key: string) =>
      card.querySelector(`li[data-row="${key}"]`) as HTMLElement;

    // 7 in work + 5 finished = 12, the period's total
    expect(within(work).getByText("7")).toBeInTheDocument();
    expect(within(results).getByText("5")).toBeInTheDocument();
    const group = (name: string) => within(work).getByRole("region", { name });
    expect(within(group("Ждут банк")).getByRole("heading")).toHaveTextContent("Ждут банк4");
    expect(within(group("Ждут клиента")).getByRole("heading")).toHaveTextContent("Ждут клиента3");
    expect(within(group("Выдача денег")).getByRole("heading")).toHaveTextContent("Выдача денег0");
    // submitted and processing are one row: the system is checking them
    expect(row(work, "checking")).toHaveTextContent("Проверяет система1");
    expect(row(work, "manual_review")).toHaveTextContent("Смотрит сотрудник банка3");
    expect(row(work, "offer")).toHaveTextContent("Решают, принять ли предложение2");
    // results: the share of the finished applications, not of the whole period
    expect(row(results, "issued")).toHaveTextContent("Деньги выданы360 %");
    expect(row(results, "declined")).toHaveTextContent("Отказ240 %");
    expect(row(results, "cancelled")).toHaveTextContent("Клиент отозвал заявку00 %");
    expect(row(results, "cancelled")).toHaveClass("text-ink-muted");
    expect(screen.queryByText(/Воронка/)).not.toBeInTheDocument();
  });

  it("a share below 1 % is «меньше 1 %», not 0", () => {
    expect(BANK_DASHBOARD.share(1, 0)).toBe("меньше 1 %");
    expect(BANK_DASHBOARD.share(0, 0)).toBe("0 %");
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
