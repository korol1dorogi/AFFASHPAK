import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { HealthPage } from "./HealthPage";

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <HealthPage />
    </QueryClientProvider>,
  );
}

function stubFetch(status: number, body: unknown) {
  const fetchMock = vi.fn(
    async () =>
      new Response(JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("HealthPage", () => {
  it("shows that the backend works", async () => {
    const fetchMock = stubFetch(200, { status: "ok", database: "ok" });

    renderPage();

    expect(await screen.findByText("Бэкенд работает")).toBeInTheDocument();
    const request = fetchMock.mock.calls[0] as unknown as [Request];
    expect(new URL(request[0].url).pathname).toBe("/api/health");
  });

  it("shows database outage from a 503 response", async () => {
    stubFetch(503, { status: "degraded", database: "unavailable" });

    renderPage();

    expect(await screen.findByText("База данных недоступна")).toBeInTheDocument();
  });

  it("shows that the API is unreachable", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("network down");
      }),
    );

    renderPage();

    expect(await screen.findByText("API недоступен")).toBeInTheDocument();
  });
});
