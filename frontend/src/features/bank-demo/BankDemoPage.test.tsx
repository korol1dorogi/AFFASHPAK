import { fireEvent, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { BankDemoPage } from "@/features/bank-demo/BankDemoPage";
import { mockApi, renderRoutes } from "@/test/utils";

const FAILURES = { egrul: false, transparent_business: false, bki: false, bank_account: false };

function render() {
  renderRoutes([{ path: "/bank/demo", element: <BankDemoPage /> }], "/bank/demo");
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("BankDemoPage — personas never vanish silently (UX2)", () => {
  it("a failed list is an alert with retry", async () => {
    let calls = 0;
    mockApi({
      "GET /api/demo/failures": FAILURES,
      "GET /api/demo/personas": () =>
        ++calls === 1
          ? [500, { error: { code: "server_error", message: "Стенд прилёг (демо)" } }]
          : [],
    });
    render();
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Не получилось загрузить демо-персон.");
    expect(alert).toHaveTextContent("Стенд прилёг (демо)");
    fireEvent.click(screen.getByRole("button", { name: "Повторить" }));
    expect(await screen.findByText("Демо-персон нет")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Проверить ещё раз" })).toBeInTheDocument();
  });
});
