import { expect, test } from "@playwright/test";

import { personaPage } from "./support";

// XP4: the demo queue always has manual reviews older than the 24 h norm
// (apps/accounts/demo_queue.py spreads time in status over 0–60 h).
test("the bank sees overdue applications marked in the queue and on the dashboard (XP4)", async ({
  browser,
}) => {
  const bank = await personaPage(browser, "Сотрудник банка", /\/bank/);

  await bank.goto("/bank?overdue=1");
  await expect(bank.getByRole("checkbox", { name: "Только просроченные" })).toBeChecked();
  const rows = bank.locator("tbody tr[data-overdue]");
  await expect(rows.first()).toBeVisible();
  await expect(rows.first()).toContainText(/просрочено (на \d+ ч|, меньше часа)/);
  await expect(bank.locator("tbody tr:not([data-overdue])")).toHaveCount(0);
  await bank.screenshot({ path: "test-results/xp4-overdue-queue.png", fullPage: true });

  await bank.getByRole("link", { name: "Сводка" }).click();
  await expect(bank).toHaveURL(/\/bank\/dashboard$/);
  await expect(bank.getByRole("heading", { name: "Сводка", level: 1 })).toBeVisible();
  // The period's applications by their current status: in work (by who has to act) and results.
  const work = bank.getByLabel("В работе сейчас");
  for (const group of ["Ждут банк", "Ждут клиента", "Выдача денег"]) {
    await expect(work.getByRole("region", { name: group })).toBeVisible();
  }
  await expect(work.locator('li[data-row="manual_review"]')).toContainText(
    /Смотрит сотрудник банка\d+/,
  );
  const results = bank.getByLabel("Итоги за период");
  await expect(results.locator('li[data-row="issued"]')).toContainText(
    /Деньги выданы\d+(\d+|меньше 1) %/,
  );

  const card = bank.getByLabel("Просрочено по нормативу");
  await expect(card).toContainText(/\d+ из \d+/);
  await expect(card).toContainText("У сотрудника банка — 24 ч");
  await card.getByRole("link", { name: "Показать просроченные в очереди" }).click();
  await expect(bank).toHaveURL(/\/bank\?overdue=1$/);
});
