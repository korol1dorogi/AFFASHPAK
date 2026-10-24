import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, onTestFinished, vi } from "vitest";

import { BankApplicationPage } from "@/features/bank-application/BankApplicationPage";
import { persona4Card } from "@/features/bank-application/fixtures";
import { mockApi, renderRoutes } from "@/test/utils";

const CARD = "GET /api/bank/applications/42";
const PRODUCTS = {
  "GET /api/products": [{ code: "investment_loan_basic", name: "Инвестиционный кредит (демо)" }],
};

function open(tab?: string, card: unknown = persona4Card(), extra: Record<string, unknown> = {}) {
  const fetchMock = mockApi({ [CARD]: card, ...PRODUCTS, ...extra });
  const router = renderRoutes(
    [
      { path: "/bank/applications/:id", element: <BankApplicationPage /> },
      { path: "/bank", element: <p>Очередь</p> },
    ],
    `/bank/applications/42${tab ? `?tab=${tab}` : ""}`,
  );
  return { fetchMock, router };
}

/** Index access under noUncheckedIndexedAccess: fail loudly instead of `!`. */
function present<T>(value: T | undefined): T {
  if (value === undefined) throw new Error("fixture item is missing");
  return value;
}

function cardCalls(fetchMock: ReturnType<typeof mockApi>) {
  return fetchMock.mock.calls.filter(
    ([request]) =>
      (request as Request).method === "GET" &&
      new URL((request as Request).url).pathname === "/api/bank/applications/42",
  ).length;
}

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("BankApplicationPage — header and states", () => {
  it("shows company, amount, product, status, grade and assignee", async () => {
    open();
    expect(
      await screen.findByRole("heading", { name: "ООО «Дубрава Мебель» (демо)" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Заявка № 42 · ИНН 0001000042/)).toBeInTheDocument();
    expect(screen.getByText("У сотрудника банка")).toBeInTheDocument();
    const header = screen.getByText("Исполнитель").closest("dl") as HTMLElement;
    expect(within(header).getByText("8 000 000 ₽")).toBeInTheDocument();
    expect(within(header).getByText("8 000 000 ₽").parentElement).toHaveTextContent(
      "8 000 000 ₽со слов клиента",
    );
    expect(await within(header).findByText("Инвестиционный кредит (демо)")).toBeInTheDocument();
    expect(within(header).getByText("C")).toBeInTheDocument();
    expect(within(header).getByText("Анна Банк")).toBeInTheDocument();
    expect(screen.queryByText(/источников не ответил/)).not.toBeInTheDocument();
  });

  it("404 → «Заявка не найдена» with a way back to the queue", async () => {
    mockApi(PRODUCTS);
    renderRoutes(
      [{ path: "/bank/applications/:id", element: <BankApplicationPage /> }],
      "/bank/applications/999",
    );
    expect(await screen.findByText("Заявка не найдена")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "К очереди" })).toHaveAttribute("href", "/bank");
  });
});

describe("BankApplicationPage — bad id", () => {
  it("a non-numeric id is «Заявка не найдена» without a request", async () => {
    const fetchMock = mockApi(PRODUCTS);
    renderRoutes(
      [{ path: "/bank/applications/:id", element: <BankApplicationPage /> }],
      "/bank/applications/abc",
    );
    expect(await screen.findByText("Заявка не найдена")).toBeInTheDocument();
    const bankCalls = fetchMock.mock.calls.filter(([request]) =>
      new URL((request as Request).url).pathname.startsWith("/api/bank/"),
    );
    expect(bankCalls).toHaveLength(0);
  });
});

