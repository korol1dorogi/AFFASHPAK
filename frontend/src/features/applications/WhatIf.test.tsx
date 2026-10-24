import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Schemas } from "@/api/client";
import { ApplicationPage } from "@/features/applications/ApplicationPage";
import { showsWhatIf } from "@/features/applications/WhatIf";
import { renderRoutes } from "@/test/utils";

type Offer = Schemas["Offer"];
type Detail = Schemas["ApplicationDetail"];

/** Persona 3 (демо): КПО, asked 5.3 mln for 12 months, counteroffer by DSCR (scenario 3). */
const PRODUCT: Schemas["Product"] = {
  code: "working_capital_loan_basic",
  kind: "working_capital_loan",
  name: "Кредит на пополнение оборотных средств (демо)",
  description: "Закупка к сезону",
  rate_min: "0.1900",
  rate_max: "0.2800",
  term_min_months: 3,
  term_max_months: 24,
  amount_min: "300000.00",
  amount_max: "30000000.00",
  is_revolving: false,
  collateral_required: false,
  params: { min_dscr: "1.25" },
  requirements: { min_business_age_months: 12, legal_forms: ["ip", "ooo"] },
  required_documents: ["bank_statement", "tax_return"],
};

function offer(changes: Partial<Offer> = {}): Offer {
  return {
    id: 5,
    product: PRODUCT,
    amount: "2009314.00",
    requested_amount: "5300000.00",
    term_months: 12,
    rate: "0.2400",
    monthly_payment: "189999.92",
    is_counteroffer: true,
    product_changed: false,
    status: "active",
    expires_at: "2026-10-29T12:00:00Z",
    reasons: [],
    ...changes,
  };
}

function detail(changes: Partial<Detail> = {}): Detail {
  return {
    id: 42,
    company_id: 3,
    need_type: "working_capital",
    purpose: "Закупка к сезону (демо)",
    product_code: "working_capital_loan_basic",
    requested_amount: "5300000.00",
    term_months: 12,
    invoice_amount: null,
    collateral_description: null,
    status: "offer",
    version: 4,
    prefill_source: "recommendation",
    available_actions: ["accept_offer", "decline_offer", "cancel"],
    created_at: "2026-10-22T09:00:00Z",
    submitted_at: "2026-10-22T09:05:00Z",
    status_changed_at: "2026-10-22T09:06:00Z",
    offer: offer(),
    open_info_requests: [],
    decision: null,
    ...changes,
  };
}

/** What the backend allows for persona 3 at 24 % (credit_math max_loan_by_dscr), by term. */
const LIMIT: Record<number, string> = { 12: "2009314.00", 18: "2848485.00", 24: "3593645.00" };
const PAYMENT: Record<number, string> = { 12: "189999.92", 18: "189999.94", 24: "189999.95" };

type WhatIfBody = { amount: string; term_months: number };

/** Answers like the backend: within the limit → fits; the limit and payment by term. */
function answer({ amount, term_months }: WhatIfBody): Schemas["WhatIfResult"] {
  const limit = LIMIT[term_months] ?? "1000000.00";
  const fits = Number(amount) <= Number(limit); // test data only: the product never does this
  return {
    amount,
    term_months,
    rate: "0.2400",
    monthly_payment: PAYMENT[term_months] ?? "100000.00",
    max_amount: limit,
    dscr_after: fits ? "1.2600" : "1.0500",
    min_dscr: "1.25",
    fits,
    reasons: [
      {
        metric: "max_loan_by_dscr",
        value: limit,
        threshold: amount,
        passed: fits,
        message: fits ? "Платёж посилен" : "Чтобы платежи не съели запас 25 %, сумма ограничена",
      },
    ],
  };
}

/** fetch stub: the page's GETs, and the what-if POST answered from its body. */
function stubApi(
  page: Detail,
  whatIf: (body: WhatIfBody) => [number, unknown] = (body) => [200, answer(body)],
) {
  const sent: WhatIfBody[] = [];
  const json = (status: number, body: unknown) =>
    new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  vi.stubGlobal(
    "fetch",
    vi.fn(async (request: Request) => {
      const path = new URL(request.url).pathname;
      if (request.method === "POST" && path === "/api/applications/42/what-if") {
        const body = (await request.clone().json()) as WhatIfBody;
        sent.push(body);
        return json(...whatIf(body));
      }
      const pages: Record<string, unknown> = {
        "/api/applications/42": page,
        "/api/applications/42/events": [],
        "/api/applications/42/documents": [],
        "/api/products": [PRODUCT],
      };
      return path in pages
        ? json(200, pages[path])
        : json(404, { error: { code: "not_found", message: "Не найдено." } });
    }),
  );
  return sent;
}

function open() {
  renderRoutes(
    [{ path: "/app/applications/:id", element: <ApplicationPage /> }],
    "/app/applications/42",
  );
}

