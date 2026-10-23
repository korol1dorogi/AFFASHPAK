import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Schemas } from "@/api/client";
import { AskAssistant } from "@/features/assistant/AskAssistant";
import { AssistantPanel } from "@/features/assistant/AssistantPanel";
import { AssistantProvider } from "@/features/assistant/context";
import { AssistantTab } from "@/features/bank-application/AssistantTab";
import { mockApi, renderRoutes, renderWithQuery } from "@/test/utils";

type Message = Schemas["AssistantMessage"];
type ToolCall = Schemas["AssistantToolCall"];

afterEach(() => vi.unstubAllGlobals());

const OFFERS: ToolCall = {
  name: "recommend_products",
  arguments: { need_type: "cash_gap" },
  result: {
    need_type: "cash_gap",
    offers: [
      {
        product: { code: "overdraft_basic", name: "Овердрафт для бизнеса (демо)" },
        amount: "900000.00",
        term_months: 12,
        rate: "0.2000",
        monthly_payment: null,
        fits: true,
      },
    ],
  },
};

const DRAFT: ToolCall = {
  name: "create_draft",
  arguments: {},
  result: {
    pending_action: {
      id: "5f3c2a1e-0000-4000-8000-000000000001",
      kind: "create_application",
      summary: "Создать черновик заявки: 900 000 ₽ на 12 мес. Отправите заявку в банк вы сами.",
      application_id: null,
    },
  },
};

/** A tiny assistant backend: history grows with every message; the reply is scripted. */
function backend(reply: (text: string) => { text: string; calls: ToolCall[] }) {
  const history: Message[] = [];
  const sent: { text: string; application_id?: number }[] = [];
  const fetchMock = mockApi({
    "GET /api/assistant/messages": () => history,
    "POST /api/assistant/messages": async (request: Request) => {
      const body = (await request.clone().json()) as { text: string; application_id?: number };
      sent.push(body);
      const answer = reply(body.text);
      history.push(
        {
          id: history.length + 1,
          role: "user",
          content: body.text,
          tool_calls: [],
          created_at: "2026-10-23T10:00:00Z",
        },
        {
          id: history.length + 2,
          role: "assistant",
          content: answer.text,
          tool_calls: answer.calls,
          created_at: "2026-10-23T10:00:01Z",
        },
      );
      const pending = answer.calls.find((call) => call.name === "create_draft");
      return {
        reply: answer.text,
        tool_calls: answer.calls,
        pending_action: pending
          ? (pending.result as { pending_action: unknown }).pending_action
          : null,
      };
    },
    "POST /api/assistant/actions/5f3c2a1e-0000-4000-8000-000000000001/confirm": {
      action_id: "5f3c2a1e-0000-4000-8000-000000000001",
      status: "done",
      application: { id: 77 },
    },
    "POST /api/applications": [201, { id: 88 }],
  });
  return { fetchMock, sent };
}

function renderPanel(path = "/app") {
  return renderRoutes(
    [
      {
        path: "/app/*",
        element: (
          <AssistantProvider>
            <AssistantPanel />
            <AskAssistant question="Почему такое решение?" applicationId={42} />
          </AssistantProvider>
        ),
      },
      { path: "/app/applications/:id/edit/:step", element: <p>Мастер заявки</p> },
    ],
    path,
  );
}

function openPanel() {
  fireEvent.click(screen.getByRole("button", { name: "Ассистент" }));
  return screen.getByRole("dialog");
}

