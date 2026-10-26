import { expect, type Page, test } from "@playwright/test";

import {
  acceptAndSign,
  createDraft,
  csrfHeaders,
  demoPdf,
  NBSP,
  personaPage,
  rub,
  signInAs,
  submitFromWizard,
} from "./support";

/** The application's status as the header badge shows it (STATUS labels, frontend texts). */
function statusBadge(page: Page) {
  return page.locator("[data-status]").first();
}

// Client and bank journeys = scenarios 1–8 (docs/test-scenarios.md; personas: docs/demo.md,
// statuses: docs/state-machine.md). Every test makes its own application, so they run on a stand
// with any amount of data and in any order.
test.describe("scenario 1: coffee shop — overdraft, auto offer, signing, disbursement", () => {
  test("client logs in as the persona and sees the dashboard (C2, C8)", async ({ page }) => {
    await signInAs(page, "кофейня «Зерно и пар»");
    await expect(page).toHaveURL(/\/app$/);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(
      "Здравствуйте, Анна Сергеевна",
    );
    await expect(page.getByText("Подписант")).toBeVisible();
  });
  test("match recommends an overdraft of 900 000 ₽ with reasons (C4)", async ({ page }) => {
    await signInAs(page, "кофейня «Зерно и пар»");
    await expect(page).toHaveURL(/\/app$/);
    await page.goto("/app/match");
    await page.getByText("Покрытие кассового разрыва").click();
    await page.getByRole("button", { name: "Подобрать продукт" }).click();
    const first = page.locator("article").first();
    await expect(first).toContainText("Овердрафт");
    await expect(first).toContainText(rub("900 000"));
    await expect(first.getByText("Лимит по оборотам")).toBeVisible();
  });

  test("wizard prefills the application; director submits (C5)", async ({ page }) => {
    await signInAs(page, "кофейня «Зерно и пар»");
    await expect(page).toHaveURL(/\/app$/);
    await page.goto("/app/match");
    await page.getByText("Покрытие кассового разрыва").click();
    await page.getByRole("button", { name: "Подобрать продукт" }).click();
    await page.getByRole("button", { name: "Оформить заявку" }).first().click();
    await expect(page).toHaveURL(/\/edit\/business$/);
    // F12: the company comes from the registry, nothing is typed again
    await expect(page.getByText("Лаврова Анна Сергеевна (демо)").first()).toBeVisible();
    await expect(page.getByRole("list", { name: "Показатели бизнеса" })).toBeVisible();
    const id = Number(page.url().match(/applications\/(\d+)/)?.[1]);
    // SRC1: without the consent the application stays a draft
    await page.goto(`/app/applications/${id}/edit/review`);
    await page.getByRole("button", { name: "Отправить в банк" }).click();
    await expect(page.getByRole("alert")).toContainText("Поставьте галочку согласия");
    await expect(page).toHaveURL(/\/edit\/review$/);
    await submitFromWizard(page, id);
    await expect(statusBadge(page)).toHaveText("Есть предложение");
    await expect(page.getByText("Согласие на запрос кредитной истории")).toBeVisible();
  });

  test("auto offer → accept → sign with the on-screen code → issued (C6, C7)", async ({ page }) => {
    await signInAs(page, "кофейня «Зерно и пар»");
    await expect(page).toHaveURL(/\/app$/);
    const id = await createDraft(page, {
      need_type: "cash_gap",
      product_code: "overdraft_basic",
      purpose: "Зарплата сотрудникам до поступлений от покупателей (демо)",
      requested_amount: "900000.00",
      term_months: 12,
    });
    await submitFromWizard(page, id);
    await expect(statusBadge(page)).toHaveText("Есть предложение");
    const offer = page.getByRole("article", { name: "Предложение банка" });
    await expect(offer).toContainText(rub("900 000"));
    await expect(offer).toContainText("Зависит от использования лимита");
    await expect(page.getByText("Предварительная оценка").first()).toBeVisible();
    await acceptAndSign(page, id);
  });
});