const region = () => screen.findByRole("region", { name: "Что если" });

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("WhatIf — who sees it", () => {
  it("only under an active fixed-payment offer whose amount or product changed", () => {
    expect(showsWhatIf(detail())).toBe(true);
    expect(
      showsWhatIf(detail({ offer: offer({ is_counteroffer: false, product_changed: true }) })),
    ).toBe(true);
    expect(showsWhatIf(detail({ offer: offer({ is_counteroffer: false }) }))).toBe(false);
    expect(
      showsWhatIf(
        detail({
          offer: offer({ product: { ...PRODUCT, kind: "overdraft", is_revolving: true } }),
        }),
      ),
    ).toBe(false);
    expect(showsWhatIf(detail({ status: "signing", offer: offer({ status: "accepted" }) }))).toBe(
      false,
    );
    expect(showsWhatIf(detail({ offer: null }))).toBe(false);
  });

  it("is not on the page for a revolving offer", async () => {
    stubApi(
      detail({ offer: offer({ product: { ...PRODUCT, kind: "overdraft", is_revolving: true } }) }),
    );
    open();
    expect(await screen.findByRole("article", { name: "Предложение банка" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Что если" })).not.toBeInTheDocument();
  });
});

describe("WhatIf — the calculation comes from the backend", () => {
  it("starts from the offer's terms", async () => {
    const sent = stubApi(detail());
    open();
    const block = await region();
    expect(await within(block).findByText("Такие условия прошли бы")).toBeInTheDocument();
    expect(sent[0]).toEqual({ amount: "2009314.00", term_months: 12 });
    expect(within(block).getByText("Можно взять на 12 мес")).toBeInTheDocument();
    expect(within(block).getByText(/189\s999,92\s₽/)).toBeInTheDocument();
    // Both amounts are counted by the bank (SRC7).
    expect(within(block).getByText(/189\s999,92\s₽/).parentElement).toHaveTextContent("расчёт");
    expect(within(block).getByText("Можно взять на 12 мес").nextElementSibling).toHaveTextContent(
      /₽расчёт$/,
    );
    expect(within(block).getByText("1,26, нужно не меньше 1,25")).toBeInTheDocument();
    expect(within(block).getByRole("slider", { name: "Срок" })).toHaveAttribute("min", "3");
    expect(within(block).getByRole("slider", { name: "Срок" })).toHaveAttribute("max", "24");
  });

  it("persona 3: 18 months shows the new allowed amount", async () => {
    const sent = stubApi(detail());
    open();
    const block = await region();
    await within(block).findByText("Можно взять на 12 мес");

    fireEvent.change(within(block).getByRole("slider", { name: "Срок" }), {
      target: { value: "18" },
    });

    expect(await within(block).findByText("Можно взять на 18 мес")).toBeInTheDocument();
    expect(within(block).getByText(/2\s848\s485\s₽/)).toBeInTheDocument();
    expect(sent.at(-1)).toEqual({ amount: "2009314.00", term_months: 18 });
  });

  it("the answer for the old terms is marked busy until the new one arrives", async () => {
    stubApi(detail());
    open();
    const block = await region();
    const results = (await within(block).findByText("Можно взять на 12 мес")).closest(
      "[aria-live]",
    ) as HTMLElement;
    expect(results).not.toHaveAttribute("aria-busy");

    fireEvent.change(within(block).getByRole("slider", { name: "Срок" }), {
      target: { value: "18" },
    });
    expect(results).toHaveAttribute("aria-busy", "true"); // the slider says 18, the answer 12

    await within(block).findByText("Можно взять на 18 мес");
    await waitFor(() => expect(results).not.toHaveAttribute("aria-busy"));
  });

  it("waits for the slider to stop: one request for a quick run of changes", async () => {
    const sent = stubApi(detail());
    open();
    const block = await region();
    await within(block).findByText("Можно взять на 12 мес");
    const term = within(block).getByRole("slider", { name: "Срок" });
    for (const value of ["13", "15", "18"]) fireEvent.change(term, { target: { value } });

    await within(block).findByText("Можно взять на 18 мес");
    expect(sent.map((body) => body.term_months)).toEqual([12, 18]);
  });

  it("the amount slider sends whole rubles; the exact field sends the typed amount", async () => {
    const sent = stubApi(detail());
    open();
    const block = await region();
    await within(block).findByText("Можно взять на 12 мес");

    fireEvent.change(within(block).getByRole("slider", { name: "Сумма" }), {
      target: { value: "1500000" },
    });
    await waitFor(() => expect(sent.at(-1)).toEqual({ amount: "1500000.00", term_months: 12 }));

    fireEvent.change(within(block).getByLabelText("Сумма точно, ₽"), {
      target: { value: "3 000 000" },
    });
    await waitFor(() => expect(sent.at(-1)).toEqual({ amount: "3000000.00", term_months: 12 }));
  });

  it("more than allowed: «не пройдут» with only the failed reasons", async () => {
    stubApi(detail());
    open();
    const block = await region();
    await within(block).findByText("Можно взять на 12 мес");
    fireEvent.change(within(block).getByLabelText("Сумма точно, ₽"), {
      target: { value: "3 000 000" },
    });

    expect(await within(block).findByText("Такие условия не пройдут")).toBeInTheDocument();
    const why = within(block).getByRole("list", { name: "Почему" });
    expect(within(why).getAllByRole("listitem")).toHaveLength(1);
    expect(why).toHaveTextContent("сумма ограничена");
  });

  it("no limit from the backend: says it cannot be counted, never 0", async () => {
    stubApi(detail(), (body) => [
      200,
      { ...answer(body), max_amount: null, dscr_after: null, fits: false },
    ]);
    open();
    const block = await region();
    expect(await within(block).findAllByText("Не получается посчитать")).toHaveLength(2);
  });

  it("an error answer is shown as text", async () => {
    stubApi(detail(), () => [
      409,
      {
        error: {
          code: "no_active_offer",
          message: "Посчитать другие условия можно, пока предложение банка действует.",
        },
      },
    ]);
    open();
    const block = await region();
    expect(await within(block).findByRole("alert")).toHaveTextContent(
      "Посчитать другие условия можно, пока предложение банка действует.",
    );
  });
});