describe("AssistantPanel", () => {
  it("offers examples when empty and shows the answer as plain text", async () => {
    backend(() => ({ text: "<b>Привет</b> — подберу овердрафт", calls: [] }));
    renderPanel();
    const panel = openPanel();
    fireEvent.click(await within(panel).findByRole("button", { name: /Зарплата 5-го/ }));
    expect(await within(panel).findByText("<b>Привет</b> — подберу овердрафт")).toBeInTheDocument();
    expect(panel.querySelector("b")).toBeNull(); // text, never HTML
  });

  it("shows offers as cards and «Оформить» creates a draft from the offer", async () => {
    const { fetchMock } = backend(() => ({ text: "Подобрал овердрафт.", calls: [OFFERS] }));
    const router = renderPanel();
    const panel = openPanel();
    fireEvent.change(within(panel).getByRole("textbox"), {
      target: { value: "Не хватает на зарплату" },
    });
    fireEvent.click(within(panel).getByRole("button", { name: "Отправить" }));
    expect(await within(panel).findByText("Овердрафт для бизнеса (демо)")).toBeInTheDocument();
    expect(within(panel).getByText("Что сделал ассистент")).toBeInTheDocument();

    fireEvent.click(within(panel).getByRole("button", { name: "Оформить" }));
    await waitFor(() =>
      expect(router.state.location.pathname).toBe("/app/applications/88/edit/business"),
    );
    const created = fetchMock.mock.calls
      .map(([request]) => request as Request)
      .find(
        (request) =>
          request.method === "POST" && new URL(request.url).pathname === "/api/applications",
      );
    expect(await created?.json()).toMatchObject({
      need_type: "cash_gap",
      requested_amount: "900000.00",
      product_code: "overdraft_basic",
      prefill_source: "assistant",
    });
  });

  it("a proposed draft waits for «Подтвердить»", async () => {
    backend(() => ({ text: "Подготовил черновик.", calls: [DRAFT] }));
    renderPanel();
    const panel = openPanel();
    fireEvent.change(within(panel).getByRole("textbox"), { target: { value: "Оформи овердрафт" } });
    fireEvent.click(within(panel).getByRole("button", { name: "Отправить" }));
    const card = await within(panel).findByRole("region", { name: "Ассистент предлагает" });
    expect(card).toHaveTextContent("Отправите заявку в банк вы сами");
    fireEvent.click(within(card).getByRole("button", { name: "Подтвердить" }));
    expect(await within(panel).findByText("Черновик создан")).toBeInTheDocument();
    expect(within(panel).getByRole("link", { name: "Открыть черновик" })).toHaveAttribute(
      "href",
      "/app/applications/77/edit/params",
    );
  });

  it("«Отмена» drops the proposal without creating anything", async () => {
    const { fetchMock } = backend(() => ({ text: "Подготовил черновик.", calls: [DRAFT] }));
    renderPanel();
    const panel = openPanel();
    fireEvent.change(within(panel).getByRole("textbox"), { target: { value: "Оформи" } });
    fireEvent.click(within(panel).getByRole("button", { name: "Отправить" }));
    const card = await within(panel).findByRole("region", { name: "Ассистент предлагает" });
    fireEvent.click(within(card).getByRole("button", { name: "Отмена" }));
    expect(await within(panel).findByText(/ничего не создано/)).toBeInTheDocument();
    const confirms = fetchMock.mock.calls.filter(([request]) =>
      (request as Request).url.includes("/confirm"),
    );
    expect(confirms).toHaveLength(0);
  });

  it("says to wait a minute on 429", async () => {
    mockApi({
      "GET /api/assistant/messages": [],
      "POST /api/assistant/messages": [429, { error: { code: "throttled", message: "x" } }],
    });
    renderPanel();
    const panel = openPanel();
    fireEvent.change(within(panel).getByRole("textbox"), { target: { value: "Привет" } });
    fireEvent.click(within(panel).getByRole("button", { name: "Отправить" }));
    expect(await within(panel).findByRole("alert")).toHaveTextContent("подождите минуту");
  });

  it("a context button asks about its application (AI6)", async () => {
    const { sent } = backend(() => ({ text: "Решение: отказ.", calls: [] }));
    renderPanel();
    fireEvent.click(screen.getByRole("button", { name: "Почему такое решение?" }));
    const panel = await screen.findByRole("dialog");
    expect(within(panel).getByText("Говорим о заявке № 42")).toBeInTheDocument();
    expect(await within(panel).findByText("Решение: отказ.")).toBeInTheDocument();
    expect(sent).toEqual([{ text: "Почему такое решение?", application_id: 42 }]);
  });

  it("on an application page the dialogue is about that application", async () => {
    const { fetchMock } = backend(() => ({ text: "ок", calls: [] }));
    renderPanel("/app/applications/42");
    openPanel();
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([request]) =>
          (request as Request).url.includes("/api/assistant/messages?application_id=42"),
        ),
      ).toBe(true),
    );
  });
});

describe("AssistantTab (bank, AI9)", () => {
  it("shows the decision summary and hands the draft to the comment field", async () => {
    mockApi({
      "GET /api/bank/applications/5/assistant/messages": [],
      "POST /api/bank/applications/5/assistant/summary": {
        risks: ["Свободных денег мало (скоринг: dscr)"],
        to_verify: ["Запросить: выписку за 12 месяцев"],
        draft_comment: "Грейд E (47 из 100). Основные риски: свободных денег мало.",
        sources: ["скоринг: dscr"],
      },
    });
    const onInsert = vi.fn();
    renderWithQuery(<AssistantTab applicationId={5} onInsertComment={onInsert} />);
    fireEvent.click(screen.getByRole("button", { name: "Сводка для решения" }));
    expect(await screen.findByText("Свободных денег мало (скоринг: dscr)")).toBeInTheDocument();
    expect(screen.getByText("Запросить: выписку за 12 месяцев")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Вставить в комментарий" }));
    expect(onInsert).toHaveBeenCalledWith(
      "Грейд E (47 из 100). Основные риски: свободных денег мало.",
    );
  });
});
