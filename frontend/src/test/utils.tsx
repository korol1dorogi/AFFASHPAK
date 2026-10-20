import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { createMemoryRouter, type RouteObject, RouterProvider } from "react-router";
import { vi } from "vitest";

type Handler = (request: Request) => unknown;

/** Stub fetch by "METHOD /path" → JSON body (or [status, body]). Unknown routes answer 404. */
export function mockApi(handlers: Record<string, unknown | Handler>) {
  const fetchMock = vi.fn(async (input: Request) => {
    const url = new URL(input.url);
    const key = `${input.method} ${url.pathname}`;
    let reply = handlers[key];
    if (typeof reply === "function") reply = (reply as Handler)(input);
    if (reply === undefined) {
      return new Response(
        JSON.stringify({ error: { code: "not_found", message: "Не найдено." } }),
        {
          status: 404,
          headers: { "Content-Type": "application/json" },
        },
      );
    }
    const [status, body] =
      Array.isArray(reply) && typeof reply[0] === "number" ? reply : [200, reply];
    return new Response(status === 204 ? null : JSON.stringify(body), {
      status: status as number,
      headers: { "Content-Type": "application/json" },
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

export function renderRoutes(routes: RouteObject[], initialPath: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter(routes, { initialEntries: [initialPath] });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

export function renderWithQuery(ui: ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

export const ME_CLIENT = {
  id: 1,
  username: "demo_coffee",
  full_name: "Анна Самойлова",
  kind: "client",
  company_id: 7,
  company_role: "signatory",
  is_demo: true,
} as const;