test.describe("scenario 2: supplier — factoring for a shipment", () => {
  test("factoring offer of 4 500 000 ₽ for the UPD amount → issued (C4, C7)", async ({ page }) => {
    await signInAs(page, "Северный поставщик");
    await expect(page).toHaveURL(/\/app$/);
    const id = await createDraft(
      page,
      {
        need_type: "receivable_delay",
        product_code: "factoring_basic",
        purpose: "Покупатель оплатит отгрузку через 60 дней (демо)",
        requested_amount: "4500000.00",
        term_months: 2,
        invoice_amount: "5000000.00",
      },
      ["contract", "shipment_document"],
    );
    await submitFromWizard(page, id);
    await expect(statusBadge(page)).toHaveText("Есть предложение");
    const offer = page.getByRole("article", { name: "Предложение банка" });
    await expect(offer).toContainText(rub("4 500 000"));
    await expect(page.getByText(`Сразу можно получить 90% от суммы отгрузки: ${rub("4 500 000")}`)).toBeVisible();
    await acceptAndSign(page, id);
  });
});

test.describe("scenario 3: seasonal store — counteroffer by DSCR", () => {
  test("asks 5.3 mln → counteroffer 2 009 314 ₽ with reasons → accepts → issued (C7)", async ({
    page,
  }) => {
    await signInAs(page, "садовый центр «Зелёный двор»");
    await expect(page).toHaveURL(/\/app$/);
    const id = await createDraft(
      page,
      {
        need_type: "working_capital",
        product_code: "working_capital_loan_basic",
        purpose: "Закупка рассады и инвентаря к сезону (демо)",
        requested_amount: "5300000.00",
        term_months: 12,
      },
      ["bank_statement", "tax_return"],
    );
    await submitFromWizard(page, id);

    // P7 auto_counteroffer: grade B (87), the amount is capped by DSCR
    await expect(statusBadge(page)).toHaveText("Есть предложение");
    await expect(page.getByText("Банк предлагает другие условия")).toBeVisible();
    const offer = page.getByRole("article", { name: "Предложение банка" });
    await expect(offer).toContainText("Другие условия");
    await expect(offer).toContainText(rub("2 009 314"));
    await expect(offer).toContainText(`Запрошено: ${rub("5 300 000")}`);
    await expect(offer).toContainText(`24${NBSP}%`);
    await expect(offer).toContainText(`12${NBSP}мес`);
    await expect(offer).toContainText(rub("189 999,92"));
    const why = offer.getByRole("list", { name: "Обоснование условий" });
    await expect(why).toContainText("87 баллов из 100, это оценка B");
    await expect(why).toContainText("На 12 месяцев под 24% можно взять не больше 2 009 314 ₽");
    await expect(why).toContainText("свободных денег в 1,25 раза больше, чем уходит на все платежи");

    await acceptAndSign(page, id);
  });
  // docs/test-scenarios.md scenario 3, step 5: the counteroffer screen also shows «что улучшить»
  // («Если взять на 24 месяца, можно получить до 3 593 645 ₽») and calls it a preliminary evaluation. Bug:
  // ApplicationPage hides DecisionCard while an offer is active and OfferCard renders neither.
  test("counteroffer screen shows what to improve and says «предварительная оценка» (C6)", async ({
    page,
  }) => {
    await signInAs(page, "садовый центр «Зелёный двор»");
    await expect(page).toHaveURL(/\/app$/);
    const id = await createDraft(
      page,
      {
        need_type: "working_capital",
        product_code: "working_capital_loan_basic",
        purpose: "Закупка рассады и инвентаря к сезону (демо)",
        requested_amount: "5300000.00",
        term_months: 12,
      },
      ["bank_statement", "tax_return"],
    );
    await submitFromWizard(page, id);
    await expect(statusBadge(page)).toHaveText("Есть предложение");
    await expect(page.getByText("Предварительная оценка").first()).toBeVisible();
    const improve = page.getByRole("list", { name: "Что можно улучшить" });
    await expect(improve).toContainText(`Если взять на 24 месяца, можно получить до ${rub("3 593 645")}`);
  });
});

