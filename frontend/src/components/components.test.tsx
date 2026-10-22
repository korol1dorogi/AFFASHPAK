import { fireEvent, render, screen, within } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import type { Schemas } from "@/api/client";
import { MoneyInput } from "@/components/MoneyInput";
import { OfferCard } from "@/components/OfferCard";
import { ReasonList } from "@/components/ReasonList";
import { StatusBadge } from "@/components/StatusBadge";
import { StatusTimeline } from "@/components/StatusTimeline";
import { Button } from "@/components/ui/button";
import { STATUS } from "@/texts";

// Testing Library's text normalizer turns   into spaces; input values keep it.
const nbsp = (text: string) => text.replace(/ /g, " ");

describe("StatusBadge", () => {
  it.each(Object.entries(STATUS))("%s shows a word, not only a colour", (status, text) => {
    render(<StatusBadge status={status as Schemas["ApplicationStatus"]} />);
    const badge = screen.getByText(text.label);
    expect(badge).toHaveAttribute("data-status", status);
    expect(badge.querySelector("svg")).not.toBeNull();
  });
});

describe("ReasonList", () => {
  const reasons: Schemas["Reason"][] = [
    {
      metric: "overdraft_limit",
      value: "900000.00",
      threshold: null,
      passed: true,
      message: "Лимит от оборота",
    },
    {
      metric: "max_loan_by_dscr",
      value: "2009314.00",
      threshold: "5300000.00",
      passed: false,
      message: "Меньше запрошенного",
    },
    {
      metric: "debt_to_ebitda",
      value: null,
      threshold: "3.5",
      passed: false,
      message: "Отчётности нет",
    },
    { metric: "dscr", value: null, threshold: "1.25", passed: true, message: "Долгов нет" },
  ];

  it("marks passed, failed and missing values with words", () => {
    render(<ReasonList reasons={reasons} />);
    const items = screen.getAllByRole("listitem");
    expect(
      within(items[0] as HTMLElement).getByRole("img", { name: "пройдено" }),
    ).toBeInTheDocument();
    expect(
      within(items[1] as HTMLElement).getByRole("img", { name: "не пройдено" }),
    ).toBeInTheDocument();
    expect(
      within(items[2] as HTMLElement).getByRole("img", { name: "нет данных" }),
    ).toBeInTheDocument();
    expect(items[2]).toHaveTextContent("нет данных");
  });

  it("formats money and never shows a missing value as 0", () => {
    render(<ReasonList reasons={reasons} />);
    expect(screen.getByText("900 000 ₽")).toBeInTheDocument();
    expect(screen.getByText("порог 5 300 000 ₽")).toBeInTheDocument();
    expect(screen.queryByText(/^0$/)).toBeNull();
  });

  it("uses plain titles for everyone and adds metric codes for the bank", () => {
    const { rerender } = render(<ReasonList reasons={reasons.slice(0, 1)} />);
    expect(
      screen.getByText("Лимит от оборота", { selector: "p.font-semibold" }),
    ).toBeInTheDocument();
    rerender(<ReasonList reasons={reasons.slice(0, 1)} variant="bank" />);
    expect(
      screen.getByText("Лимит от оборота", { selector: "p.font-semibold" }),
    ).toBeInTheDocument();
    expect(screen.getByText("overdraft_limit")).toBeInTheDocument();
  });

  it("a failed yes/no check is a failure, not «нет данных» (С1, С2, С6, П6)", () => {
    const stop: Schemas["Reason"] = {
      metric: "registry_status",
      value: null,
      threshold: null,
      passed: false,
      message: "Компания в процессе ликвидации",
    };
    render(<ReasonList reasons={[stop]} />);
    expect(screen.getByRole("img", { name: "не пройдено" })).toBeInTheDocument();
    expect(screen.queryByRole("img", { name: "нет данных" })).toBeNull();
  });

  it("shows shares to the tenth of a percent, like rates", () => {
    const share: Schemas["Reason"] = {
      metric: "counterparty_concentration",
      value: "0.235",
      threshold: "0.6",
      passed: true,
      message: "Один покупатель — меньше половины выручки",
    };
    render(<ReasonList reasons={[share]} />);
    expect(screen.getByText(/^23,5\s%$/)).toBeInTheDocument();
  });
});

