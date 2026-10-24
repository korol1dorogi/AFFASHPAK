import { fireEvent, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RegisterPage } from "@/features/auth/RegisterPage";
import { mockApi, renderRoutes } from "@/test/utils";
import { LANDING } from "@/texts";

function open(registerReply: unknown = [201, {}]) {
  const fetchMock = mockApi({ "POST /api/auth/register": registerReply });
  renderRoutes([{ path: "/register", element: <RegisterPage /> }], "/register");
  return fetchMock;
}

function fill(username: string, password: string, repeat = password) {
  fireEvent.input(screen.getByLabelText("Имя и фамилия"), { target: { value: "Ирина Демо" } });
  fireEvent.input(screen.getByLabelText("Логин"), { target: { value: username } });
  fireEvent.input(screen.getByLabelText("Пароль"), { target: { value: password } });
  fireEvent.input(screen.getByLabelText("Повторите пароль"), { target: { value: repeat } });
  fireEvent.click(screen.getByRole("button", { name: "Создать учётную запись" }));
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("RegisterPage — password rules and one message at a time", () => {
  it("names every rule up front, under the field", () => {
    open();
    expect(
      screen.getByText(
        "От 8 символов, не только цифры, не простой вроде qwerty123 и не похожий на логин",
      ),
    ).toBeInTheDocument();
  });

  it("too short: only that, even though it is also all digits", async () => {
    open();
    fill("kofeinia", "123");
    expect(await screen.findByText("Пароль — от 8 символов")).toBeInTheDocument();
    expect(screen.queryByText("Пароль не может состоять только из цифр")).not.toBeInTheDocument();
  });

  it("long enough but only digits: says so before sending", async () => {
    const fetchMock = open();
    fill("kofeinia", "12345678");
    expect(await screen.findByText("Пароль не может состоять только из цифр")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("the server's single message lands under the password", async () => {
    open([
      400,
      {
        error: {
          code: "invalid",
          message: "Проверьте введённые данные.",
          details: { password: ["Пароль слишком похож на логин."] },
        },
      },
    ]);
    fill("kofeinia", "kofeinia2024");
    expect(await screen.findByText("Пароль слишком похож на логин.")).toBeInTheDocument();
    expect(screen.queryByText(/распространён|только из цифр/)).not.toBeInTheDocument();
  });
});

describe("RegisterPage — the password typed twice", () => {
  it("different repeat: «Пароли не совпадают», nothing is sent", async () => {
    const fetchMock = open();
    fill("kofeinia", "Kofe-2026-demo", "Kofe-2026-dem0");
    expect(await screen.findByText("Пароли не совпадают")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("an empty repeat asks for it", async () => {
    open();
    fill("kofeinia", "Kofe-2026-demo", "");
    expect(await screen.findByText("Повторите пароль", { selector: "p" })).toBeInTheDocument();
  });

  it("the same password twice: the API gets the password once, no repeat field", async () => {
    const fetchMock = open();
    fill("kofeinia", "Kofe-2026-demo");
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const request = fetchMock.mock.calls[0]?.[0] as Request;
    expect(await request.clone().json()).toEqual({
      full_name: "Ирина Демо",
      username: "kofeinia",
      password: "Kofe-2026-demo",
    });
  });
});

describe("Landing — the sign-up promise", () => {
  it("does not promise «только ИНН»: the INN comes after the account", () => {
    expect(LANDING.register).toBe("Зарегистрируйтесь — логин и пароль, компанию добавите по ИНН");
  });
});