test.describe("scenario 4: manufacturer — manual review and info request", () => {
  // One test: both halves need the same application, and tests must not depend on each other.
  test("accountant hands off → director notified → grade C → manual review → bank requests a document → client uploads and responds → bank approves → issued (B4, B5, C6, C7, XP5)", async ({
    browser,
  }) => {
    // Three people and about ten steps: 22–25 s alone, past the default 30 s in a full run.
    test.slow();
    const accountant = await personaPage(
      browser,
      "Главный бухгалтер: ООО «Дубрава Мебель»",
      /\/app$/,
    );
    const director = await personaPage(browser, /^ООО «Дубрава Мебель»/, /\/app$/);
    const bank = await personaPage(browser, "Сотрудник банка", /\/bank/);
    let id = 0;

    await test.step("the accountant prepares the draft, cannot send it and hands it to the director", async () => {
      id = await createDraft(
        accountant,
        {
          need_type: "capex",
          product_code: "investment_loan_basic",
          purpose: "Покупка фрезерного станка с ЧПУ (демо)",
          requested_amount: "8000000.00",
          term_months: 36,
          collateral_description: "Фрезерный станок с ЧПУ по договору поставки (демо)",
        },
        ["bank_statement", "tax_return", "contract", "invoice"],
      );
      await accountant.goto(`/app/applications/${id}/edit/review`);
      await expect(accountant.getByText("Отправить заявку может только подписант")).toBeVisible();
      await expect(accountant.getByRole("button", { name: "Отправить в банк" })).toHaveCount(0);
      await accountant.getByRole("button", { name: "Передать директору" }).click();
      await expect(accountant.getByRole("status")).toContainText(
        "Передано: подписант получил уведомление",
      );
    });

    await test.step("the director gets the notification and opens the draft from it (XP5)", async () => {
      await director.goto("/app");
      await director.getByRole("link", { name: /^Уведомления, непрочитанных/ }).click();
      const note = director
        .getByRole("listitem")
        .filter({ hasText: `Заявка № ${id} готова к отправке` });
      await expect(note).toContainText("отправить заявку может только подписант");
      await note.getByRole("link", { name: "Открыть заявку" }).click();
      await expect(director).toHaveURL(new RegExp(`/app/applications/${id}$`));
      await expect(director.getByText("Заявка передана подписанту на отправку.")).toBeVisible();
    });

    await test.step("the director sends it; grade C goes to an officer", async () => {
      await submitFromWizard(director, id);
      await expect(statusBadge(director)).toHaveText("У сотрудника банка");
      await expect(director.getByRole("list", { name: "Причины" })).toContainText(
        "65 баллов из 100, это оценка C",
      );
      // BKI1: the 10-day overdue of two years ago is explained, not left as a black box (L01, R04)
      const history = director.getByRole("region", { name: "Кредитная история: что увидел банк" });
      await expect(history).toContainText("10 дней, а банк допускает до 30 дней");
      await expect(history.getByRole("listitem").first()).toContainText("Госуслугах");
    });

    await test.step("the officer finds it in the queue, takes it and asks for a document", async () => {
      await bank.goto(
        "/bank?status=manual_review&grade=C&search=0001000042&ordering=-status_changed_at",
      );
      await bank.getByRole("link", { name: `Заявка № ${id}`, exact: true }).click();
      await expect(bank).toHaveURL(new RegExp(`/bank/applications/${id}`));
      await bank.getByRole("tab", { name: "Скоринг" }).click();
      await expect(bank.getByRole("tabpanel")).toContainText("65");

      const actions = bank.getByRole("complementary", { name: "Действия сотрудника" });
      await actions.getByRole("button", { name: "Взять в работу" }).click();
      await expect(bank.getByText("Заявка у вас в работе")).toBeVisible();
      const assignee = bank.locator("dt", { hasText: "Исполнитель" }).locator("xpath=../dd");
      await expect(assignee).not.toHaveText("Не назначен");

      await actions.getByRole("button", { name: "Запросить информацию" }).click();
      const dialog = bank.getByRole("dialog");
      await dialog
        .getByLabel("Что нужно от клиента")
        .fill(
          "Загрузите бухгалтерскую отчётность за последний год — по ней оценим долговую нагрузку",
        );
      await dialog.getByRole("button", { name: "Отправить запрос" }).click();
      await expect(dialog).toHaveCount(0);
      await expect(statusBadge(bank)).toHaveText("Нужны уточнения");
    });

    await test.step("the accountant uploads the report and answers", async () => {
      await accountant.goto(`/app/applications/${id}`);
      await expect(statusBadge(accountant)).toHaveText("Нужны уточнения");
      const request = accountant
        .locator('[data-slot="card"]')
        .filter({ has: accountant.getByRole("heading", { name: "Банк просит уточнить" }) });
      await expect(request).toContainText(
        "Загрузите бухгалтерскую отчётность за последний год — по ней оценим долговую нагрузку",
      );
      await request.getByLabel("Тип документа").selectOption({ label: "Бухгалтерская отчётность" });
      await request.locator('input[type="file"]').setInputFiles(demoPdf("financial_report"));
      await expect(accountant.getByText("Загружено: financial_report_demo.pdf")).toBeVisible();
      await request.getByLabel("Ответ банку").fill("Загрузили отчётность за последний год");
      await request.getByRole("button", { name: "Ответить банку" }).click();
      await expect(statusBadge(accountant)).toHaveText("У сотрудника банка");
    });

    await test.step("the officer sees the report and approves", async () => {
      await bank.reload();
      await expect(statusBadge(bank)).toHaveText("У сотрудника банка");
      await bank.getByRole("tab", { name: "Документы" }).click();
      await expect(bank.getByRole("tabpanel")).toContainText("Бухгалтерская отчётность");

      await bank
        .getByRole("complementary", { name: "Действия сотрудника" })
        .getByRole("button", { name: "Одобрить", exact: true })
        .click();
      const dialog = bank.getByRole("dialog");
      await expect(dialog).toContainText(`${rub("8 000 000")} на 36 месяцев`);
      await dialog.getByRole("button", { name: "Одобрить", exact: true }).click();
      await expect(dialog).toHaveCount(0);
      await expect(statusBadge(bank)).toHaveText("Есть предложение");
    });

    await test.step("only the director can accept: 8 000 000 ₽ at 23,5 % for 36 months", async () => {
      await accountant.reload();
      await expect(statusBadge(accountant)).toHaveText("Есть предложение");
      await expect(accountant.getByRole("button", { name: "Принять и подписать" })).toHaveCount(0);

      await director.goto(`/app/applications/${id}`);
      const offer = director.getByRole("article", { name: "Предложение банка" });
      await expect(offer).toContainText(rub("8 000 000"));
      await expect(offer).toContainText(`23,5${NBSP}%`);
      await expect(offer).toContainText(`36${NBSP}мес`);
      await expect(offer).toContainText(rub("311 766,44"));
      await acceptAndSign(director, id);
    });
  });
});

