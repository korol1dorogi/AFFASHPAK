import { expect, test } from "@playwright/test";

test("landing explains the product and signs in as a persona in one click (UX1)", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Деньги для бизнеса");
  await expect(page.getByRole("link", { name: "Войти по логину" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Как получить деньги: три шага" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Банк работает с той же заявкой" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Контракт API (Swagger)" })).toHaveAttribute(
    "href",
    "/api/docs/",
  );

  await page.getByRole("link", { name: "Войти за демо-компанию" }).click();
  const personas = page.getByRole("list", { name: "Попробуйте от имени демо-компании" });
  await expect(personas).toContainText("Кассовый разрыв. Овердрафт на 900 000 ₽");
  await personas.getByRole("button", { name: /^Войти: ИП Лаврова/ }).click();
  await expect(page).toHaveURL(/\/app$/);
});

test("status page shows that the backend works", async ({ page }) => {
  await page.goto("/status");
  await expect(page.getByTestId("health-status")).toHaveText("Бэкенд работает");
});

test("the cabinet sends a visitor without a session to sign in", async ({ page }) => {
  await page.goto("/app/match");
  await expect(page).toHaveURL(/\/login\?next=%2Fapp%2Fmatch/);
  await expect(page.getByRole("heading", { name: "Вход", exact: true })).toBeVisible();
});
