import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Schemas } from "@/api/client";
import { CompanyPage } from "@/features/company/CompanyPage";
import { company, me, members } from "@/features/company/fixtures";
import { mockApi, renderRoutes } from "@/test/utils";

function open(handlers: Record<string, unknown> = {}, role: Schemas["MemberRole"] = "signatory") {
  const fetchMock = mockApi({
    "GET /api/auth/me": me({ company_role: role }),
    "GET /api/company": company({ my_role: role }),
    "GET /api/company/members": members,
    "GET /api/company/invitations": [],
    ...handlers,
  });
  renderRoutes(
    [
      { path: "/app/company", element: <CompanyPage /> },
      { path: "/app/company/new", element: <p>Подключение компании</p> },
    ],
    "/app/company",
  );
  return fetchMock;
}

function sent(fetchMock: ReturnType<typeof mockApi>, method: string, path: string) {
  const requests = fetchMock.mock.calls
    .map(([request]) => request as Request)
    .filter((request) => request.method === method && new URL(request.url).pathname === path);
  return Promise.all(requests.map((request) => request.clone().text()));
}

const memberList = () => screen.findByRole("list", { name: "Сотрудники и роли" });

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("CompanyPage — requisites", () => {
  it("shows requisites from the registry, read-only", async () => {
    open();
    expect(
      await screen.findByRole("heading", { level: 1, name: "ООО «Дубрава Мебель» (демо)" }),
    ).toBeInTheDocument();
    expect(screen.getByText("ООО · ИНН 0001000042")).toBeInTheDocument();
    expect(screen.getByText("из ЕГРЮЛ")).toBeInTheDocument();
    expect(screen.getByText("1260000000042")).toBeInTheDocument();
    expect(screen.getByText("г. Демо, ул. Примерная, 4")).toBeInTheDocument();
    expect(screen.getByText("Пётр Демо", { selector: "dd" })).toBeInTheDocument();
    // The legal name is a registry requisite; the short name is a separate field (short_name).
    expect(screen.getByText("Название", { selector: "dt" })).toBeInTheDocument();
    expect(screen.getByText("ООО «Дубрава Мебель» (демо)", { selector: "dd" })).toBeInTheDocument();
    // The only fields are the short name and the new member: requisites are never typed in.
    await memberList();
    expect(screen.getAllByRole("textbox").map((field) => field.getAttribute("name"))).toEqual([
      "short_name",
      "username",
      "position",
    ]);
  });

  it("a company in liquidation carries the warning", async () => {
    open({ "GET /api/company": company({ registry_status: "liquidating" }) });
    expect(await screen.findByText(/кредит не выдадут/)).toBeInTheDocument();
  });

  it("a client without a company goes to connect one", async () => {
    open({
      "GET /api/company": [404, { error: { code: "not_found", message: "Не найдено." } }],
    });
    expect(await screen.findByText("Подключение компании")).toBeInTheDocument();
  });

  it("signatory sets a short name: PATCH {short_name}, the header follows, the legal name stays", async () => {
    const fetchMock = open({
      "PATCH /api/company": company({ short_name: "Дубрава" }),
    });
    const field = await screen.findByLabelText("Короткое название");
    const save = screen.getByRole("button", { name: "Сохранить" });
    expect(save).toBeDisabled();
    fireEvent.change(field, { target: { value: "  Дубрава  " } });
    fireEvent.click(save);
    expect(await screen.findByRole("heading", { level: 1, name: "Дубрава" })).toBeInTheDocument();
    expect(await sent(fetchMock, "PATCH", "/api/company")).toEqual([
      JSON.stringify({ short_name: "Дубрава" }),
    ]);
  });

  it("an empty short name brings the registry name back (PATCH null)", async () => {
    const fetchMock = open({
      "GET /api/company": company({ short_name: "Дубрава" }),
      "PATCH /api/company": company({ short_name: null }),
    });
    const field = await screen.findByLabelText("Короткое название");
    fireEvent.change(field, { target: { value: "   " } });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить" }));
    expect(
      await screen.findByRole("heading", { level: 1, name: "ООО «Дубрава Мебель» (демо)" }),
    ).toBeInTheDocument();
    expect(await sent(fetchMock, "PATCH", "/api/company")).toEqual([
      JSON.stringify({ short_name: null }),
    ]);
  });

  it("lists members with roles; the signatory cannot remove themselves", async () => {
    open();
    const list = await memberList();
    const [mine, other] = within(list).getAllByRole("listitem");
    expect(mine).toHaveTextContent("Пётр Демо · вы");
    expect(mine).toHaveTextContent("Подписант");
    expect(within(mine as HTMLElement).queryByRole("button")).not.toBeInTheDocument();
    expect(other).toHaveTextContent("Ольга Демо");
    expect(other).toHaveTextContent("Главный бухгалтер");
    expect(other).toHaveTextContent("Готовит заявки");
    expect(
      within(other as HTMLElement).getByRole("button", { name: "Убрать Ольга Демо" }),
    ).toBeInTheDocument();
  });

  it("a preparer sees everything but changes nothing", async () => {
    open({}, "preparer");
    await memberList();
    expect(screen.queryByLabelText("Короткое название")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Убрать/ })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Логин сотрудника")).not.toBeInTheDocument();
    expect(
      screen.getByText("Приглашать и убирать сотрудников может подписант."),
    ).toBeInTheDocument();
  });

  it("removes a member after confirmation", async () => {
    let current = members;
    const fetchMock = open({
      "GET /api/company/members": () => current,
      "DELETE /api/company/members/2": () => {
        current = members.slice(0, 1);
        return [204, null];
      },
    });
    const list = await memberList();
    fireEvent.click(within(list).getByRole("button", { name: "Убрать Ольга Демо" }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent("Ольга Демо больше не увидит заявки компании");
    fireEvent.click(within(dialog).getByRole("button", { name: "Убрать" }));
    await waitFor(() => expect(screen.queryByText("Ольга Демо")).not.toBeInTheDocument());
    expect(await sent(fetchMock, "DELETE", "/api/company/members/2")).toHaveLength(1);
  });

  it("invites by login: nobody is added until the person accepts", async () => {
    const created: Schemas["Invitation"] = {
      id: 5,
      username: "ilya_demo",
      role: "preparer",
      position: "Финансовый директор",
      created_at: "2026-10-22T09:00:00Z",
    };
    let pending: Schemas["Invitation"][] = [];
    const fetchMock = open({
      "GET /api/company/invitations": () => pending,
      "POST /api/company/invitations": () => {
        pending = [created];
        return [201, created];
      },
    });
    await memberList();
    const inviteButton = screen.getByRole("button", { name: "Пригласить сотрудника" });
    fireEvent.click(inviteButton);
    expect(await screen.findByText("Напишите логин")).toBeInTheDocument();
    expect(screen.getByText("Напишите должность")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Логин сотрудника"), {
      target: { value: "ilya_demo" },
    });
    fireEvent.change(screen.getByLabelText("Должность"), {
      target: { value: "Финансовый директор" },
    });
    fireEvent.click(inviteButton);
    const waiting = await screen.findByRole("list", { name: "Ждут ответа" });
    expect(waiting).toHaveTextContent("ilya_demo");
    expect(waiting).toHaveTextContent("Готовит заявки · Финансовый директор");
    expect(await sent(fetchMock, "POST", "/api/company/invitations")).toEqual([
      JSON.stringify({ username: "ilya_demo", position: "Финансовый директор", role: "preparer" }),
    ]);
    // Not a member yet: the member list is unchanged.
    expect(within(await memberList()).getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getByLabelText("Логин сотрудника")).toHaveValue("");
  });

  it("a login with spaces is rejected before the request", async () => {
    const fetchMock = open();
    await memberList();
    fireEvent.change(screen.getByLabelText("Логин сотрудника"), {
      target: { value: "ilya demo" },
    });
    fireEvent.change(screen.getByLabelText("Должность"), { target: { value: "Бухгалтер" } });
    fireEvent.click(screen.getByRole("button", { name: "Пригласить сотрудника" }));
    expect(await screen.findByText(/только буквы, цифры/)).toBeInTheDocument();
    expect(await sent(fetchMock, "POST", "/api/company/invitations")).toHaveLength(0);
  });

  it("already invited: the API's message lands under the login field", async () => {
    open({
      "POST /api/company/invitations": [
        409,
        {
          error: { code: "invitation_exists", message: "Этот логин уже приглашён — ждём ответа." },
        },
      ],
    });
    await memberList();
    fireEvent.change(screen.getByLabelText("Логин сотрудника"), {
      target: { value: "ilya_demo" },
    });
    fireEvent.change(screen.getByLabelText("Должность"), { target: { value: "Бухгалтер" } });
    fireEvent.change(screen.getByLabelText("Роль"), { target: { value: "signatory" } });
    fireEvent.click(screen.getByRole("button", { name: "Пригласить сотрудника" }));
    expect(await screen.findByText("Этот логин уже приглашён — ждём ответа.")).toBeInTheDocument();
    expect(screen.getByLabelText("Логин сотрудника")).toHaveAttribute("aria-invalid", "true");
  });

  it("the signatory takes a pending invitation back", async () => {
    let pending: Schemas["Invitation"][] = [
      {
        id: 5,
        username: "ilya_demo",
        role: "signatory",
        position: "Директор",
        created_at: "2026-10-22T09:00:00Z",
      },
    ];
    const fetchMock = open({
      "GET /api/company/invitations": () => pending,
      "DELETE /api/company/invitations/5": () => {
        pending = [];
        return [204, null];
      },
    });
    fireEvent.click(
      await screen.findByRole("button", { name: "Отозвать приглашение для ilya_demo" }),
    );
    await waitFor(() =>
      expect(screen.queryByRole("list", { name: "Ждут ответа" })).not.toBeInTheDocument(),
    );
    expect(await sent(fetchMock, "DELETE", "/api/company/invitations/5")).toHaveLength(1);
  });

  it("a preparer sees pending invitations but cannot invite or take them back", async () => {
    open(
      {
        "GET /api/company/invitations": [
          {
            id: 5,
            username: "ilya_demo",
            role: "preparer",
            position: "Бухгалтер",
            created_at: "2026-10-22T09:00:00Z",
          },
        ],
      },
      "preparer",
    );
    expect(await screen.findByRole("list", { name: "Ждут ответа" })).toHaveTextContent("ilya_demo");
    expect(screen.queryByRole("button", { name: /Отозвать/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Пригласить сотрудника" })).not.toBeInTheDocument();
    expect(
      screen.getByText("Приглашать и убирать сотрудников может подписант."),
    ).toBeInTheDocument();
  });
});

describe("CompanyPage — data sources", () => {
  it("shows what is connected and connects the other one", async () => {
    const fetchMock = open({
      "GET /api/company": company({
        integrations: { bank_account: "2026-10-01T09:00:00Z", edo: null },
      }),
      "POST /api/company/integrations/edo/connect": {
        source: "edo",
        status: "connected",
        is_demo: true,
        snapshot: {},
      },
    });
    const list = await screen.findByRole("list", { name: "Источники данных" });
    const [bank, edo] = within(list).getAllByRole("listitem");
    expect(bank).toHaveTextContent("Выписка по расчётному счёту");
    expect(bank).toHaveTextContent(/Подключено/);
    fireEvent.click(within(edo as HTMLElement).getByRole("button", { name: "Подключить" }));
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([request]) =>
            (request as Request).method === "POST" &&
            (request as Request).url.endsWith("/api/company/integrations/edo/connect"),
        ),
      ).toBe(true),
    );
  });
});
