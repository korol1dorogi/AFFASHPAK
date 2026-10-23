import { fireEvent, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Schemas } from "@/api/client";
import { BankDemoPage } from "@/features/bank-demo/BankDemoPage";
import { mockApi, renderRoutes } from "@/test/utils";
import { errorsWord } from "@/texts";

type Source = Schemas["DemoSource"];

const ALL_UP = { egrul: false, transparent_business: false, bki: false, bank_account: false };

function source(name: Source["source"], changes: Partial<Source> = {}): Source {
  return {
    source: name,
    failing: false,
    failing_until: null,
    breaker: { state: "closed", failures: 0, open_until: null, last_failure_at: null },
    ...changes,
  };
}

const inSeconds = (seconds: number) => new Date(Date.now() + seconds * 1000).toISOString();

/** Scenario 7 a moment later: BKI is off, one application met it, the breaker is open. */
const BKI_DOWN: Source[] = [
  source("egrul"),
  source("transparent_business", {
    breaker: { state: "closed", failures: 2, open_until: null, last_failure_at: inSeconds(-5) },
  }),
  source("bki", {
    failing: true,
    failing_until: inSeconds(14 * 60),
    breaker: {
      state: "open",
      failures: 3,
      open_until: inSeconds(24),
      last_failure_at: inSeconds(-6),
    },
  }),
  source("bank_account", {
    breaker: { state: "half_open", failures: 3, open_until: inSeconds(-1), last_failure_at: null },
  }),
];

function open(sources: Source[], failures = { ...ALL_UP, bki: true }) {
  const fetchMock = mockApi({
    "GET /api/demo/failures": failures,
    "PUT /api/demo/failures": (request: Request) => request.clone().json(),
    "GET /api/demo/sources": sources,
    "GET /api/demo/personas": [],
  });
  renderRoutes([{ path: "/bank/demo", element: <BankDemoPage /> }], "/bank/demo");
  return fetchMock;
}

const row = (name: string) =>
  screen
    .getByRole("list", { name: "Сбои источников (сценарий 7)" })
    .querySelector(`li[data-source="${name}"]`) as HTMLElement;

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("BankDemoPage — chaos demo (XP6)", () => {
  it("shows the breaker of every source in words, live", async () => {
    open(BKI_DOWN);
    await screen.findByText("Breaker открыт");

    const bki = row("bki");
    expect(within(bki).getByText("Сбой")).toBeInTheDocument();
    expect(bki.querySelector("[data-breaker]")).toHaveAttribute("data-breaker", "open");
    expect(bki).toHaveTextContent("3 ошибки подряд");
    expect(bki).toHaveTextContent(/повтор через 2[45] с/);
    expect(bki).toHaveTextContent(/сбой выключится сам через 1[45] мин/);

    expect(row("egrul")).toHaveTextContent("Breaker закрыт");
    expect(row("egrul")).toHaveTextContent("вызовы идут");
    expect(row("transparent_business")).toHaveTextContent("ошибок подряд: 2 из 3");
    expect(row("bank_account")).toHaveTextContent("Breaker: пробный вызов");
    expect(row("bank_account")).toHaveTextContent("следующий вызов пробный");
  });

  it("says how to show scenario 7 in two clicks", async () => {
    open(BKI_DOWN);
    expect(await screen.findByText(/Сценарий 7 в два клика/)).toHaveTextContent(
      "выключите «Бюро кредитных историй» и нажмите «Войти» у персоны сценария 7",
    );
  });

  it("turning a source back on re-reads the live state at once", async () => {
    const fetchMock = open(BKI_DOWN);
    await screen.findByText("Breaker открыт");
    const reads = () =>
      fetchMock.mock.calls.filter(
        ([request]) =>
          (request as Request).method === "GET" &&
          new URL((request as Request).url).pathname === "/api/demo/sources",
      ).length;
    const before = reads();

    fireEvent.click(within(row("bki")).getByRole("switch"));

    await vi.waitFor(() => expect(reads()).toBeGreaterThan(before));
    const put = fetchMock.mock.calls.find(([request]) => (request as Request).method === "PUT");
    expect(await (put?.[0] as Request).clone().json()).toEqual(ALL_UP);
  });
});

describe("errorsWord", () => {
  it.each([
    [1, "ошибка"],
    [2, "ошибки"],
    [3, "ошибки"],
    [5, "ошибок"],
    [11, "ошибок"],
    [21, "ошибка"],
    [24, "ошибки"],
  ])("%i → %s", (n, word) => {
    expect(errorsWord(n)).toBe(word);
  });
});
