import { fireEvent, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Schemas } from "@/api/client";
import { WizardPage } from "@/features/application-wizard/WizardPage";
import { mockApi, renderRoutes } from "@/test/utils";

const DRAFT: Schemas["ApplicationDetail"] = {
  id: 42,
  company_id: 3,
  need_type: "working_capital",
  purpose: "Закупка к сезону (демо)",
  product_code: null,
  requested_amount: "5300000.00",
  term_months: 12,
  invoice_amount: null,
  collateral_description: null,
  status: "draft",
  version: 1,
  prefill_source: "manual",
  available_actions: ["edit", "submit", "cancel"],
  created_at: "2026-10-22T09:00:00Z",
  submitted_at: null,
  status_changed_at: "2026-10-22T09:00:00Z",
  offer: null,
  open_info_requests: [],
  decision: null,
};

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("WizardPage — review (SRC7)", () => {
  it("the requested amount is the client's word", async () => {
    mockApi({
      "GET /api/applications/42": DRAFT,
      "GET /api/applications/42/documents": [],
      "GET /api/products": [],
      "GET /api/company/members": [],
    });
    renderRoutes(
      [{ path: "/app/applications/:id/edit/:step", element: <WizardPage /> }],
      "/app/applications/42/edit/review",
    );
    const amount = await screen.findByText("5 300 000 ₽");
    expect(amount.parentElement).toHaveTextContent("5 300 000 ₽со слов клиента на 12 мес");
  });
});

describe("WizardPage — the preparer hands the draft to the director (XP5)", () => {
  const AS_PREPARER: Schemas["ApplicationDetail"] = {
    ...DRAFT,
    available_actions: ["edit", "upload_document", "hand_off"],
  };
  const MEMBERS = [
    {
      id: 1,
      user: { id: 10, full_name: "Пётр Демо" },
      role: "signatory",
      position: "Генеральный директор",
    },
  ];

  function open(detail: Schemas["ApplicationDetail"], handOff: unknown = AS_PREPARER) {
    const fetchMock = mockApi({
      "GET /api/applications/42": detail,
      "GET /api/applications/42/documents": [],
      "GET /api/products": [],
      "GET /api/company/members": MEMBERS,
      "POST /api/applications/42/hand-off": handOff,
    });
    renderRoutes(
      [{ path: "/app/applications/:id/edit/:step", element: <WizardPage /> }],
      "/app/applications/42/edit/review",
    );
    return fetchMock;
  }

  const handOffCalls = (fetchMock: ReturnType<typeof mockApi>) =>
    fetchMock.mock.calls.filter(
      ([request]) => new URL((request as Request).url).pathname === "/api/applications/42/hand-off",
    );

  it("no «Отправить в банк», a «Передать директору» button and who will send it", async () => {
    open(AS_PREPARER);
    const button = await screen.findByRole("button", { name: "Передать директору" });
    expect(screen.queryByRole("button", { name: "Отправить в банк" })).not.toBeInTheDocument();
    // The members list arrives after the draft: the name appears a moment later.
    expect(
      await screen.findByText(/Отправить заявку может подписант: Пётр Демо/),
    ).toHaveTextContent("передайте его подписанту: он получит уведомление в кабинете");
    expect(button).toBeEnabled();
  });

  it("hands off and says the signatory was notified; the button stays for a reminder", async () => {
    const fetchMock = open(AS_PREPARER);
    fireEvent.click(await screen.findByRole("button", { name: "Передать директору" }));
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Передано: подписант получил уведомление",
    );
    expect(handOffCalls(fetchMock)).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Передать директору" })).toBeInTheDocument();
  });

  it("an unfinished draft: the field errors from the server, no «передано»", async () => {
    open(AS_PREPARER, [
      400,
      {
        error: {
          code: "validation_error",
          message: "Проверьте поля.",
          details: { product_code: ["Выберите продукт"] },
        },
      },
    ]);
    fireEvent.click(await screen.findByRole("button", { name: "Передать директору" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Выберите продукт");
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("without hand_off in available_actions there is no button", async () => {
    open({ ...DRAFT, available_actions: ["edit", "upload_document"] });
    expect(await screen.findByText(/Отправить заявку может подписант/)).toHaveTextContent(
      "подписант увидит его в своём кабинете",
    );
    expect(screen.queryByRole("button", { name: "Передать директору" })).not.toBeInTheDocument();
  });
});
