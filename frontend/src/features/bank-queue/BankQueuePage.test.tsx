import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { BankQueuePage } from "@/features/bank-queue/BankQueuePage";
import { SEARCH_DELAY_MS } from "@/features/bank-queue/QueueFilters";
import { mockApi, renderRoutes } from "@/test/utils";

const QUEUE = "GET /api/bank/applications";

function item(id: number, overrides: Record<string, unknown> = {}) {
  return {
    id,
    company_name: `ООО Демо ${id}`,
    company_inn: "7701234567",
    product_kind: "working_capital_loan",
    requested_amount: "2009314.00",
    status: "manual_review",
    grade: "C",
    assignee: null,
    source_unavailable: false,
    status_changed_at: "2026-10-21T10:00:00Z",
    hours_in_status: 3,
    sla_due_at: "2026-10-22T10:00:00Z",
    is_overdue: false,
    overdue_hours: 0,
    version: 1,
    ...overrides,
  };
}

function page(results: unknown[], extra: Record<string, unknown> = {}) {
  return {
    count: results.length,
    page: 1,
    page_size: 20,
    results,
    counters: { submitted: 1, manual_review: 12, info_requested: 3, offer: 7, declined: 0 },
    ...extra,
  };
}

function render(path = "/bank") {
  return renderRoutes(
    [
      { path: "/bank", element: <BankQueuePage /> },
      { path: "/bank/applications/:id", element: <p>Карточка заявки</p> },
    ],
    path,
  );
}

