import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { type Browser, expect, type Page } from "@playwright/test";

/** Quick sign-in as a seeded demo persona (DEMO_MODE=1, docs/openapi.yaml `demo`). */
export async function signInAs(page: Page, title: RegExp | string) {
  await page.goto("/login");
  await page.locator("li", { hasText: title }).getByRole("button", { name: "Войти" }).click();
}

/** A fresh page signed in as the persona, in its own browser context (its own session). */
export async function personaPage(browser: Browser, title: RegExp | string, landing: RegExp) {
  const page = await (await browser.newContext()).newPage();
  await signInAs(page, title);
  await expect(page).toHaveURL(landing);
  return page;
}

/** Unsafe API calls from the page's session need the CSRF cookie echoed in a header. */
export async function csrfHeaders(page: Page) {
  const cookies = await page.context().cookies();
  const token = cookies.find((cookie) => cookie.name === "csrftoken")?.value ?? "";
  return { "X-CSRFToken": token };
}

/** Money as the interface prints it: "2 009 314 ₽", thousands split by a no-break space. */
export function rub(amount: string) {
  return `${amount.replace(/ /g, " ")} ₽`;
}

export type DocumentKind = "bank_statement" | "tax_return" | "contract" | "invoice" | "financial_report";

/** Demo PDF stubs with a DEMO watermark (S9, data/sample/documents). */
export function demoPdf(kind: DocumentKind) {
  const path = new URL(`../data/sample/documents/${kind}_0001000042_demo.pdf`, import.meta.url);
  return { name: `${kind}_demo.pdf`, mimeType: "application/pdf", buffer: readFileSync(fileURLToPath(path)) };
}

export interface Draft {
  need_type: string;
  product_code: string;
  purpose: string;
  requested_amount: string;
  term_months: number;
  collateral_description?: string;
}

/**
 * The persona's draft from the scenario's preconditions (docs/test-scenarios.md): seed_demo does
 * not seed drafts, so each test makes its own and stays independent of the others and of reruns.
 */
export async function createDraft(page: Page, draft: Draft, documents: DocumentKind[] = []) {
  const created = await page.request.post("/api/applications", {
    headers: await csrfHeaders(page),
    data: draft,
  });
  expect(created.status()).toBe(201);
  const { id } = (await created.json()) as { id: number };
  for (const kind of documents) {
    const uploaded = await page.request.post(`/api/applications/${id}/documents`, {
      headers: await csrfHeaders(page),
      multipart: { kind, file: demoPdf(kind) },
    });
    expect(uploaded.status()).toBe(201);
  }
  return id;
}

/**
 * «Подписание и выдача» (docs/test-scenarios.md, П-1…П-5): accept the offer, sign with the code
 * shown on screen (O5) and wait for the simulated disbursement.
 */
export async function acceptAndSign(page: Page, id: number) {
  await page.getByRole("button", { name: "Принять и подписать" }).click();
  await expect(page).toHaveURL(new RegExp(`/app/applications/${id}/sign$`));
  await page.getByRole("button", { name: "Показать код" }).click();
  const shown = await page.getByRole("img", { name: /^Код \d( \d){5}$/ }).getAttribute("aria-label");
  const code = (shown ?? "").replace(/\D/g, "");
  await page.getByLabel("Введите код").fill(code);
  await page.getByRole("button", { name: "Подписать", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/app/applications/${id}$`));
  await expect(page.locator("[data-status]").first()).toHaveText("Деньги выданы");
}

/** The client sends the draft from the wizard's last step, as a person does. */
export async function submitFromWizard(page: Page, id: number) {
  await page.goto(`/app/applications/${id}/edit/review`);
  await page.getByRole("button", { name: "Отправить в банк" }).click();
  await expect(page).toHaveURL(new RegExp(`/app/applications/${id}$`));
}
