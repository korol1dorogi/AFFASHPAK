import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RequireAuth } from "@/app/guards";
import { BankLayout, ClientLayout } from "@/app/layouts";
import { ME_CLIENT, mockApi, renderRoutes } from "@/test/utils";

// As in the router: the layout renders only after RequireAuth has loaded `me`.
const tree = [
  {
    element: <RequireAuth />,
    children: [
      {
        element: <ClientLayout />,
        children: [
          { path: "/app", element: <p>Главная клиента</p> },
          { path: "/app/company/new", element: <p>Подключение компании</p> },
        ],
      },
      {
        element: <BankLayout />,
        children: [{ path: "/bank", element: <p>Очередь банка</p> }],
      },
    ],
  },
];

afterEach(() => vi.unstubAllGlobals());

describe("layouts", () => {
  it("shows the sections to a client with a company", async () => {
    mockApi({ "GET /api/auth/me": ME_CLIENT });
    renderRoutes(tree, "/app");
    expect(await screen.findByText("Главная клиента")).toBeInTheDocument();
    const sections = screen.getByRole("navigation", { name: "Разделы" });
    expect(sections).toHaveTextContent("Подобрать финансирование");
  });

  it("shows no sections until the client has a company", async () => {
    mockApi({ "GET /api/auth/me": { ...ME_CLIENT, company_id: null, company_role: null } });
    renderRoutes(tree, "/app/company/new");
    expect(await screen.findByText("Подключение компании")).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Разделы" })).toBeNull();
    expect(screen.getByRole("button", { name: "Выйти" })).toBeInTheDocument();
  });

  it("keeps the sections of the bank", async () => {
    mockApi({
      "GET /api/auth/me": { ...ME_CLIENT, kind: "bank", company_id: null, company_role: null },
    });
    renderRoutes(tree, "/bank");
    expect(await screen.findByText("Очередь банка")).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Разделы" })).toHaveTextContent("Очередь");
  });
});
