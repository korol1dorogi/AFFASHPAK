import { expect, test } from "@playwright/test";

import { personaPage } from "./support";

// XP7: the officer sees the policy in force and recounts the population on other boundaries.
test("the bank sees the credit policy and what a lower C boundary changes (XP7)", async ({
  browser,
}) => {
  const bank = await personaPage(browser, "Сотрудник банка", /\/bank/);
  await bank.getByRole("link", { name: "Кредитная политика" }).click();
  await expect(bank).toHaveURL(/\/bank\/policy$/);
  await expect(bank.getByText(/Действует версия правил 2026\.10-v1/)).toBeVisible();
  await expect(bank.locator("[data-factor='dscr']")).toContainText("от 2 — 25 б.");
  await expect(bank.getByText("При этих порогах грейд не сменит ни одна компания.")).toBeVisible();

  await bank.getByLabel(/Грейд C/).fill("55");
  await bank.getByRole("button", { name: "Пересчитать" }).click();
  await expect(bank.getByText(/^Грейд сменят \d+ из 240 компаний$/)).toBeVisible();
  await expect(bank.getByText(/^D → C: \d+$/)).toBeVisible();
  await bank.screenshot({ path: "test-results/xp7-policy.png", fullPage: true });
});
