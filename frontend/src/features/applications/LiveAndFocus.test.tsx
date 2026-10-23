import { fireEvent, screen, waitFor } from "@testing-library/react";
import { toast } from "sonner";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Schemas } from "@/api/client";
import { ApplicationPage } from "@/features/applications/ApplicationPage";
import { DocumentUpload } from "@/features/applications/Documents";
import { HomePage } from "@/features/home/HomePage";
import { mockApi, renderRoutes, renderWithQuery } from "@/test/utils";

const BASE: Schemas["ApplicationDetail"] = {
  id: 42,
  company_id: 3,
  need_type: "cash_gap",
  purpose: "Зарплата до поступлений (демо)",
  product_code: null,
  requested_amount: "900000.00",
  term_months: 12,
  invoice_amount: null,
  collateral_description: null,
  status: "manual_review",
  version: 3,
  prefill_source: "manual",
  available_actions: ["cancel"],
  created_at: "2026-10-22T09:00:00Z",
  submitted_at: "2026-10-22T09:05:00Z",
  status_changed_at: "2026-10-22T09:06:00Z",
  offer: null,
  open_info_requests: [],
  decision: null,
};

function renderApplication() {
  renderRoutes(
    [{ path: "/app/applications/:id", element: <ApplicationPage /> }],
    "/app/applications/42",
  );
}

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("application page — live updates and focus (UX2)", () => {
  it("a status changed by the bank comes as a toast (sonner reads it politely)", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const info = vi.spyOn(toast, "info");
    let calls = 0;
    mockApi({
      "GET /api/applications/42": () =>
        ++calls === 1 ? BASE : { ...BASE, status: "declined", available_actions: [] },
      "GET /api/applications/42/events": [],
      "GET /api/applications/42/documents": [],
    });
    renderApplication();
    await screen.findByRole("heading", { level: 1, name: "Заявка № 42" });
    expect(info).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(15_000);
    await waitFor(() => expect(info).toHaveBeenCalledWith("Статус заявки изменился: Отказ"));
  });

  it("closing «Отозвать заявку» with Escape gives focus back to the button", async () => {
    mockApi({
      "GET /api/applications/42": BASE,
      "GET /api/applications/42/events": [],
      "GET /api/applications/42/documents": [],
    });
    renderApplication();
    const button = await screen.findByRole("button", { name: "Отозвать заявку" });
    button.focus();
    fireEvent.click(button);
    const dialog = await screen.findByRole("dialog", { name: "Отозвать заявку?" });
    fireEvent.keyDown(dialog, { key: "Escape" });

    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await waitFor(() => expect(button).toHaveFocus());
  });
});

describe("keyboard and names (UX2)", () => {
  it("the hidden file input is not a separate Tab stop: the button opens it", () => {
    mockApi({});
    renderWithQuery(<DocumentUpload applicationId={42} kinds={["bank_statement"]} />);
    const input = document.querySelector<HTMLInputElement>("input[type=file]");
    expect(input).toHaveAttribute("tabindex", "-1");
    expect(input).toHaveAttribute("aria-hidden", "true");
    expect(screen.getByRole("button", { name: "Выбрать файл" })).toBeInTheDocument();
  });

  it("home: every «Открыть» says which application it opens", async () => {
    mockApi({
      "GET /api/auth/me": {},
      "GET /api/applications": [
        { ...BASE, id: 7, status: "offer" },
        { ...BASE, id: 8, status: "processing" },
      ],
    });
    renderRoutes([{ path: "/app", element: <HomePage /> }], "/app");
    expect(await screen.findByRole("link", { name: "Открыть заявку № 7" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Открыть заявку № 8" })).toBeInTheDocument();
  });
});