/** Query strings the queue was asked with, in order. */
function queueCalls(fetchMock: ReturnType<typeof mockApi>) {
  return fetchMock.mock.calls
    .map(([request]) => new URL((request as Request).url))
    .filter((url) => url.pathname === "/api/bank/applications")
    .map((url) => url.searchParams);
}

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("BankQueuePage", () => {
  it("renders rows and counters from the response", async () => {
    mockApi({
      [QUEUE]: page([
        item(41, {
          assignee: { id: 5, full_name: "Ирина Банкова" },
          hours_in_status: 30,
          source_unavailable: true,
          status: "info_requested",
          grade: null,
          // waits for the client: no SLA, however long it has been (XP4)
          sla_due_at: null,
        }),
        item(42, { hours_in_status: 26, is_overdue: true, overdue_hours: 2 }),
      ]),
    });
    render();

    const table = await screen.findByRole("table", { name: "Заявки в очереди" });
    const rows = within(table).getAllByRole("row");
    expect(rows).toHaveLength(3); // header + 2

    const first = rows[1] as HTMLElement;
    expect(within(first).getByRole("link", { name: "Заявка №41" })).toHaveAttribute(
      "href",
      "/bank/applications/41",
    );
    expect(within(first).getByText("ООО Демо 41")).toBeInTheDocument();
    expect(within(first).getByText("ИНН 7701234567")).toBeInTheDocument();
    expect(within(first).getByText("Кредит на пополнение оборотных средств")).toBeInTheDocument();
    expect(within(first).getByText("2 009 314 ₽")).toBeInTheDocument();
    expect(within(first).getByText("Нужны уточнения")).toBeInTheDocument();
    expect(within(first).getByText("Ирина Банкова")).toBeInTheDocument();
    expect(within(first).getByText("30 ч")).toBeInTheDocument();
    expect(within(first).queryByText(/просрочено/)).not.toBeInTheDocument();
    expect(first).not.toHaveAttribute("data-overdue");
    expect(within(first).getByRole("img", { name: "Источник недоступен" })).toBeInTheDocument();

    const second = rows[2] as HTMLElement;
    expect(within(second).getByText("C")).toBeInTheDocument();
    expect(within(second).getByText("Не назначен")).toBeInTheDocument();
    expect(within(second).getByText("26 ч")).toBeInTheDocument();
    expect(within(second).getByText("просрочено на 2 ч")).toBeInTheDocument();
    expect(second).toHaveAttribute("data-overdue", "true");
    expect(within(second).queryByRole("img", { name: "Источник недоступен" })).toBeNull();

    const chips = screen.getByRole("group", { name: "Фильтр по статусу" });
    expect(within(chips).getByRole("button", { name: "Все: 23" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(within(chips).getByRole("button", { name: "У сотрудника банка: 12" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });

  it("a click on a row opens the bank card", async () => {
    mockApi({ [QUEUE]: page([item(41)]) });
    const router = render();
    fireEvent.click(await screen.findByText("ООО Демо 41"));
    await waitFor(() => expect(router.state.location.pathname).toBe("/bank/applications/41"));
  });

  it("a click on a counter filters by its status and keeps the URL", async () => {
    const fetchMock = mockApi({ [QUEUE]: page([item(41)]) });
    const router = render("/bank?status=offer&grade=B&page=3");
    await screen.findByRole("table");
    expect(queueCalls(fetchMock)[0]?.getAll("status")).toEqual(["offer"]);
    expect(queueCalls(fetchMock)[0]?.get("grade")).toBe("B");
    expect(queueCalls(fetchMock)[0]?.get("page")).toBe("3");

    fireEvent.click(screen.getByRole("button", { name: "У сотрудника банка: 12" }));
    await waitFor(() =>
      expect(router.state.location.search).toBe("?status=offer&status=manual_review&grade=B"),
    );
    await waitFor(() =>
      expect(queueCalls(fetchMock).at(-1)?.getAll("status")).toEqual(["offer", "manual_review"]),
    );

    fireEvent.click(screen.getByRole("button", { name: "Все: 23" }));
    await waitFor(() => expect(router.state.location.search).toBe("?grade=B"));
  });

  it("selects write to the URL; «back» brings the previous filter", async () => {
    mockApi({ [QUEUE]: page([item(41)]) });
    const router = render();
    await screen.findByRole("table");

    fireEvent.change(screen.getByLabelText("Исполнитель"), { target: { value: "me" } });
    await waitFor(() => expect(router.state.location.search).toBe("?assignee=me"));
    fireEvent.change(screen.getByLabelText("В статусе"), { target: { value: "24" } });
    await waitFor(() =>
      expect(router.state.location.search).toBe("?assignee=me&min_hours_in_status=24"),
    );

    await router.navigate(-1);
    await waitFor(() => expect(router.state.location.search).toBe("?assignee=me"));
    await waitFor(() => expect(screen.getByLabelText("В статусе")).toHaveValue(""));
  });

  it("«Только просроченные» writes overdue=1 to the URL and asks the server (XP4)", async () => {
    const fetchMock = mockApi({
      [QUEUE]: page([item(42, { is_overdue: true, overdue_hours: 0 })]),
    });
    const router = render();
    await screen.findByRole("table");

    const toggle = screen.getByRole("checkbox", { name: "Только просроченные" });
    fireEvent.click(toggle);
    await waitFor(() => expect(router.state.location.search).toBe("?overdue=1"));
    await waitFor(() => expect(queueCalls(fetchMock).at(-1)?.get("overdue")).toBe("true"));
    expect(screen.getByText("просрочено, меньше часа")).toBeInTheDocument();

    fireEvent.click(toggle);
    await waitFor(() => expect(router.state.location.search).toBe(""));
    expect(queueCalls(fetchMock).at(-1)?.has("overdue")).toBe(false);
  });

  it("opens with the overdue filter from a link", async () => {
    const fetchMock = mockApi({ [QUEUE]: page([item(42)]) });
    render("/bank?overdue=1");
    await screen.findByRole("table");

    expect(screen.getByRole("checkbox", { name: "Только просроченные" })).toBeChecked();
    expect(queueCalls(fetchMock)[0]?.get("overdue")).toBe("true");
    expect(screen.getByRole("button", { name: "Сбросить фильтры" })).toBeInTheDocument();
  });

  it("shows a non-preset hours value from the URL", async () => {
    mockApi({ [QUEUE]: page([item(41)]) });
    render("/bank?min_hours_in_status=10");
    await screen.findByRole("table");
    const select = screen.getByLabelText("В статусе");
    expect(select).toHaveValue("10");
    expect(within(select).getByRole("option", { name: "Больше 10 ч" })).toBeInTheDocument();
  });

  it("searches once typing pauses", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const fetchMock = mockApi({ [QUEUE]: page([item(41)]) });
    const router = render();
    await screen.findByRole("table");

    const search = screen.getByLabelText("Поиск");
    fireEvent.change(search, { target: { value: "77" } });
    fireEvent.change(search, { target: { value: "7701" } });
    expect(router.state.location.search).toBe("");

    await vi.advanceTimersByTimeAsync(SEARCH_DELAY_MS + 50);
    await waitFor(() => expect(router.state.location.search).toBe("?search=7701"));
    await waitFor(() => expect(queueCalls(fetchMock).at(-1)?.get("search")).toBe("7701"));
    expect(queueCalls(fetchMock).filter((params) => params.get("search") === "77")).toHaveLength(0);
  });

  it("pages through 250 applications 20 at a time", async () => {
    const fetchMock = mockApi({
      [QUEUE]: (request: Request) => {
        const current = Number(new URL(request.url).searchParams.get("page"));
        return page([item(current * 100)], { count: 250, page: current });
      },
    });
    const router = render();
    expect(await screen.findByText("Страница 1 из 13")).toBeInTheDocument();
    expect(screen.getByText(/всего 250/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Назад" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Вперёд" }));
    await waitFor(() => expect(router.state.location.search).toBe("?page=2"));
    expect(await screen.findByText("ООО Демо 200")).toBeInTheDocument();
    expect(queueCalls(fetchMock).at(-1)?.get("page_size")).toBe("20");
  });

  it("empty result: says so and resets the filters", async () => {
    mockApi({ [QUEUE]: page([]) });
    const router = render("/bank?grade=E&search=нет");
    expect(await screen.findByText("Заявок с такими фильтрами нет")).toBeInTheDocument();

    const reset = screen.getAllByRole("button", { name: "Сбросить фильтры" });
    fireEvent.click(reset.at(-1) as HTMLElement);
    await waitFor(() => expect(router.state.location.search).toBe(""));
    await waitFor(() => expect(screen.getByLabelText("Поиск")).toHaveValue(""));
  });

  it("an empty queue without filters has no reset", async () => {
    mockApi({ [QUEUE]: page([]) });
    render();
    expect(await screen.findByText("В очереди пока нет заявок")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Сбросить фильтры" })).toBeNull();
  });

  it("error: shows the message and retries", async () => {
    let fail = true;
    const fetchMock = mockApi({
      [QUEUE]: () =>
        fail
          ? [500, { error: { code: "server_error", message: "Сервер прилёг отдохнуть." } }]
          : page([item(41)]),
    });
    render();
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText("Не получилось загрузить очередь")).toBeInTheDocument();
    expect(within(alert).getByText("Сервер прилёг отдохнуть.")).toBeInTheDocument();

    fail = false;
    fireEvent.click(within(alert).getByRole("button", { name: "Повторить" }));
    expect(await screen.findByText("ООО Демо 41")).toBeInTheDocument();
    expect(queueCalls(fetchMock)).toHaveLength(2);
  });
});
