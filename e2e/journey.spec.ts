import { expect, type Page, test } from "@playwright/test";

import {
  createDraft,
  csrfHeaders,
  demoPdf,
  personaPage,
  rub,
  signInAs,
  submitFromWizard,
} from "./support";

/** The application's status as the header badge shows it (STATUS labels, frontend texts). */
function statusBadge(page: Page) {
  return page.locator("[data-status]").first();
}

// Client and bank journeys = the 7 scenarios from docs/plan.md (personas: docs/demo.md,
// statuses: docs/state-machine.md). Each test becomes real when its task is done
// (docs/tasks.md "Готово, когда"); until then it stays fixme.
test.describe("scenario 1: coffee shop — overdraft, auto offer, signing, disbursement", () => {
  test("client logs in as the persona and sees the dashboard (C2, C8)", async ({ page }) => {
    await signInAs(page, "кофейня «Зерно и пар»");
    await expect(page).toHaveURL(/\/app$/);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(
      "Здравствуйте, Анна Сергеевна",
    );
    await expect(page.getByText("Подписант")).toBeVisible();
  });
  test.fixme("match recommends an overdraft of 900 000 ₽ with reasons (C4)", async () => {});
  test.fixme("wizard prefills the application; director submits (C5)", async () => {});
  test.fixme("auto offer → accept → sign with the on-screen code → issued (C6, C7)", async () => {});
});

test.describe("scenario 2: supplier — factoring for a shipment", () => {
  test.fixme("factoring offer of 4 500 000 ₽ for the UPD amount → issued (C4, C7)", async () => {});
});

test.describe("scenario 3: seasonal store — counteroffer by DSCR", () => {
  test.fixme("asks 5.3 mln → counteroffer 2 009 314 ₽ with reasons → accepts → issued (C7)", async () => {});
});

test.describe("scenario 4: manufacturer — manual review and info request", () => {
  test.fixme("grade C → manual review; bank requests a document (B4, B5)", async () => {});
  test.fixme("client uploads the document and responds; bank approves (C6, B5)", async () => {});
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
    await expect(reasons).toContainText("Грейд E (47 из 100)");
    await expect(reasons).toContainText("1,1 ₽ на рубль при норме 1,25");
    await expect(reasons).toContainText("Долги — 4,2 годовых прибыли, это больше нормы 3,5");
    await expect(reasons).toContainText("Выручка упала на 20% к прошлому году");
    await expect(reasons).toContainText("80% денег приходит от одного покупателя");
    await expect(
      page.getByText("Что можно улучшить", { exact: true }).locator("xpath=following-sibling::ol[1]/li"),
    ).toHaveText([
      /Снизьте текущие платежи по долгам или увеличьте свободный денежный поток/,
      /Снизьте долг до 3,5 годовой прибыли/,
      /Восстановите выручку хотя бы до уровня прошлого года/,
      /Снизьте долю крупнейшего покупателя до 50% и меньше/,
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
      "По данным ЕГРЮЛ компания в процессе ликвидации — кредит оформить нельзя",
    );
    await expect(page.getByText(/Грейд [A-E]/)).toHaveCount(0);
    await expect(page.getByText("Что можно улучшить", { exact: true })).toHaveCount(0);
  });
});

test.describe("scenario 7: BKI outage — manual review", () => {
  test("demo panel turns BKI off → application lands in manual review with a note (B7, L4)", async ({
    browser,
  }) => {
    const bank = await personaPage(browser, "Сотрудник банка", /\/bank/);
    const setFailures = async (bki: boolean) => {
      // TODO B7: заменить на UI — /bank/demo is still a placeholder
      const response = await bank.request.put("/api/demo/failures", {
        headers: await csrfHeaders(bank),
        data: { egrul: false, transparent_business: false, bki, bank_account: false },
      });
      expect(response.status()).toBe(200);
      expect((await response.json()).bki).toBe(bki);
    };

    await setFailures(true);
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
        "Бюро кредитных историй сейчас не отвечает — заявку проверит сотрудник. Это не отказ",
      );
      await expect(reasons).toContainText("Грейд B (82 из 100)");
    } finally {
      await setFailures(false);
    }

    await bank.goto("/bank?status=manual_review&search=000100000702&ordering=-status_changed_at");
    const link = bank.getByRole("link", { name: `Заявка №${id}`, exact: true });
    const row = bank.getByRole("row").filter({ has: link });
    await expect(row.getByRole("img", { name: "Источник недоступен" })).toBeVisible();

    await link.click();
    await expect(bank).toHaveURL(new RegExp(`/bank/applications/${id}`));
    await expect(
      bank.getByRole("status").filter({ hasText: "Один из источников не ответил" }),
    ).toContainText("Это не отказ: проверьте вручную.");
    const actions = bank.getByRole("complementary", { name: "Действия сотрудника" });
    for (const action of [
      "Взять в работу",
      "Одобрить",
      "Иные условия",
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
  test.fixme("investment loan without collateral → leasing offer → issued (S6, D15)", async () => {});
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
