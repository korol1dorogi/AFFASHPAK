import { expect, test } from "@playwright/test";

import { createDraft, NBSP, signInAs } from "./support";

// UX5 (C5 tail, F12): the wizard saves the draft by itself — a reload or a closed tab loses nothing.
test("the draft survives a page reload and a trip through the steps (C5)", async ({ page }) => {
  await signInAs(page, "кофейня «Зерно и пар»");
  await expect(page).toHaveURL(/\/app$/);
  const id = await createDraft(page, {
    need_type: "cash_gap",
    product_code: "overdraft_basic",
    purpose: "Демо: зарплата до поступлений",
    requested_amount: "500000.00",
    term_months: 6,
  });

  await page.goto(`/app/applications/${id}/edit/params`);
  const amount = page.getByLabel("Сумма", { exact: true });
  const term = page.getByLabel("Срок, месяцев");
  const purpose = page.getByLabel("На что нужны деньги");
  const product = page.getByLabel("Продукт");
  await expect(amount).toHaveValue(`500${NBSP}000`);
  // the catalog loads after the draft: the select must still show the draft's product
  await expect(product).toHaveValue("overdraft_basic");

  await amount.fill("750000");
  await term.fill("9");
  await purpose.fill("Демо: аренда и зарплата до оплаты от сети");
  await expect(page.getByText(/^Сохранено · /)).toBeVisible();

  await page.reload();
  await expect(amount).toHaveValue(`750${NBSP}000`);
  await expect(product).toHaveValue("overdraft_basic");
  await expect(term).toHaveValue("9");
  await expect(purpose).toHaveValue("Демо: аренда и зарплата до оплаты от сети");

  // Away to another step and back: still the same, and still a draft the bank does not see.
  await page.goto(`/app/applications/${id}/edit/review`);
  await expect(page.getByText("Демо: аренда и зарплата до оплаты от сети")).toBeVisible();
  await page.goto(`/app/applications/${id}/edit/params`);
  await expect(amount).toHaveValue(`750${NBSP}000`);

  const saved = await page.request.get(`/api/applications/${id}`);
  const body = (await saved.json()) as Record<string, unknown>;
  expect(body).toMatchObject({
    status: "draft",
    product_code: "overdraft_basic",
    requested_amount: "750000.00",
    term_months: 9,
    purpose: "Демо: аренда и зарплата до оплаты от сети",
  });
});
