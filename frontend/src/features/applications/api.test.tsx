import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useApplication } from "@/features/applications/api";
import { mockApi } from "@/test/utils";

function application(status: string) {
  return {
    id: 1,
    company_id: 7,
    need_type: "cash_gap",
    purpose: "Демо",
    product_code: null,
    requested_amount: "900000.00",
    term_months: 3,
    invoice_amount: null,
    collateral_description: null,
    status,
    version: 1,
    prefill_source: "manual",
    available_actions: [],
    created_at: "2026-10-21T10:00:00Z",
    submitted_at: "2026-10-21T10:00:00Z",
    status_changed_at: "2026-10-21T10:00:00Z",
    offer: null,
    open_info_requests: [],
    decision: null,
  };
}

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

function detailCalls(fetchMock: ReturnType<typeof mockApi>) {
  return fetchMock.mock.calls.filter(([request]) =>
    new URL((request as Request).url).pathname.endsWith("/api/applications/1"),
  ).length;
}

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("useApplication polling (F5: status changes without a reload)", () => {
  it.each(["submitted", "processing"])("re-asks every 3 s while %s", async (status) => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const fetchMock = mockApi({ "GET /api/applications/1": application(status) });
    const { result } = renderHook(() => useApplication(1), { wrapper });
    await waitFor(() => expect(result.current.data?.status).toBe(status));
    expect(detailCalls(fetchMock)).toBe(1);

    await vi.advanceTimersByTimeAsync(3_100);
    await waitFor(() => expect(detailCalls(fetchMock)).toBe(2));
    await vi.advanceTimersByTimeAsync(3_100);
    await waitFor(() => expect(detailCalls(fetchMock)).toBe(3));
  });

  it("slows down to 15 s when the client has to act", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const fetchMock = mockApi({ "GET /api/applications/1": application("offer") });
    const { result } = renderHook(() => useApplication(1), { wrapper });
    await waitFor(() => expect(result.current.data?.status).toBe("offer"));

    await vi.advanceTimersByTimeAsync(3_100);
    expect(detailCalls(fetchMock)).toBe(1);
    await vi.advanceTimersByTimeAsync(12_000);
    await waitFor(() => expect(detailCalls(fetchMock)).toBe(2));
  });
});
