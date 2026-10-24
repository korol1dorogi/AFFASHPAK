import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Schemas } from "@/api/client";
import { CreditHistory, creditHistoryFinding } from "@/features/applications/CreditHistory";

type Reason = Schemas["Reason"];

const history = (value: string | null, passed: boolean, message: string): Reason => ({
  metric: "bki_history",
  value,
  threshold: "30",
  passed,
  message,
});
const dscr: Reason = {
  metric: "dscr",
  value: "1.05",
  threshold: "1.25",
  passed: false,
  message: "Свободных денег мало",
};

describe("creditHistoryFinding", () => {
  it("says nothing for a clean history or when the bureau gave no data", () => {
    expect(creditHistoryFinding([dscr])).toBeNull();
    expect(
      creditHistoryFinding([history("0", true, "Кредитная история без серьёзных просрочек")]),
    ).toBeNull();
    expect(creditHistoryFinding([history(null, false, "БКИ не ответило")])).toBeNull();
  });

  it("explains a past overdue over the bank's limit", () => {
    expect(creditHistoryFinding([history("65", false, "Была просрочка")])).toBe(
      "В истории была просрочка 65 дней, а банк допускает не больше 30 дней, поэтому кредитную " +
        "историю оценили низко.",
    );
  });

  it("explains a past overdue within the limit without calling it a reason to decline", () => {
    const text = creditHistoryFinding([history("10", true, "Была просрочка")]);
    expect(text).toContain("10 дней, а банк допускает до 30 дней");
    expect(text).toContain("Отказывать из-за неё не будут");
  });

  it("uses the backend's sentence for a current overdue under the stop limit", () => {
    const text = creditHistoryFinding([
      history("0", false, "Сейчас есть просрочка по кредиту: 12 дней"),
    ]);
    expect(text).toBe(
      "Сейчас есть просрочка по кредиту: 12 дней. Это сильнее всего снижает оценку кредитной истории.",
    );
  });

  it("explains the stop factor of a current overdue over the limit", () => {
    const stop: Reason = {
      metric: "bki_current_overdue_days",
      value: "45",
      threshold: "30",
      passed: false,
      message: "Текущая просрочка",
    };
    expect(creditHistoryFinding([stop])).toContain(
      "Сейчас есть просрочка 45 дней. Пока она больше 30 дней",
    );
  });
});

describe("CreditHistory", () => {
  it("renders nothing when there is nothing to explain", () => {
    const { container } = render(<CreditHistory reasons={[dscr]} finished />);
    expect(container).toBeEmptyDOMElement();
  });

  it("tells a declined client where to get the report and how to dispute it", () => {
    render(<CreditHistory reasons={[dscr, history("65", false, "Была просрочка")]} finished />);
    const card = screen.getByRole("region", { name: "Кредитная история: что увидел банк" });
    expect(within(card).getByText(/с вашего согласия/)).toBeInTheDocument();
    const steps = within(card).getAllByRole("listitem");
    expect(steps).toHaveLength(4);
    expect(steps[0]).toHaveTextContent("Госуслугах");
    expect(steps[1]).toHaveTextContent("дважды в год это бесплатно");
    expect(steps[2]).toHaveTextContent("20 рабочих дней");
    expect(steps[3]).toHaveTextContent("К новой заявке приложите справку");
  });

  it("starts with paying off a current overdue and speaks about this application while open", () => {
    render(
      <CreditHistory
        reasons={[history("0", false, "Сейчас есть просрочка по кредиту: 12 дней")]}
        finished={false}
      />,
    );
    const steps = screen.getAllByRole("listitem");
    expect(steps[0]).toHaveTextContent("Погасите текущую просрочку");
    expect(steps.at(-1)).toHaveTextContent("Приложите к заявке справку");
  });
});
