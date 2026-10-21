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
    // The only fields are the short name and the new member: requisites are never typed in.
    await memberList();
    expect(screen.getAllByRole("textbox").map((field) => field.getAttribute("name"))).toEqual([
      "name",
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

  it("signatory renames the company: PATCH {name}, the header follows", async () => {
    const fetchMock = open({
      "PATCH /api/company": company({ name: "Дубрава" }),
    });
    const field = await screen.findByLabelText("Короткое название");
    const save = screen.getByRole("button", { name: "Сохранить" });
    expect(save).toBeDisabled();
    fireEvent.change(field, { target: { value: "  Дубрава  " } });
    fireEvent.click(save);
    expect(await screen.findByRole("heading", { level: 1, name: "Дубрава" })).toBeInTheDocument();
    expect(await sent(fetchMock, "PATCH", "/api/company")).toEqual([
      JSON.stringify({ name: "Дубрава" }),
    ]);
  });

  it("an empty name is refused", async () => {
    const fetchMock = open();
    fireEvent.change(await screen.findByLabelText("Короткое название"), {
      target: { value: " " },
    });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить" }));
    expect(await screen.findByText("Напишите название")).toBeInTheDocument();
    expect(await sent(fetchMock, "PATCH", "/api/company")).toEqual([]);
  });
});

describe("CompanyPage — members and roles", () => {
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
      screen.getByText("Добавлять и убирать сотрудников может подписант."),
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

  it("adds a member by login with a position and a role", async () => {
    const added: Schemas["Member"] = {
      id: 3,
      user: { id: 12, full_name: "Илья Демо" },
      role: "preparer",
      position: "Финансовый директор",
    };
    let current = members;
    const fetchMock = open({
      "GET /api/company/members": () => current,
      "POST /api/company/members": () => {
        current = [...members, added];
        return [201, added];
      },
    });
    await memberList();
    const addButton = screen.getByRole("button", { name: "Добавить сотрудника" });
    fireEvent.click(addButton);
    expect(await screen.findByText("Напишите логин")).toBeInTheDocument();
    expect(screen.getByText("Напишите должность")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Логин сотрудника"), {
      target: { value: "ilya_demo" },
    });
    fireEvent.change(screen.getByLabelText("Должность"), {
      target: { value: "Финансовый директор" },
    });
    fireEvent.click(addButton);
    expect(await screen.findByText("Илья Демо")).toBeInTheDocument();
    expect(await sent(fetchMock, "POST", "/api/company/members")).toEqual([
      JSON.stringify({ username: "ilya_demo", position: "Финансовый директор", role: "preparer" }),
    ]);
    expect(screen.getByLabelText("Логин сотрудника")).toHaveValue("");
  });

  it("unknown login: the API's message lands under the login field", async () => {
    open({
      "POST /api/company/members": [
        404,
        { error: { code: "not_found", message: "Пользователь с таким логином не найден." } },
      ],
    });
    await memberList();
    fireEvent.change(screen.getByLabelText("Логин сотрудника"), {
      target: { value: "nobody" },
    });
    fireEvent.change(screen.getByLabelText("Должность"), { target: { value: "Бухгалтер" } });
    fireEvent.change(screen.getByLabelText("Роль"), { target: { value: "signatory" } });
    fireEvent.click(screen.getByRole("button", { name: "Добавить сотрудника" }));
    expect(await screen.findByText("Пользователь с таким логином не найден.")).toBeInTheDocument();
    expect(screen.getByLabelText("Логин сотрудника")).toHaveAttribute("aria-invalid", "true");
  });
});