describe("OfferCard", () => {
  const product = {
    code: "working_capital_loan_basic",
    kind: "working_capital_loan",
    name: "КПО",
    description: "",
    rate_min: "0.22",
    rate_max: "0.30",
    term_min_months: 3,
    term_max_months: 24,
    amount_min: "300000.00",
    amount_max: "30000000.00",
    is_revolving: false,
    collateral_required: false,
    params: {},
    requirements: { min_business_age_months: 6, legal_forms: ["ip", "ooo"] },
    required_documents: [],
  } satisfies Schemas["Product"];
  const counteroffer: Schemas["Offer"] = {
    id: 1,
    product,
    amount: "2009314.00",
    requested_amount: "5300000.00",
    term_months: 12,
    rate: "0.2400",
    monthly_payment: "189999.92",
    is_counteroffer: true,
    product_changed: false,
    status: "active",
    expires_at: "2026-11-13T10:13:00Z",
    reasons: [
      {
        metric: "max_loan_by_dscr",
        value: "2009314.00",
        threshold: "5300000.00",
        passed: false,
        message: "Поток не выдержит больше",
      },
    ],
  };

  it("explains a counteroffer and offers only the available actions", () => {
    const onAccept = vi.fn();
    render(
      <OfferCard
        offer={counteroffer}
        actions={["accept_offer", "decline_offer", "cancel"]}
        onAccept={onAccept}
      />,
    );
    expect(screen.getByText("Вы просили 5 300 000 ₽")).toBeInTheDocument();
    expect(screen.getByText("Почему меньше, чем вы просили")).toBeInTheDocument();
    expect(screen.getByText("24 %")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Принять и подписать" }));
    expect(onAccept).toHaveBeenCalledOnce();
  });

  it("hides the buttons when the user may not act (preparer)", () => {
    render(<OfferCard offer={counteroffer} actions={[]} />);
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("says the payment depends on use for revolving products", () => {
    render(
      <OfferCard
        offer={{
          ...counteroffer,
          is_counteroffer: false,
          monthly_payment: null,
          product: { ...product, is_revolving: true },
        }}
        actions={[]}
      />,
    );
    expect(screen.getByText("Зависит от использования")).toBeInTheDocument();
  });
});

describe("MoneyInput", () => {
  function Harness({ onValue }: { onValue: (value: string | null) => void }) {
    const [value, setValue] = useState("");
    return (
      <MoneyInput
        aria-label="Сумма"
        value={value}
        onValueChange={(next) => {
          onValue(next);
          setValue(next ?? "");
        }}
      />
    );
  }

  it("groups digits and hands the API a decimal string", () => {
    const onValue = vi.fn();
    render(<Harness onValue={onValue} />);
    const input = screen.getByLabelText("Сумма");
    fireEvent.change(input, { target: { value: "5300000" } });
    expect(input).toHaveValue(nbsp("5 300 000"));
    expect(onValue).toHaveBeenLastCalledWith("5300000.00");
    fireEvent.change(input, { target: { value: "1200,5" } });
    expect(onValue).toHaveBeenLastCalledWith("1200.50");
  });
});

describe("StatusTimeline", () => {
  const event: Schemas["ApplicationEvent"] = {
    id: 1,
    kind: "comment",
    from_status: null,
    to_status: null,
    actor_kind: "bank",
    actor: null,
    message: "Проверить выписку",
    is_internal: true,
    created_at: "2026-10-20T10:00:00Z",
  };

  it("hides internal bank events from the client and says the history is empty", () => {
    render(<StatusTimeline events={[event]} />);
    expect(screen.queryByText("Проверить выписку")).toBeNull();
    expect(screen.getByText("Событий пока нет")).toBeInTheDocument();
  });

  it("shows internal events to the bank", () => {
    render(<StatusTimeline events={[event]} showInternal />);
    expect(screen.getByText("Проверить выписку")).toBeInTheDocument();
    expect(screen.getByText(/видно только банку/)).toBeInTheDocument();
  });
});

describe("Button", () => {
  it("renders a link as a button without breaking Slot (asChild)", () => {
    render(
      <Button asChild size="lg">
        <a href="/login">Войти</a>
      </Button>,
    );
    expect(screen.getByRole("link", { name: "Войти" })).toHaveAttribute("data-slot", "button");
  });

  it("shows a spinner and blocks repeated clicks while loading", () => {
    const onClick = vi.fn();
    render(
      <Button loading onClick={onClick}>
        Отправляем…
      </Button>,
    );
    const button = screen.getByRole("button", { name: "Отправляем…" });
    expect(button).toBeDisabled();
    fireEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
  });
});