test.describe("scenario 5: dependent supplier — decline with improvements", () => {
  test("decline shows reasons and what to improve (C6)", async ({ page }) => {
    await signInAs(page, "ООО «Опора Снаб»");
    await expect(page).toHaveURL(/\/app$/);
    const id = await createDraft(
      page,
      {
        need_type: "working_capital",
        product_code: "working_capital_loan_basic",
        purpose: "Пополнение оборотных средств под поставки (демо)",
        requested_amount: "3000000.00",
        term_months: 12,
      },
      ["bank_statement", "tax_return"],
    );
    await submitFromWizard(page, id);

    // P4 auto_decline: grade E (47), docs/test-scenarios.md scenario 5
    await expect(statusBadge(page)).toHaveText("Отказ");
    await expect(page.getByRole("heading", { name: "Предварительная оценка" })).toBeVisible();
    const reasons = page.getByRole("list", { name: "Причины" });
    await expect(reasons).toContainText("47 баллов из 100, это оценка E");
    await expect(reasons).toContainText("только 1,1 ₽ свободных денег, а нужно не меньше 1,25 ₽");
    await expect(reasons).toContainText(
      "Чтобы отдать долги, понадобится операционная прибыль (EBITDA) за 4,2 года, а норма — не больше 3,5 года",
    );
    await expect(reasons).toContainText("Выручка за последние три месяца на 20% меньше, чем год назад");
    await expect(reasons).toContainText("80% денег приносит один покупатель");
    await expect(
      page
        .getByText("Что можно улучшить", { exact: true })
        .locator("xpath=following-sibling::ol[1]/li"),
    ).toHaveText([
      /Снизьте платежи по текущим долгам или увеличьте остаток денег после расходов/,
      /Снизьте долг так, чтобы его можно было отдать из прибыли за 3,5 года/,
      /Верните выручку хотя бы к уровню прошлого года/,
      /Найдите ещё покупателей, чтобы на крупнейшего приходилось не больше 50% поступлений/,
    ]);
  });
});

