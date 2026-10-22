import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Schemas } from "@/api/client";
import type { BankApplicationDetail } from "@/features/bank-application/api";
import { BankApplicationPage } from "@/features/bank-application/BankApplicationPage";
import { persona4Card } from "@/features/bank-application/fixtures";
import { mockApi, renderRoutes } from "@/test/utils";

const BASE = "/api/bank/applications/42";
const PRODUCTS = [
  {
    code: "investment_loan_basic",
    name: "Инвестиционный кредит (демо)",
    rate_min: "0.18",
    rate_max: "0.26",
  },
  { code: "leasing_basic", name: "Лизинг (демо)", rate_min: "0.15", rate_max: "0.22" },
];

/** Persona 4 card with other status, version, actions or assignee. */
function cardWith(
  changes: Partial<Schemas["Application"]>,
  assignee: BankApplicationDetail["assignee"] = persona4Card().assignee,
): BankApplicationDetail {
  const card = persona4Card();
  return { ...card, application: { ...card.application, ...changes }, assignee };
}

/** The card after a finished action: the status moved on, nothing is left for the employee. */
const done = (status: Schemas["ApplicationStatus"]) =>
  cardWith({ status, version: 4, available_actions: [] });

function open(handlers: Record<string, unknown> = {}, card: unknown = persona4Card()) {
  const fetchMock = mockApi({ [`GET ${BASE}`]: card, "GET /api/products": PRODUCTS, ...handlers });
  renderRoutes(
    [{ path: "/bank/applications/:id", element: <BankApplicationPage /> }],
    "/bank/applications/42",
  );
  return fetchMock;
}

/** JSON bodies sent to POST {BASE}/{action}, in order. */
function sent(fetchMock: ReturnType<typeof mockApi>, action: string) {
  const requests = fetchMock.mock.calls
    .map(([request]) => request as Request)
    .filter(
      (request) =>
        request.method === "POST" && new URL(request.url).pathname === `${BASE}/${action}`,
    );
  return Promise.all(requests.map((request) => request.clone().json()));
}

async function openDialog(name: string) {
  fireEvent.click(await screen.findByRole("button", { name }));
  return screen.findByRole("dialog");
}

const type = (field: HTMLElement, value: string) => fireEvent.change(field, { target: { value } });

const dialogClosed = () =>
  waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("ActionPanel — buttons only from available_actions", () => {
  it("shows every employee action of manual review; counteroffer gives two buttons", async () => {
    open();
    const panel = await screen.findByRole("complementary", { name: "Действия сотрудника" });
    expect(
      within(panel)
        .getAllByRole("button")
        .map((button) => button.textContent),
    ).toEqual([
      "Взять в работу",
      "Одобрить",
      "Иные условия",
      "Другой продукт",
      "Запросить информацию",
      "Отказать",
    ]);
  });

  it("draws nothing that is not in available_actions", async () => {
    open({}, cardWith({ available_actions: ["request_info"] }));
    const panel = await screen.findByRole("complementary", { name: "Действия сотрудника" });
    expect(
      within(panel)
        .getAllByRole("button")
        .map((button) => button.textContent),
    ).toEqual(["Запросить информацию"]);
  });

  it("says so when there is nothing to do", async () => {
    open({}, cardWith({ status: "offer", available_actions: [] }));
    const panel = await screen.findByRole("complementary", { name: "Действия сотрудника" });
    expect(within(panel).queryByRole("button")).not.toBeInTheDocument();
    expect(
      within(panel).getByText("Сейчас по заявке нет действий для сотрудника."),
    ).toBeInTheDocument();
  });

  it("assign sends the version and the button goes once the card has no assign", async () => {
    const fetchMock = open({
      [`POST ${BASE}/assign`]: cardWith({
        version: 4,
        available_actions: ["approve", "counteroffer", "request_info", "decline"],
      }),
    });
    fireEvent.click(await screen.findByRole("button", { name: "Взять в работу" }));
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: "Взять в работу" })).not.toBeInTheDocument(),
    );
    expect(await sent(fetchMock, "assign")).toEqual([{ version: 3 }]);
  });
});

