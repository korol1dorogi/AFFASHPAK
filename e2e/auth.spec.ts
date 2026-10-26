import { expect, test } from "@playwright/test";

// Sign-in without email or SMS (O5): register, password login, demo personas, logout.
test("a new client registers and is sent to connect the company", async ({ page }) => {
  await page.goto("/register");
  await page.getByLabel("Имя и фамилия").fill("Ирина Демо");
  await page.getByLabel("Логин").fill(`e2e_${Date.now()}`);
  await page.getByLabel("Пароль", { exact: true }).fill("Kofe-2026-demo");
  await page.getByLabel("Повторите пароль").fill("Kofe-2026-demo");
  await page.getByRole("button", { name: "Создать учётную запись" }).click();
  await expect(page).toHaveURL(/\/app\/company\/new$/);
  // Until the company is connected the cabinet has no sections to open.
  await expect(page.getByLabel("ИНН компании или ИП")).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Разделы" })).toHaveCount(0);
});

test("a wrong password shows a plain error", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Логин").fill("nobody");
  await page.getByLabel("Пароль").fill("wrong-password");
  await page.locator("form").getByRole("button", { name: "Войти" }).click();
  await expect(page.getByText("Неверный логин или пароль.")).toBeVisible();
  await expect(page).toHaveURL(/\/login/);
});

test("a bank manager signs in as a demo persona and lands in the bank", async ({ page }) => {
  await page.goto("/login");
  const bank = page.locator("li", { hasText: "Сотрудник банка" });
  await expect(bank.getByText("Рабочее место банка")).toBeVisible();
  await bank.getByRole("button", { name: "Войти" }).click();
  await expect(page).toHaveURL(/\/bank/);
});

test("logout ends the session", async ({ page }) => {
  await page.goto("/login");
  await page
    .locator("li", { hasText: "кофейня «Зерно и пар»" })
    .getByRole("button", { name: "Войти" })
    .click();
  await expect(page).toHaveURL(/\/app$/);
  await page.getByRole("button", { name: "Выйти" }).click();
  await expect(page).toHaveURL(/\/login/);
  await page.goto("/app");
  await expect(page).toHaveURL(/\/login\?next=%2Fapp/);
});
