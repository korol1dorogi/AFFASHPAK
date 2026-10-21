import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CompanyNewPage } from "@/features/company/CompanyNewPage";
import { company, me, registryRecord } from "@/features/company/fixtures";
import { mockApi, renderRoutes } from "@/test/utils";

const LOOKUP = "GET /api/company/lookup";
const NEW_CLIENT = { "GET /api/auth/me": me({ company_id: null, company_role: null }) };

function open(handlers: Record<string, unknown>) {
  const fetchMock = mockApi({ ...NEW_CLIENT, ...handlers });
  renderRoutes(
    [
      { path: "/app/company/new", element: <CompanyNewPage /> },
      { path: "/app", element: <p>Главная</p> },
      { path: "/app/company", element: <p>Профиль компании</p> },
    ],
    "/app/company/new",
  );
  return fetchMock;
}

function calls(fetchMock: ReturnType<typeof mockApi>, method: string, path: string) {
  return fetchMock.mock.calls
    .map(([request]) => request as Request)
    .filter((request) => request.method === method && new URL(request.url).pathname === path);
}

async function find(inn: string) {
  fireEvent.change(await screen.findByLabelText("ИНН компании или ИП"), {
    target: { value: inn },
  });
  fireEvent.click(screen.getByRole("button", { name: "Найти в реестре" }));
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("CompanyNewPage — INN → registry → company", () => {
  it("checks the INN format before asking the registry", async () => {
    const fetchMock = open({ [LOOKUP]: registryRecord() });
    await find("12345");
    expect(await screen.findByText("ИНН — 10 цифр у компании или 12 у ИП")).toBeInTheDocument();
    expect(screen.getByLabelText("ИНН компании или ИП")).toHaveAttribute("aria-invalid", "true");
    expect(calls(fetchMock, "GET", "/api/company/lookup")).toHaveLength(0);
  });

  it("shows the registry record and creates the company from the INN alone", async () => {
    const fetchMock = open({ [LOOKUP]: registryRecord(), "POST /api/company": [201, company()] });
    await find("0001000042");

    expect(await screen.findByText("Нашли в реестре")).toBeInTheDocument();
    expect(screen.getByText("ООО «Дубрава Мебель» (демо)")).toBeInTheDocument();
    expect(screen.getByText("31.09 — Производство прочей мебели")).toBeInTheDocument();
    expect(screen.getByText("1260000000042")).toBeInTheDocument();
    expect(screen.getByText("Действует")).toBeInTheDocument();
    expect(screen.queryByText(/кредит не выдадут/)).not.toBeInTheDocument();
    const [lookup] = calls(fetchMock, "GET", "/api/company/lookup");
    expect(new URL((lookup as Request).url).searchParams.get("inn")).toBe("0001000042");

    fireEvent.click(screen.getByRole("button", { name: "Это моя компания" }));
    expect(await screen.findByText("Главная")).toBeInTheDocument();
    const [created] = calls(fetchMock, "POST", "/api/company");
    expect(await (created as Request).clone().json()).toEqual({ inn: "0001000042" });
  });

  it("warns that a liquidating company gets no loan, but still lets it be connected", async () => {
    open({ [LOOKUP]: registryRecord({ registry_status: "liquidating" }) });
    await find("0001000042");
    expect(await screen.findByText("В процессе ликвидации")).toBeInTheDocument();
    expect(screen.getByText(/кредит не выдадут/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Это моя компания" })).toBeEnabled();
  });

  it("not in the registry: the message lands under the INN field", async () => {
    open({
      [LOOKUP]: [
        404,
        { error: { code: "not_found", message: "Не нашли компанию с таким ИНН в реестре." } },
      ],
    });
    await find("0009999999");
    expect(await screen.findByText("Не нашли компанию с таким ИНН в реестре.")).toBeInTheDocument();
    expect(screen.getByLabelText("ИНН компании или ИП")).toHaveAttribute("aria-invalid", "true");
    expect(screen.queryByText("Нашли в реестре")).not.toBeInTheDocument();
  });

  it("registry down: says so and retries", async () => {
    let attempts = 0;
    open({
      [LOOKUP]: () => {
        attempts += 1;
        return attempts === 1
          ? [
              503,
              {
                error: {
                  code: "source_unavailable",
                  message: "Реестр временно недоступен. Попробуйте позже.",
                },
              },
            ]
          : registryRecord();
      },
    });
    await find("0001000042");
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Реестр временно недоступен. Попробуйте позже.",
    );
    fireEvent.click(screen.getByRole("button", { name: "Повторить" }));
    expect(await screen.findByText("Нашли в реестре")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("company already taken: the API's message, no navigation", async () => {
    open({
      [LOOKUP]: registryRecord(),
      "POST /api/company": [
        409,
        {
          error: {
            code: "company_taken",
            message: "Эту компанию уже подключил другой пользователь.",
          },
        },
      ],
    });
    await find("0001000042");
    fireEvent.click(await screen.findByRole("button", { name: "Это моя компания" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Эту компанию уже подключил другой пользователь.",
    );
    expect(screen.queryByText("Главная")).not.toBeInTheDocument();
  });

  it("another INN clears the found record", async () => {
    open({ [LOOKUP]: registryRecord() });
    await find("0001000042");
    fireEvent.click(await screen.findByRole("button", { name: "Другой ИНН" }));
    await waitFor(() => expect(screen.queryByText("Нашли в реестре")).not.toBeInTheDocument());
    expect(screen.getByLabelText("ИНН компании или ИП")).toHaveValue("");
  });

  it("a client who already has a company goes to the profile", async () => {
    mockApi({ "GET /api/auth/me": me() });
    renderRoutes(
      [
        { path: "/app/company/new", element: <CompanyNewPage /> },
        { path: "/app/company", element: <p>Профиль компании</p> },
      ],
      "/app/company/new",
    );
    expect(await screen.findByText("Профиль компании")).toBeInTheDocument();
  });
});