describe("ActionPanel — dialogs send what the contract asks", () => {
  it("approve: requested terms in the text, optional comment, trimmed", async () => {
    const fetchMock = open({ [`POST ${BASE}/approve`]: done("offer") });
    const dialog = await openDialog("Одобрить");
    expect(within(dialog).getByText(/8\s000\s000\s₽ на 36 мес/)).toBeInTheDocument();
    type(within(dialog).getByLabelText("Комментарий клиенту"), "  Одобряем на ваших условиях  ");
    fireEvent.click(within(dialog).getByRole("button", { name: "Одобрить" }));
    await dialogClosed();
    expect(await sent(fetchMock, "approve")).toEqual([
      { version: 3, comment: "Одобряем на ваших условиях" },
    ]);
    expect(
      await screen.findByText("Сейчас по заявке нет действий для сотрудника."),
    ).toBeInTheDocument();
  });

  it("approve without a comment sends only the version", async () => {
    const fetchMock = open({ [`POST ${BASE}/approve`]: done("offer") });
    const dialog = await openDialog("Одобрить");
    fireEvent.click(within(dialog).getByRole("button", { name: "Одобрить" }));
    await dialogClosed();
    expect(await sent(fetchMock, "approve")).toEqual([{ version: 3 }]);
  });

  it("counteroffer: hints, required rate and comment, percent leaves as a fraction", async () => {
    const fetchMock = open({ [`POST ${BASE}/counteroffer`]: done("offer") });
    const dialog = await openDialog("Иные условия");
    expect(within(dialog).getByText(/допустимо до 11\s290\s503\s₽/)).toBeInTheDocument();
    expect(await within(dialog).findByText(/от 18\s%\sдо 26\s%/)).toBeInTheDocument();
    expect(within(dialog).queryByLabelText("Продукт")).not.toBeInTheDocument();

    const confirm = within(dialog).getByRole("button", { name: "Предложить условия" });
    fireEvent.click(confirm);
    expect(
      await within(dialog).findByText("Укажите ставку больше нуля, например 21,5"),
    ).toBeInTheDocument();
    expect(within(dialog).getByText("Напишите комментарий для клиента")).toBeInTheDocument();

    type(within(dialog).getByLabelText("Сумма"), "6500000");
    type(within(dialog).getByLabelText("Срок, месяцев"), "24");
    type(within(dialog).getByLabelText("Ставка, % годовых"), "21,5");
    type(within(dialog).getByLabelText("Комментарий клиенту"), "Сумма, которую выдержит поток");
    fireEvent.click(confirm);
    await dialogClosed();
    expect(await sent(fetchMock, "counteroffer")).toEqual([
      {
        version: 3,
        amount: "6500000.00",
        term_months: 24,
        rate: "0.215",
        comment: "Сумма, которую выдержит поток",
      },
    ]);
  });

  it("counteroffer refuses a zero amount", async () => {
    const fetchMock = open();
    const dialog = await openDialog("Иные условия");
    type(within(dialog).getByLabelText("Сумма"), "0");
    fireEvent.click(within(dialog).getByRole("button", { name: "Предложить условия" }));
    expect(await within(dialog).findByText("Укажите сумму больше нуля")).toBeInTheDocument();
    expect(await sent(fetchMock, "counteroffer")).toEqual([]);
  });

  it("another product: the current one is not offered, product_code is required and sent", async () => {
    const fetchMock = open({ [`POST ${BASE}/counteroffer`]: done("offer") });
    const dialog = await openDialog("Другой продукт");
    const select = within(dialog).getByLabelText("Продукт");
    expect(
      await within(select).findByRole("option", { name: "Лизинг (демо)" }),
    ).toBeInTheDocument();
    expect(
      within(select).queryByRole("option", { name: "Инвестиционный кредит (демо)" }),
    ).not.toBeInTheDocument();

    const confirm = within(dialog).getByRole("button", { name: "Предложить продукт" });
    fireEvent.click(confirm);
    expect(await within(dialog).findByText("Выберите продукт")).toBeInTheDocument();

    type(select, "leasing_basic");
    type(within(dialog).getByLabelText("Ставка, % годовых"), "17");
    // The rate hint follows the chosen product (it shows once the field has no error).
    expect(await within(dialog).findByText(/от 15\s%\sдо 22\s%/)).toBeInTheDocument();
    type(within(dialog).getByLabelText("Комментарий клиенту"), "Лизинг без отдельного залога");
    fireEvent.click(confirm);
    await dialogClosed();
    expect(await sent(fetchMock, "counteroffer")).toEqual([
      {
        version: 3,
        product_code: "leasing_basic",
        amount: "8000000.00",
        term_months: 36,
        rate: "0.17",
        comment: "Лизинг без отдельного залога",
      },
    ]);
  });

  it("request info: the text is required", async () => {
    const fetchMock = open({ [`POST ${BASE}/request-info`]: done("info_requested") });
    const dialog = await openDialog("Запросить информацию");
    const confirm = within(dialog).getByRole("button", { name: "Отправить запрос" });
    fireEvent.click(confirm);
    expect(await within(dialog).findByText("Напишите, что нужно от клиента")).toBeInTheDocument();
    type(
      within(dialog).getByLabelText("Что нужно от клиента"),
      "Загрузите бухгалтерскую отчётность за 2025 год",
    );
    fireEvent.click(within(dialog).getByLabelText("Бухгалтерская отчётность"));
    fireEvent.click(confirm);
    await dialogClosed();
    expect(await sent(fetchMock, "request-info")).toEqual([
      {
        version: 3,
        message: "Загрузите бухгалтерскую отчётность за 2025 год",
        document_kinds: ["financial_report"],
      },
    ]);
  });

  it("decline: reasons and at least one filled «что улучшить»; empty rows are refused", async () => {
    const fetchMock = open({ [`POST ${BASE}/decline`]: done("declined") });
    const dialog = await openDialog("Отказать");
    expect(
      within(dialog).queryByRole("button", { name: "Убрать пункт 1" }),
    ).not.toBeInTheDocument();
    type(
      within(dialog).getByLabelText("Почему отказ — простым языком"),
      "Платежи по кредиту не покрываются денежным потоком",
    );
    type(within(dialog).getByLabelText("Что улучшить, пункт 1"), "Снизьте долговую нагрузку");
    fireEvent.click(within(dialog).getByRole("button", { name: "Добавить пункт" }));

    const confirm = within(dialog).getByRole("button", { name: "Отказать" });
    fireEvent.click(confirm);
    expect(await within(dialog).findByText("Заполните пункт или уберите его")).toBeInTheDocument();

    fireEvent.click(within(dialog).getByRole("button", { name: "Убрать пункт 2" }));
    fireEvent.click(confirm);
    await dialogClosed();
    expect(await sent(fetchMock, "decline")).toEqual([
      {
        version: 3,
        reasons_text: "Платежи по кредиту не покрываются денежным потоком",
        improvements: ["Снизьте долговую нагрузку"],
      },
    ]);
  });
});