describe("BankApplicationPage — tabs in the URL", () => {
  it("opens the tab from ?tab= and writes the clicked tab back", async () => {
    const { router } = open("scoring");
    expect(await screen.findByRole("tab", { name: "Скоринг" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    fireEvent.mouseDown(screen.getByRole("tab", { name: "Журнал" }), { button: 0 });
    await waitFor(() => expect(router.state.location.search).toBe("?tab=journal"));
    expect(screen.getByRole("tab", { name: "Журнал" })).toHaveAttribute("aria-selected", "true");
  });

  it("falls back to «Заявка» for an unknown tab", async () => {
    open("nonsense");
    expect(await screen.findByRole("tab", { name: "Заявка" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  it("moves between tabs with the arrow keys", async () => {
    const { router } = open();
    const first = await screen.findByRole("tab", { name: "Заявка" });
    first.focus();
    fireEvent.keyDown(first, { key: "ArrowRight" });
    await waitFor(() =>
      expect(screen.getByRole("tab", { name: "Клиент" })).toHaveAttribute("aria-selected", "true"),
    );
    expect(router.state.location.search).toBe("?tab=client");
  });
});

describe("BankApplicationPage — tabs", () => {
  it("«Заявка»: parameters and decision history with reasons", async () => {
    open("application");
    expect(await screen.findByText("Параметры заявки")).toBeInTheDocument();
    expect(screen.getByText("Купить фрезерный станок с ЧПУ (демо)")).toBeInTheDocument();
    expect(screen.getByText("36 мес")).toBeInTheDocument();
    const history = screen.getByRole("list", { name: "История решений" });
    expect(within(history).getByText("Нужен сотрудник банка")).toBeInTheDocument();
    expect(within(history).getByText("Система · предварительная оценка")).toBeInTheDocument();
    expect(within(history).getByText("2026.10-v1")).toBeInTheDocument();
    const reasons = within(history).getByRole("list", { name: "Причины решения" });
    expect(within(reasons).getByText("score_total")).toBeInTheDocument();
    expect(within(reasons).getByText("11 290 503 ₽")).toBeInTheDocument();
    expect(within(reasons).getByText("11 290 503 ₽").parentElement).toHaveTextContent("расчёт");
    // The requested amount is the client's word (SRC7).
    const params = screen.getByText("Параметры заявки").closest("div") as HTMLElement;
    const requested = within(params.parentElement as HTMLElement).getByText("8 000 000 ₽");
    expect(requested.parentElement).toHaveTextContent("8 000 000 ₽со слов клиента");
  });

  it("«Заявка»: offer and improvements when the bank has decided", async () => {
    const card = persona4Card();
    card.offer = {
      id: 1,
      product: { name: "Инвестиционный кредит (демо)" } as never,
      amount: "8000000.00",
      requested_amount: "8000000.00",
      term_months: 36,
      rate: "0.2350",
      monthly_payment: "311766.44",
      is_counteroffer: false,
      product_changed: false,
      status: "active",
      expires_at: "2026-11-20T00:00:00Z",
      reasons: [],
    };
    card.decisions.push({
      ...present(card.decisions[0]),
      id: 6,
      outcome: "offer",
      decided_by: "officer",
      is_preliminary: false,
      policy_version: "officer",
      improvements: ["Подключите выписку — оценка станет точнее"],
      comment: "Одобрили на запрошенных условиях",
      created_at: "2026-10-21T09:00:00Z",
    });
    open("application", card);
    expect(await screen.findByText("Оффер")).toBeInTheDocument();
    expect(screen.getByText("23,5 %")).toBeInTheDocument();
    expect(screen.getByText("311 766,44 ₽")).toBeInTheDocument();
    // SRC7: the officer set the amount, the payment is counted.
    const offer = screen.getByText("Оффер").closest("[data-slot=card]") as HTMLElement;
    expect(within(offer).getByText("8 000 000 ₽").parentElement).toHaveTextContent(
      "8 000 000 ₽решение банка",
    );
    expect(within(offer).getByText("311 766,44 ₽").parentElement).toHaveTextContent(
      "311 766,44 ₽расчёт",
    );
    const newest = present(
      within(screen.getByRole("list", { name: "История решений" })).getAllByRole("listitem")[0],
    );
    // Newest first.
    expect(within(newest).getByText("Одобрено")).toBeInTheDocument();
    expect(within(newest).getByText("Сотрудник банка")).toBeInTheDocument();
    expect(within(newest).getByText("Одобрили на запрошенных условиях")).toBeInTheDocument();
    expect(
      within(newest).getByText("Подключите выписку — оценка станет точнее"),
    ).toBeInTheDocument();
  });

  it("«Клиент»: requisites, members with roles, snapshot; null is «нет данных», not 0", async () => {
    open("client");
    expect(await screen.findByText("Реквизиты")).toBeInTheDocument();
    expect(screen.getByText("1260000000042")).toBeInTheDocument();
    expect(screen.getByText("31.09 — Производство прочей мебели")).toBeInTheDocument();
    const members = screen.getByRole("list", { name: "Сотрудники и роли" });
    expect(within(members).getByText("Подписант")).toBeInTheDocument();
    expect(within(members).getByText("Готовит заявки")).toBeInTheDocument();

    const row = (title: string) =>
      (screen.getByText(title).parentElement as HTMLElement).querySelector("dd") as HTMLElement;
    expect(row("Денежный поток на обслуживание долга (CFADS), в месяц")).toHaveTextContent(
      "1 800 000 ₽",
    );
    expect(row("Денежный поток на обслуживание долга (CFADS), в месяц")).toHaveTextContent(
      "1 800 000 ₽по выписке",
    );
    expect(row("Долг")).toHaveTextContent("нет данных");
    expect(row("Долг")).not.toHaveTextContent("по выписке"); // no amount, no label
    expect(row("Выручка год к году (коэффициент)")).not.toHaveTextContent("по выписке");
    expect(row("EBITDA за 12 мес")).toHaveTextContent("нет данных");
    expect(row("Выручка год к году (коэффициент)")).toHaveTextContent("0,97");
    expect(row("Доля крупнейшего покупателя (коэффициент)")).toHaveTextContent("0,4");
    expect(screen.queryByText("0 ₽")).not.toBeInTheDocument();
  });

  it("«Клиент»: a snapshot typed in by hand is the client's word", async () => {
    const card = persona4Card();
    card.snapshot = { ...present(card.snapshot ?? undefined), source: "manual" };
    open("client", card);
    const cfads = await screen.findByText("Денежный поток на обслуживание долга (CFADS), в месяц");
    expect((cfads.parentElement as HTMLElement).querySelector("dd")).toHaveTextContent(
      "1 800 000 ₽со слов клиента",
    );
  });

  it("«Клиент»: no snapshot → empty state", async () => {
    open("client", { ...persona4Card(), snapshot: null });
    expect(await screen.findByText("Снимка нет")).toBeInTheDocument();
  });

  it("«Проверки»: four sources with status in words and summary", async () => {
    open("checks");
    const list = await screen.findByRole("list", { name: "Проверки по источникам" });
    // One item per source; founders and loans are lists of their own inside.
    expect(list.querySelectorAll(":scope > li")).toHaveLength(4);
    expect(within(list).getAllByText("В порядке")).toHaveLength(4);
    expect(within(list).getByText("Бюро кредитных историй")).toBeInTheDocument();
    expect(within(list).getByText("Текущей просрочки нет, прошлая — 10 дн.")).toBeInTheDocument();
  });

  it("«Проверки»: an unavailable source says so and the header warns", async () => {
    const card = persona4Card();
    card.checks[2] = { ...present(card.checks[2]), status: "unavailable", summary: "" };
    open("checks", card);
    const bki = (await screen.findByText("Бюро кредитных историй")).closest("li") as HTMLElement;
    expect(within(bki).getByText("Источник не ответил")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(/источников не ответил/);
  });

  it("«Проверки»: each answer shows when it came, the simulator version and its sha256", async () => {
    open("checks");
    const egrul = (await screen.findByText("ЕГРЮЛ / ЕГРИП")).closest("li") as HTMLElement;
    expect(within(egrul).getByText("Происхождение")).toBeInTheDocument();
    expect(within(egrul).getByText("Ответ получен")).toBeInTheDocument();
    expect(within(egrul).getByText("datagen-2026.10-v1")).toBeInTheDocument();
    expect(within(egrul).getByText("SHA-256 ответа")).toBeInTheDocument();
    // The full hash, not a cut one: the bank compares it with the source's answer.
    expect(
      within(egrul).getByText("04ab99570b8f3edb7b58f8898450582b15487f07647f8d53a2f8c9b24b5bd322"),
    ).toBeInTheDocument();
  });

  it("«Проверки»: a source that did not answer has no provenance and says so", async () => {
    const card = persona4Card();
    card.checks[2] = {
      ...present(card.checks[2]),
      status: "consent_missing",
      summary: "",
      received_at: null,
      response_sha256: null,
      simulator_version: null,
    };
    open("checks", card);
    const bki = (await screen.findByText("Бюро кредитных историй")).closest("li") as HTMLElement;
    expect(within(bki).getByText("Источник не ответил — происхождения нет")).toBeInTheDocument();
    expect(within(bki).queryByText("SHA-256 ответа")).not.toBeInTheDocument();
    expect(within(bki).queryByText("Происхождение")).not.toBeInTheDocument();
  });

  it("«Проверки»: every source says what its status means and lists its answer in words", async () => {
    open("checks");
    const list = await screen.findByRole("list", { name: "Проверки по источникам" });
    const row = (source: string) =>
      list.querySelector(`li[data-source="${source}"]`) as HTMLElement;

    const egrul = row("egrul");
    expect(
      within(egrul).getByText(
        "Компания действует, отметок о недостоверности и предстоящем исключении нет.",
      ),
    ).toBeInTheDocument();
    expect(within(egrul).getByText("Сведения источника")).toBeInTheDocument();
    expect(within(egrul).getByText("Вид деятельности (ОКВЭД)")).toBeInTheDocument();
    expect(within(egrul).getByText("31.09 — Производство прочей мебели")).toBeInTheDocument();
    expect(
      within(egrul).getByText(/Полякова Маргарита Олеговна \(демо\) — ИНН 000300000227/),
    ).toBeInTheDocument();

    const bki = row("bki");
    expect(within(bki).getByText("Самая долгая прошлая просрочка")).toBeInTheDocument();
    expect(within(bki).getByText("10 дн.")).toBeInTheDocument();
    expect(within(bki).getAllByText(/^(Кредит|Лизинг): платёж/)).toHaveLength(2);

    const account = row("bank_account");
    expect(
      within(account).getByText("Выписка получена — показатели снимка посчитаны по ней."),
    ).toBeInTheDocument();
    expect(within(account).getByText("12 мес")).toBeInTheDocument();
    // Nothing is a risk for persona 4.
    expect(screen.queryByText("признак риска")).not.toBeInTheDocument();
  });

  it("«Проверки»: no technical keys anywhere in the tab", async () => {
    const card = persona4Card();
    card.checks[1] = {
      ...present(card.checks[1]),
      status: "warning",
      data: {
        mass_address: false,
        mass_director: false,
        tax_arrears: "0.00",
        employees: 5,
        tax_regime: "usn_income_minus_expenses",
        msp_category: "micro",
        taxes_paid: "612000.00",
        accounts_suspended: true,
      },
    };
    open("checks", card);
    const list = await screen.findByRole("list", { name: "Проверки по источникам" });
    // Status codes, data keys and enum codes are all snake_case or bare latin words.
    expect(list.textContent).not.toMatch(/[a-z]+_[a-z]+/);
    for (const code of ["usn", "micro", "loan", "leasing", "active", "true", "false", "null"]) {
      expect(list.textContent).not.toMatch(new RegExp(`\\b${code}\\b`));
    }
  });

  it("«Проверки»: suspended accounts are a risk said in words", async () => {
    const card = persona4Card();
    card.checks[1] = {
      ...present(card.checks[1]),
      status: "warning",
      data: {
        mass_address: false,
        mass_director: false,
        tax_arrears: "0.00",
        accounts_suspended: true,
      },
    };
    open("checks", card);
    const list = await screen.findByRole("list", { name: "Проверки по источникам" });
    const fns = list.querySelector('li[data-source="transparent_business"]') as HTMLElement;
    expect(within(fns).getByText(/Приостановка операций по счетам — отказ/)).toBeInTheDocument();
    const suspended = within(fns).getByText("Приостановка операций по счетам").parentElement;
    expect(suspended).toHaveTextContent("да");
    expect(within(suspended as HTMLElement).getByText("признак риска")).toBeInTheDocument();
  });

  it.each([
    ["unavailable", {}, "Источник не ответил. Это не отказ"],
    ["restricted", {}, "сведения скрыты. Это не отказ"],
    ["consent_missing", { consent_missing: true }, "Клиент не дал согласие на запрос в БКИ"],
  ] as const)("«Проверки»: БКИ %s — no data is not a decline", async (status, data, text) => {
    const card = persona4Card();
    card.checks[2] = {
      ...present(card.checks[2]),
      status,
      summary: "",
      data,
      received_at: null,
      response_sha256: null,
      simulator_version: null,
    };
    open("checks", card);
    const bki = (await screen.findByText("Бюро кредитных историй")).closest(
      "li[data-source]",
    ) as HTMLElement;
    expect(within(bki).getByText(new RegExp(text))).toBeInTheDocument();
    expect(within(bki).queryByText("Сведения источника")).not.toBeInTheDocument();
  });

  it("«Проверки»: pipeline has not run → empty state", async () => {
    open("checks", { ...persona4Card(), checks: [] });
    expect(await screen.findByText("Проверки ещё не запускались")).toBeInTheDocument();
  });

  it("«Скоринг»: persona 4 — seven factors out of their maxima, 65, grade C, model version", async () => {
    open("scoring");
    const factors = await screen.findByRole("list", { name: "Факторы скоринга" });
    const points = within(factors)
      .getAllByRole("listitem")
      .map((item) => within(item).getByText(/ из /).textContent);
    expect(points).toEqual([
      "10 из 10",
      "18 из 25",
      "7 из 15",
      "10 из 15",
      "7 из 10",
      "8 из 20",
      "5 из 5",
    ]);
    expect(screen.getByText("65 из 100")).toBeInTheDocument();
    expect(screen.getByText("scorecard-2026.10-v1")).toBeInTheDocument();
    const dscr = within(factors).getByText("Запас на платежи по долгам (DSCR)").closest("li");
    expect(dscr).toHaveTextContent("1,8");
    const debt = within(factors).getByText("Долговая нагрузка (долг к EBITDA)").closest("li");
    expect(debt).toHaveTextContent("нет данных");
  });

  it("«Скоринг»: no score yet → empty state", async () => {
    open("scoring", { ...persona4Card(), score: null });
    expect(await screen.findByText("Скоринг ещё не считали")).toBeInTheDocument();
  });

  it("«Документы»: downloads through the API and revokes the object URL", async () => {
    // jsdom has no object URLs; put stubs in and take them out after.
    const revokeObjectURL = vi.fn();
    Object.assign(URL, { createObjectURL: () => "blob:demo", revokeObjectURL });
    onTestFinished(() => {
      Reflect.deleteProperty(URL, "createObjectURL");
      Reflect.deleteProperty(URL, "revokeObjectURL");
    });
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    const { fetchMock } = open("documents", persona4Card(), {
      "GET /api/bank/applications/42/documents/3": { file: "демо" },
    });
    const list = await screen.findByRole("list", { name: "Документы" });
    expect(within(list).getAllByRole("listitem")).toHaveLength(4);
    fireEvent.click(screen.getByRole("button", { name: "Скачать dogovor-demo.pdf" }));
    await waitFor(() => expect(click).toHaveBeenCalledTimes(1));
    expect(
      fetchMock.mock.calls.some(
        ([request]) =>
          new URL((request as Request).url).pathname === "/api/bank/applications/42/documents/3",
      ),
    ).toBe(true);
    await waitFor(() => expect(revokeObjectURL).toHaveBeenCalledWith("blob:demo"));
  });

  it("«Документы»: empty list → empty state", async () => {
    open("documents", { ...persona4Card(), documents: [] });
    expect(await screen.findByText("Документов нет")).toBeInTheDocument();
  });
});

describe("BankApplicationPage — journal", () => {
  it("shows internal events marked as bank-only", async () => {
    open("journal");
    const journal = await screen.findByRole("list", { name: "История заявки" });
    const internal = within(journal).getByText("Попросить отчётность за год").closest("li");
    expect(internal).toHaveTextContent("видно только банку");
    expect(within(journal).getAllByRole("listitem")).toHaveLength(3);
  });

  it("sends a comment and re-reads the card", async () => {
    let sent: unknown;
    const { fetchMock } = open("journal", persona4Card(), {
      "POST /api/bank/applications/42/comments": async (request: Request) => {
        sent = await request.json();
        return [201, { ...persona4Card().events[2], id: 4, message: "Проверить залог" }];
      },
    });
    const field = await screen.findByLabelText("Внутренний комментарий");
    fireEvent.change(field, { target: { value: "Проверить залог" } });
    fireEvent.click(screen.getByRole("button", { name: "Добавить в журнал" }));
    await waitFor(() => expect(sent).toEqual({ message: "Проверить залог" }));
    await waitFor(() => expect(cardCalls(fetchMock)).toBe(2));
    await waitFor(() => expect(field).toHaveValue(""));
  });

  it("shows the server validation error under the field", async () => {
    open("journal", persona4Card(), {
      "POST /api/bank/applications/42/comments": [
        400,
        {
          error: {
            code: "validation_error",
            message: "Проверьте поля",
            details: { message: ["Комментарий слишком длинный"] },
          },
        },
      ],
    });
    const field = await screen.findByLabelText("Внутренний комментарий");
    fireEvent.change(field, { target: { value: "Текст" } });
    fireEvent.click(screen.getByRole("button", { name: "Добавить в журнал" }));
    expect(await screen.findByText("Комментарий слишком длинный")).toBeInTheDocument();
    expect(field).toHaveAttribute("aria-invalid", "true");
    expect(field).toHaveValue("Текст");
  });

  it("does not send an empty comment", async () => {
    const { fetchMock } = open("journal");
    const field = await screen.findByLabelText("Внутренний комментарий");
    fireEvent.change(field, { target: { value: "   " } });
    fireEvent.click(screen.getByRole("button", { name: "Добавить в журнал" }));
    expect(await screen.findByText("Напишите комментарий")).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([request]) => (request as Request).method === "POST")).toBe(
      false,
    );
  });

  it("polling the card keeps the comment being typed", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    // The second answer differs (the client responded), so the card really re-renders.
    const later = persona4Card();
    later.events.push({
      ...present(later.events[0]),
      id: 9,
      kind: "info_responded",
      message: "Ответ клиента",
    });
    let calls = 0;
    open("journal", undefined, {
      [CARD]: () => (++calls === 1 ? persona4Card() : later),
    });
    const field = await screen.findByLabelText("Внутренний комментарий");
    fireEvent.change(field, { target: { value: "Черновик комментария" } });
    await vi.advanceTimersByTimeAsync(15_100);
    expect(await screen.findByText("Ответ клиента")).toBeInTheDocument();
    expect(screen.getByLabelText("Внутренний комментарий")).toHaveValue("Черновик комментария");
  });
});
