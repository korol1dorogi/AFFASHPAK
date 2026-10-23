import { fireEvent, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Schemas } from "@/api/client";
import { ProductsPage } from "@/features/products/ProductsPage";
import { mockApi, renderRoutes } from "@/test/utils";

const LOAN: Schemas["Product"] = {
  code: "working_capital_loan_basic",
  kind: "working_capital_loan",
  name: "Кредит на пополнение оборотных средств (демо)",
  description: "",
  rate_min: "0.2000",
  rate_max: "0.3000",
  term_min_months: 3,
  term_max_months: 24,
  amount_min: "300000.00",
  amount_max: "30000000.00",
  is_revolving: false,
  collateral_required: false,
  params: {},
  requirements: { min_business_age_months: 6, legal_forms: ["ip", "ooo"] },
  required_documents: [],
};

function render() {
  renderRoutes(
    [
      { path: "/app/products", element: <ProductsPage /> },
      { path: "/app/match", element: <p>Подбор</p> },
    ],
    "/app/products",
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("ProductsPage (UX2)", () => {
  it("an empty catalog says so and leads to the match", async () => {
    mockApi({ "GET /api/products": [] });
    render();
    expect(await screen.findByText("Каталог продуктов пуст")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Подобрать по задаче" }).length).toBeGreaterThan(1);
  });

  it("the calculator says what is wrong under the field instead of a grey button", async () => {
    const fetchMock = mockApi({ "GET /api/products": [LOAN] });
    render();
    const term = await screen.findByLabelText("Срок, мес");
    fireEvent.change(term, { target: { value: "0" } });
    const form = term.closest("form") as HTMLFormElement;
    fireEvent.click(within(form).getByRole("button", { name: "Рассчитать платёж" }));

    expect(term).toHaveAttribute("aria-invalid", "true");
    expect(term).toHaveAccessibleDescription("Срок — целое число месяцев от 1 до 360");
    expect(
      fetchMock.mock.calls.some(
        ([request]) => new URL((request as Request).url).pathname === "/api/calculators/annuity",
      ),
    ).toBe(false);
  });
});