describe("ActionPanel — errors", () => {
  it("409 version_conflict: keeps what was typed, re-reads the card, retries with the new version", async () => {
    let fresh = false;
    let attempts = 0;
    const fetchMock = open({
      // After the conflict the card comes back changed by a colleague.
      [`GET ${BASE}`]: () =>
        fresh ? cardWith({ version: 4 }, { id: 21, full_name: "Иван Банк" }) : persona4Card(),
      [`POST ${BASE}/approve`]: () => {
        attempts += 1;
        if (attempts > 1) return done("offer");
        fresh = true;
        return [
          409,
          {
            error: { code: "version_conflict", message: "Заявку уже изменили. Обновите страницу." },
          },
        ];
      },
    });
    const dialog = await openDialog("Одобрить");
    const comment = within(dialog).getByLabelText("Комментарий клиенту");
    type(comment, "Одобряем");
    fireEvent.click(within(dialog).getByRole("button", { name: "Одобрить" }));

    const alert = await within(dialog).findByRole("alert");
    expect(alert).toHaveTextContent("Заявку уже изменили. Обновите страницу.");
    expect(alert).toHaveTextContent("Карточку обновили — проверьте данные и повторите.");
    expect(await screen.findByText("Иван Банк")).toBeInTheDocument();
    expect(comment).toHaveValue("Одобряем");

    fireEvent.click(within(dialog).getByRole("button", { name: "Одобрить" }));
    await dialogClosed();
    expect(await sent(fetchMock, "approve")).toEqual([
      { version: 3, comment: "Одобряем" },
      { version: 4, comment: "Одобряем" },
    ]);
  });

  it("409 invalid_transition: the action is gone after re-reading — confirm is disabled", async () => {
    let fresh = false;
    open({
      [`GET ${BASE}`]: () =>
        fresh
          ? cardWith({ status: "cancelled", version: 4, available_actions: [] })
          : persona4Card(),
      [`POST ${BASE}/decline`]: () => {
        fresh = true;
        return [
          409,
          {
            error: {
              code: "invalid_transition",
              message: "Действие недоступно в текущем статусе заявки.",
            },
          },
        ];
      },
    });
    const dialog = await openDialog("Отказать");
    const reasons = within(dialog).getByLabelText("Почему отказ — простым языком");
    type(reasons, "Высокая долговая нагрузка");
    type(within(dialog).getByLabelText("Что улучшить, пункт 1"), "Погасите часть долга");
    fireEvent.click(within(dialog).getByRole("button", { name: "Отказать" }));

    expect(
      await within(dialog).findByText(
        "Это действие больше недоступно: статус заявки изменился. Закройте окно.",
      ),
    ).toBeInTheDocument();
    expect(within(dialog).getByRole("alert")).toHaveTextContent(
      "Действие недоступно в текущем статусе заявки.",
    );
    expect(within(dialog).getByRole("alert")).not.toHaveTextContent("Карточку обновили");
    expect(within(dialog).getByRole("button", { name: "Отказать" })).toBeDisabled();
    expect(reasons).toHaveValue("Высокая долговая нагрузка");
  });

  it("400 with details: the API's message lands under the field, the dialog stays", async () => {
    open({
      [`POST ${BASE}/counteroffer`]: [
        400,
        {
          error: {
            code: "validation_error",
            message: "Проверьте поля",
            details: { amount: ["Больше максимальной суммы продукта"] },
          },
        },
      ],
    });
    const dialog = await openDialog("Иные условия");
    type(within(dialog).getByLabelText("Ставка, % годовых"), "20");
    type(within(dialog).getByLabelText("Комментарий клиенту"), "Меньше, чем просили");
    fireEvent.click(within(dialog).getByRole("button", { name: "Предложить условия" }));
    expect(
      await within(dialog).findByText("Больше максимальной суммы продукта"),
    ).toBeInTheDocument();
    expect(within(dialog).getByLabelText("Сумма")).toHaveAttribute("aria-invalid", "true");
    expect(within(dialog).queryByRole("alert")).not.toBeInTheDocument();
  });
});
