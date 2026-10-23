import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Schemas } from "@/api/client";
import { WizardPage } from "@/features/application-wizard/WizardPage";
import { ApplicationPage } from "@/features/applications/ApplicationPage";
import { mockApi, renderRoutes } from "@/test/utils";

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
  available_actions: [],
  created_at: "2026-10-22T09:00:00Z",
  submitted_at: "2026-10-22T09:05:00Z",
  status_changed_at: "2026-10-22T09:06:00Z",
  offer: null,
  open_info_requests: [],
  decision: null,
};

const FAIL = [500, { error: { code: "server_error", message: "Сервер прилёг (демо)" } }];

function renderApplication() {
  renderRoutes(
    [{ path: "/app/applications/:id", element: <ApplicationPage /> }],
    "/app/applications/42",
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("application page — history and documents never pretend (UX2)", () => {
  it("a failed history says so and retries, instead of «Загружаем…» forever", async () => {
    let calls = 0;
    mockApi({
      "GET /api/applications/42": BASE,
      "GET /api/applications/42/documents": [],
      "GET /api/applications/42/events": () => (++calls === 1 ? FAIL : []),
    });
    renderApplication();

    expect(await screen.findByText("Не получилось загрузить историю.")).toBeInTheDocument();
    expect(screen.getByText("Сервер прилёг (демо)")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Повторить" }));
    expect(await screen.findByText(/Событий пока нет/)).toBeInTheDocument();
  });

  it("documents: a failed list is an error, not «Документов пока нет»", async () => {
    mockApi({
      "GET /api/applications/42": BASE,
      "GET /api/applications/42/events": [],
      "GET /api/applications/42/documents": FAIL,
    });
    renderApplication();

    expect(await screen.findByText("Не получилось загрузить документы.")).toBeInTheDocument();
    expect(screen.queryByText("Документов пока нет.")).not.toBeInTheDocument();
    expect(
      screen.getByText("Не получилось загрузить документы.").closest("[role=alert]"),
    ).not.toBeNull();
  });

  it("documents: while loading — a skeleton, then the empty text", async () => {
    let release: () => void = () => undefined;
    const pending = new Promise<void>((resolve) => {
      release = resolve;
    });
    mockApi({
      "GET /api/applications/42": BASE,
      "GET /api/applications/42/events": [],
      "GET /api/applications/42/documents": [],
    });
    const fetchMock = vi.mocked(fetch);
    const answer = fetchMock.getMockImplementation();
    fetchMock.mockImplementation(async (input) => {
      if (new URL((input as Request).url).pathname.endsWith("/documents")) await pending;
      return answer?.(input as Request) as Promise<Response>;
    });
    renderApplication();

    expect(await screen.findByRole("status", { name: "Загружаем документы" })).toBeInTheDocument();
    expect(screen.queryByText("Документов пока нет.")).not.toBeInTheDocument();
    release();
    expect(await screen.findByText("Документов пока нет.")).toBeInTheDocument();
  });
});

describe("wizard «О бизнесе» — loading is not «профиль не заполнен» (UX2)", () => {
  it("shows a skeleton while the company loads and an error with retry for metrics", async () => {
    let releaseCompany: () => void = () => undefined;
    const companyPending = new Promise<void>((resolve) => {
      releaseCompany = resolve;
    });
    mockApi({
      "GET /api/applications/42": { ...BASE, status: "draft", available_actions: ["edit"] },
      "GET /api/company": {},
      "GET /api/company/metrics": FAIL,
    });
    const fetchMock = vi.mocked(fetch);
    const answer = fetchMock.getMockImplementation();
    fetchMock.mockImplementation(async (input) => {
      if (new URL((input as Request).url).pathname === "/api/company") await companyPending;
      return answer?.(input as Request) as Promise<Response>;
    });
    renderRoutes(
      [{ path: "/app/applications/:id/edit/:step", element: <WizardPage /> }],
      "/app/applications/42/edit/business",
    );

    expect(
      await screen.findByRole("status", { name: "Загружаем данные компании" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Профиль компании ещё не заполнен.")).not.toBeInTheDocument();
    expect(
      await screen.findByText("Не получилось загрузить показатели по счёту."),
    ).toBeInTheDocument();
    releaseCompany();
    await waitFor(() =>
      expect(
        screen.queryByRole("status", { name: "Загружаем данные компании" }),
      ).not.toBeInTheDocument(),
    );
  });
});