test.describe("scenario 6: company in liquidation — stop factor", () => {
  test("instant decline with the stop factor (L4, C6)", async ({ page }) => {
    await signInAs(page, "ООО «Вектор Сервис»");
    await expect(page).toHaveURL(/\/app$/);
    const id = await createDraft(page, {
      need_type: "cash_gap",
      product_code: "overdraft_basic",
      purpose: "Покрыть кассовый разрыв до оплаты клиентов (демо)",
      requested_amount: "500000.00",
      term_months: 6,
    });
    await submitFromWizard(page, id);

    // P1, stop factor C1: declined without a grade, nothing to improve
    await expect(statusBadge(page)).toHaveText("Отказ");
    await expect(page.getByRole("heading", { name: "Предварительная оценка" })).toBeVisible();
    const reasons = page.getByRole("list", { name: "Причины" }).getByRole("listitem");
    await expect(reasons).toHaveCount(1);
    await expect(reasons).toContainText("Статус в реестре");
    await expect(reasons).toContainText(
      "По данным ЕГРЮЛ компания ликвидируется, поэтому кредит выдать нельзя",
    );
    await expect(page.getByText(/(Оценка риска|это оценка) [A-E]/)).toHaveCount(0);
    await expect(page.getByText("Что можно улучшить", { exact: true })).toHaveCount(0);
  });
});

test.describe("scenario 7: BKI outage — manual review", () => {
  test("demo panel turns BKI off → application lands in manual review with a note, breaker opens (B7, L4, XP6)", async ({
    browser,
  }) => {
    const bank = await personaPage(browser, "Сотрудник банка", /\/bank/);
    const setFailures = async (bki: boolean) => {
      // Safety net for `finally`: the stand must not keep the outage whatever failed above.
      const response = await bank.request.put("/api/demo/failures", {
        headers: await csrfHeaders(bank),
        data: { egrul: false, transparent_business: false, bki, bank_account: false },
      });
      expect(response.status()).toBe(200);
    };
    const bkiRow = bank.locator('li[data-source="bki"]');

    // XP6: two clicks on the panel — switch BKI off, then the persona submits.
    await bank.goto("/bank/demo");
    await bkiRow.getByRole("switch").check();
    await expect(bkiRow).toContainText("Сбой");
    await expect(bkiRow).toContainText("Предохранитель в норме");
    let id: number;
    try {
      const client = await personaPage(browser, "кофейня «Северный ветер»", /\/app$/);
      id = await createDraft(client, {
        need_type: "cash_gap",
        product_code: "overdraft_basic",
        purpose: "Покрыть кассовый разрыв до оплаты клиентов (демо)",
        requested_amount: "900000.00",
        term_months: 12,
      });
      await submitFromWizard(client, id);

      // P3 needs_review: the outage sends the application to an officer, it is not a decline
      await expect(statusBadge(client)).toHaveText("У сотрудника банка");
      await expect(client.getByRole("heading", { name: "Предварительная оценка" })).toBeVisible();
      const reasons = client.getByRole("list", { name: "Причины" });
      await expect(reasons).toContainText(
        "Бюро кредитных историй сейчас не отвечает, поэтому заявку проверит сотрудник банка. Это не отказ",
      );
      await expect(reasons).toContainText("82 балла из 100, это оценка B");

      // The application met the outage: three failed calls opened the breaker for everyone.
      await expect(bkiRow).toContainText("Предохранитель сработал");
      await expect(bkiRow).toContainText("3 ошибки подряд");
      await expect(bkiRow).toContainText(/повтор через \d+ с/);

      // Back on: the operator fixed the source, its breaker closes at once.
      await bkiRow.getByRole("switch").uncheck();
      await expect(bkiRow).toContainText("Работает");
      await expect(bkiRow).toContainText("Предохранитель в норме");
    } finally {
      await setFailures(false);
    }

    await bank.goto("/bank?status=manual_review&search=000100000702&ordering=-status_changed_at");
    const link = bank.getByRole("link", { name: `Заявка № ${id}`, exact: true });
    const row = bank.getByRole("row").filter({ has: link });
    await expect(row.getByRole("img", { name: "Источник недоступен" })).toBeVisible();

    await link.click();
    await expect(bank).toHaveURL(new RegExp(`/bank/applications/${id}`));
    await expect(
      bank.getByRole("status").filter({ hasText: "Один из источников не ответил" }),
    ).toContainText("Это не отказ: проверьте заявку вручную.");
    const actions = bank.getByRole("complementary", { name: "Действия сотрудника" });
    for (const action of [
      "Взять в работу",
      "Одобрить",
      "Другие условия",
      "Запросить информацию",
      "Отказать",
    ]) {
      await expect(actions.getByRole("button", { name: action, exact: true })).toBeVisible();
    }
    await bank.getByRole("tab", { name: "Проверки" }).click();
    await expect(bank.getByRole("tabpanel")).toContainText("Бюро кредитных историй");
    await expect(bank.getByRole("tabpanel")).toContainText("Источник не ответил");
  });
});

