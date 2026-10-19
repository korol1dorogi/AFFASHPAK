import { expect, test } from "@playwright/test";

test("cabinet opens and shows backend status", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByText("Кредитный кабинет предпринимателя")).toBeVisible();
  await expect(page.getByTestId("health-status")).toHaveText("Бэкенд работает");
});
