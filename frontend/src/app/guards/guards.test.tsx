import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RedirectIfAuthed, RequireAuth, RequireCompany, RequireKind } from "@/app/guards";
import { ME_CLIENT, mockApi, renderRoutes } from "@/test/utils";

const tree = [
  { path: "/login", element: <p>Страница входа</p> },
  { path: "/app/company/new", element: <p>Создание компании</p> },
  { path: "/bank", element: <p>Очередь банка</p> },
  {
    element: <RequireAuth />,
    children: [
      {
        element: <RequireKind kind="client" />,
        children: [
          {
            element: <RequireCompany />,
            children: [{ path: "/app/match", element: <p>Подбор</p> }],
          },
        ],
      },
    ],
  },
  {
    element: <RedirectIfAuthed />,
    children: [{ path: "/register", element: <p>Регистрация</p> }],
  },
  { path: "/app", element: <p>Главная клиента</p> },
];

afterEach(() => vi.unstubAllGlobals());

describe("route guards", () => {
  it("sends a visitor without a session to login with ?next", async () => {
    mockApi({ "GET /api/auth/me": [401, { error: { code: "not_authenticated", message: "x" } }] });
    const router = renderRoutes(tree, "/app/match?need=cash_gap");
    expect(await screen.findByText("Страница входа")).toBeInTheDocument();
    expect(router.state.location.search).toBe(
      `?next=${encodeURIComponent("/app/match?need=cash_gap")}`,
    );
  });

  it("lets a client with a company in", async () => {
    mockApi({ "GET /api/auth/me": ME_CLIENT });
    renderRoutes(tree, "/app/match");
    expect(await screen.findByText("Подбор")).toBeInTheDocument();
  });

  it("sends a client without a company to create one", async () => {
    mockApi({ "GET /api/auth/me": { ...ME_CLIENT, company_id: null } });
    renderRoutes(tree, "/app/match");
    expect(await screen.findByText("Создание компании")).toBeInTheDocument();
  });

  it("sends a bank user away from the client cabinet", async () => {
    mockApi({
      "GET /api/auth/me": { ...ME_CLIENT, kind: "bank", company_id: null, company_role: null },
    });
    renderRoutes(tree, "/app/match");
    expect(await screen.findByText("Очередь банка")).toBeInTheDocument();
  });

  it("treats a missing auth API (404) as no session", async () => {
    mockApi({});
    renderRoutes(tree, "/app/match");
    expect(await screen.findByText("Страница входа")).toBeInTheDocument();
  });

  it("sends a signed-in user from /register to their home", async () => {
    mockApi({ "GET /api/auth/me": ME_CLIENT });
    renderRoutes(tree, "/register");
    expect(await screen.findByText("Главная клиента")).toBeInTheDocument();
  });
});