test.describe("scenario 8: equipment without collateral — alternative product", () => {
  test("investment loan without collateral → leasing offer → issued (S6, D15)", async ({ page }) => {
    await signInAs(page, "Ковка и Фреза");
    await expect(page).toHaveURL(/\/app$/);
    const id = await createDraft(
      page,
      {
        need_type: "capex",
        product_code: "investment_loan_basic",
        purpose: "Покупка токарно-фрезерного центра с ЧПУ (демо)",
        requested_amount: "12000000.00",
        term_months: 36,
      },
      ["bank_statement", "tax_return", "contract", "invoice"],
    );
    await submitFromWizard(page, id);
    // P6: the loan needs collateral → leasing; P7: the amount by DSCR.
    // The pipeline runs in the worker and the page polls every 3 s: 5 s is one poll, too tight
    // under a full run.
    await expect(page.getByText("Банк предлагает другой продукт")).toBeVisible({ timeout: 15_000 });
    const offer = page.getByRole("article", { name: "Предложение банка" });
    await expect(offer).toContainText("Другой продукт");
    await expect(offer).toContainText(rub("11 443 551"));
    await expect(offer).toContainText(rub("440 000"));
    await expect(offer.getByText("Почему предложен другой продукт")).toBeVisible();
    await expect(offer).toContainText(
      "Инвестиционный кредит выдают только под залог, зато подходит лизинг оборудования и транспорта",
    );
    await acceptAndSign(page, id);
  });
});

test.describe("access", () => {
  test("another client cannot open this application (404) (L3)", async ({ browser }) => {
    const owner = await (await browser.newContext()).newPage();
    await signInAs(owner, "кофейня «Зерно и пар»");
    await expect(owner).toHaveURL(/\/app$/);
    const created = await owner.request.post("/api/applications", {
      headers: await csrfHeaders(owner),
      data: {
        need_type: "cash_gap",
        purpose: "Демо: проверка доступа",
        requested_amount: "300000.00",
        term_months: 3,
      },
    });
    expect(created.status()).toBe(201);
    const { id } = await created.json();

    const stranger = await (await browser.newContext()).newPage();
    await signInAs(stranger, "Северный поставщик");
    await expect(stranger).toHaveURL(/\/app$/);
    expect((await stranger.request.get(`/api/applications/${id}`)).status()).toBe(404);
    await stranger.goto(`/app/applications/${id}`);
    await expect(stranger.getByText("Заявка не найдена")).toBeVisible();
  });
});
