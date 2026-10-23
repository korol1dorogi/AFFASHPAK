import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { BankApplicationDetail } from "@/features/bank-application/api";
import { BankApplicationPage } from "@/features/bank-application/BankApplicationPage";
import { PRINT_CSS } from "@/features/bank-application/ConclusionPrint";
import { CreditConclusion } from "@/features/bank-application/CreditConclusion";
import { compareDecimal, officerName } from "@/features/bank-application/conclusion";
import { persona4Card, persona4DecidedCard } from "@/features/bank-application/fixtures";
import { mockApi, renderRoutes } from "@/test/utils";

const GENERATED = new Date("2026-10-22T08:00:00Z");

function show(card: BankApplicationDetail) {
  render(
    <CreditConclusion card={card} product="Инвестиционный кредит (демо)" generatedAt={GENERATED} />,
  );
  return screen.getByRole("article", { name: "Кредитное заключение" });
}

function section(name: string) {
  return screen.getByRole("region", { name });
}

/** Index access under noUncheckedIndexedAccess: fail loudly instead of `!`. */
function present<T>(value: T | undefined): T {
  if (value === undefined) throw new Error("fixture item is missing");
  return value;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("CreditConclusion — persona 4 decided by an officer", () => {
  it("has the head: number, demo mark, assignee", () => {
    const doc = show(persona4DecidedCard());
    expect(within(doc).getByRole("heading", { level: 1 })).toHaveTextContent(
      "Кредитное заключение",
    );
    expect(within(doc).getByText("по заявке № 42")).toBeInTheDocument();
    expect(within(doc).getAllByText("демо").length).toBeGreaterThan(0);
    expect(within(doc).getByText("Анна Банк", { selector: "header span" })).toBeInTheDocument();
  });

  it("shows the client, members and the application", () => {
    show(persona4DecidedCard());
    const client = section("Клиент");
    expect(within(client).getByText("ООО «Дубрава Мебель» (демо)")).toBeInTheDocument();
    expect(within(client).getByText("0001000042")).toBeInTheDocument();
    expect(
      within(client).getByText("Ольга Демо — Главный бухгалтер, Готовит заявки"),
    ).toBeInTheDocument();
    expect(within(client).getByText("6 000 000 ₽")).toBeInTheDocument();
    const application = section("Заявка");
    expect(within(application).getByText("8 000 000 ₽")).toBeInTheDocument();
    expect(within(application).getByText("36 мес")).toBeInTheDocument();
    expect(
      within(application).getByText("Фрезерный станок с ЧПУ по договору поставки (демо)"),
    ).toBeInTheDocument();
  });

  it("lists the four checks in words with their summaries", () => {
    show(persona4DecidedCard());
    const checks = within(section("Проверки источников")).getAllByRole("listitem");
    expect(checks).toHaveLength(4);
    expect(checks[2]).toHaveTextContent(
      "Бюро кредитных историй — В порядке. Текущей просрочки нет",
    );
  });

  it("explains the score factor by factor with the max points of ScoreBreakdown", () => {
    show(persona4DecidedCard());
    const scoring = section("Скоринг");
    expect(within(scoring).getByText("Итого 65 из 100 · грейд C")).toBeInTheDocument();
    const dscr = scoring.querySelector('[data-factor="dscr"]') as HTMLElement;
    expect(dscr).toHaveTextContent("18 из 25");
    expect(within(scoring).getByText(/scorecard-2026\.10-v1/)).toBeInTheDocument();
  });

  it("orders decisions by time; the officer's after a handoff is a plain block, not an alarm", () => {
    show(persona4DecidedCard());
    const history = within(section("Решения и история")).getAllByRole("listitem", {
      name: undefined,
    });
    const items = history.filter((item) => item.hasAttribute("data-decision"));
    expect(items.map((item) => item.getAttribute("data-decision"))).toEqual(["5", "6", "7"]);
    const approve = present(items[2]);
    expect(approve).toHaveTextContent(
      "Решение принял сотрудник: система передала заявку на ручное рассмотрение (Предварительная оценка риска: грейд C (65 из 100)) → сотрудник: ",
    );
    expect(approve).toHaveTextContent("Анна Банк");
    expect(approve).toHaveTextContent("Отчётность подтверждает поток");
    expect(
      screen.queryByRole("note", { name: "Сотрудник изменил предварительную оценку" }),
    ).toBeNull();
    // The info request is named from its own journal event.
    expect(present(items[1])).toHaveTextContent("Анна Банк");
  });

  it("names reasons by title with the metric code next to it", () => {
    show(persona4DecidedCard());
    const reasons = within(section("Решения и история")).getAllByRole("list", { name: "Причины" });
    const first = present(reasons[0]);
    expect(within(first).getByText("Оценка риска")).toBeInTheDocument();
    expect(within(first).getByText("score_total")).toBeInTheDocument();
    expect(first).toHaveTextContent("11 290 503 ₽");
  });

  it("shows the current offer and the answered info request", () => {
    show(persona4DecidedCard());
    const offer = section("Текущее предложение");
    expect(within(offer).getByText("23,5 %")).toBeInTheDocument();
    expect(within(offer).getByText("311 766,44 ₽")).toBeInTheDocument();
    expect(section("Запросы информации")).toHaveTextContent("Загрузили отчётность (демо)");
  });

  it("ends with the demo note and a place for the signature", () => {
    const doc = show(persona4DecidedCard());
    expect(within(doc).getByText(/Синтетические данные, демо/)).toBeInTheDocument();
    expect(within(doc).getByText("подпись")).toBeInTheDocument();
  });
});

describe("CreditConclusion — handoff cause", () => {
  it("names the failed decision rule, not a scorecard factor that only lowered the score", () => {
    const card = persona4DecidedCard();
    const auto = present(card.decisions[0]);
    auto.reasons.unshift({
      metric: "debt_to_ebitda",
      value: null,
      threshold: "3.5",
      passed: false,
      message: "Отчётности нет — долговую нагрузку оценили по счёту",
    });
    show(card);
    const approve = section("Решения и история").querySelector('[data-decision="7"]');
    expect(approve).toHaveTextContent("(Предварительная оценка риска: грейд C (65 из 100))");
  });
});

describe("CreditConclusion — empty and missing data", () => {
  it("says so when there are no checks, score, decisions, snapshot or offer", () => {
    const card = persona4Card();
    card.checks = [];
    card.score = null;
    card.decisions = [];
    card.snapshot = null;
    show(card);
    expect(section("Проверки источников")).toHaveTextContent("Проверки ещё не проводились");
    expect(section("Скоринг")).toHaveTextContent("Скоринг ещё не считали");
    expect(section("Решения и история")).toHaveTextContent("Решений пока нет");
    expect(section("Клиент")).toHaveTextContent("показатели посчитать не из чего");
    expect(section("Текущее предложение")).toHaveTextContent("Предложения нет.");
  });

  it("null metrics are «нет данных», never 0", () => {
    show(persona4Card());
    const client = section("Клиент");
    const revenue = within(client).getByText("Выручка за 12 мес:").parentElement as HTMLElement;
    expect(revenue).toHaveTextContent("нет данных");
    const factor = section("Скоринг").querySelector(
      '[data-factor="debt_to_ebitda"]',
    ) as HTMLElement;
    expect(factor).toHaveTextContent("нет данных");
  });
});

describe("CreditConclusion — an officer overrides the system", () => {
  it("highlights a different outcome after the system's verdict: who, when and why", () => {
    const card = persona4DecidedCard();
    const auto = present(card.decisions[0]);
    auto.outcome = "declined";
    auto.is_preliminary = true;
    card.decisions = [auto, present(card.decisions[2])];
    show(card);
    const note = screen.getByRole("note", { name: "Сотрудник изменил предварительную оценку" });
    expect(note).toHaveTextContent("Система: «Отказ» → сотрудник: «Одобрено»");
    expect(note).toHaveTextContent("Кто и когда: Анна Банк");
    expect(note).toHaveTextContent("Почему: Отчётность подтверждает поток");
  });

  it("highlights approval above the amount the system allows", () => {
    const card = persona4DecidedCard();
    const offer = present(card.offer ?? undefined);
    card.offer = { ...offer, amount: "12000000.00", requested_amount: "12000000.00" };
    show(card);
    const note = screen.getByRole("note", { name: "Сотрудник изменил предварительную оценку" });
    expect(note).toHaveTextContent(
      "Сотрудник одобрил 12 000 000 ₽ — больше допустимой суммы системы 11 290 503 ₽",
    );
  });

  it("no comment → «обоснование не указано»; no journal event → «Сотрудник банка»", () => {
    const card = persona4DecidedCard();
    const auto = present(card.decisions[0]);
    auto.outcome = "counteroffer";
    card.decisions = [auto, { ...present(card.decisions[2]), comment: null }];
    card.events = [];
    show(card);
    const note = screen.getByRole("note", { name: "Сотрудник изменил предварительную оценку" });
    expect(note).toHaveTextContent("Кто и когда: Сотрудник банка");
    expect(note).toHaveTextContent("Почему: обоснование не указано");
  });

  it("the same outcome as the system's verdict is not an override", () => {
    const card = persona4DecidedCard();
    const auto = present(card.decisions[0]);
    auto.outcome = "offer";
    card.decisions = [auto, present(card.decisions[2])];
    show(card);
    expect(screen.queryByRole("note")).toBeNull();
  });
});

describe("conclusion helpers", () => {
  it("compares decimal strings without floats", () => {
    expect(compareDecimal("12000000.00", "11290503.00")).toBe(1);
    expect(compareDecimal("8000000.00", "11290503.00")).toBe(-1);
    expect(compareDecimal("8000000", "8000000.00")).toBe(0);
    expect(compareDecimal("0.10", "0.09")).toBe(1);
    expect(compareDecimal("abc", "1")).toBeNull();
  });

  it("takes the officer's name only from a bank event of the same kind close in time", () => {
    const card = persona4DecidedCard();
    const approve = present(card.decisions[2]);
    expect(officerName(approve, card.events)).toBe("Анна Банк");
    const late = card.events.map((event) =>
      event.kind === "decision" ? { ...event, created_at: "2026-10-21T13:00:00Z" } : event,
    );
    expect(officerName(approve, late)).toBeNull();
  });
});

describe("BankApplicationPage — credit conclusion", () => {
  function open() {
    mockApi({
      "GET /api/bank/applications/42": persona4DecidedCard(),
      "GET /api/products": [
        { code: "investment_loan_basic", name: "Инвестиционный кредит (демо)" },
      ],
    });
    renderRoutes(
      [{ path: "/bank/applications/:id", element: <BankApplicationPage /> }],
      "/bank/applications/42",
    );
  }

  it("opens a full-screen preview outside the app root; «Сохранить в PDF» prints", async () => {
    const print = vi.fn();
    vi.stubGlobal("print", print);
    open();
    expect(screen.queryByRole("dialog")).toBeNull();
    fireEvent.click(await screen.findByRole("button", { name: "Кредитное заключение" }));
    const dialog = screen.getByRole("dialog", { name: "Предпросмотр кредитного заключения" });
    // A direct child of <body>: the print rule hides every other child (the app).
    expect(dialog.parentElement).toBe(document.body);
    expect(dialog).toHaveAttribute("data-credit-conclusion");
    expect(dialog.querySelector("style")?.textContent).toBe(PRINT_CSS);
    expect(PRINT_CSS).toContain(
      "body > :not([data-credit-conclusion]) { display: none !important; }",
    );
    expect(PRINT_CSS).toContain("size: A4");
    expect(
      within(dialog).getByRole("article", { name: "Кредитное заключение" }),
    ).toBeInTheDocument();

    fireEvent.click(within(dialog).getByRole("button", { name: "Сохранить в PDF" }));
    expect(print).toHaveBeenCalledTimes(1);

    fireEvent.click(within(dialog).getByRole("button", { name: "Закрыть" }));
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("keeps Tab inside the preview and gives focus back to its button (UX2)", async () => {
    open();
    const opener = await screen.findByRole("button", { name: "Кредитное заключение" });
    opener.focus();
    fireEvent.click(opener);
    const dialog = screen.getByRole("dialog", { name: "Предпросмотр кредитного заключения" });
    const print = within(dialog).getByRole("button", { name: "Сохранить в PDF" });
    const close = within(dialog).getByRole("button", { name: "Закрыть" });
    expect(print).toHaveFocus();
    close.focus();
    fireEvent.keyDown(window, { key: "Tab" });
    expect(print).toHaveFocus();
    fireEvent.keyDown(window, { key: "Tab", shiftKey: true });
    expect(close).toHaveFocus();
    fireEvent.keyDown(window, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(opener).toHaveFocus();
  });

  it("closes the preview with Escape", async () => {
    open();
    fireEvent.click(await screen.findByRole("button", { name: "Кредитное заключение" }));
    fireEvent.keyDown(window, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("Ctrl+P on the card prints the conclusion: it is mounted on beforeprint", async () => {
    open();
    await screen.findByRole("button", { name: "Кредитное заключение" });
    expect(document.querySelector("[data-credit-conclusion]")).toBeNull();
    fireEvent(window, new Event("beforeprint"));
    expect(document.querySelector("[data-credit-conclusion]")).not.toBeNull();
    fireEvent(window, new Event("afterprint"));
    await waitFor(() => expect(document.querySelector("[data-credit-conclusion]")).toBeNull());
  });
});
