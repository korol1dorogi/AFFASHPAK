import { expect, test } from "@playwright/test";

test("landing opens and offers to sign in", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Деньги для бизнеса");
  await expect(page.getByRole("link", { name: "Войти" })).toBeVisible();
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
