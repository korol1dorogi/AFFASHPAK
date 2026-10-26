import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Term, WithTerms } from "@/components/Term";
import { NEED, TERMS } from "@/texts";

describe("Term", () => {
  it("shows the definition when the term gets focus", async () => {
    render(<Term id="upd">УПД</Term>);
    const term = screen.getByText("УПД");
    expect(term).toHaveClass("term");
    expect(term).toHaveAttribute("tabindex", "0");

    fireEvent.focus(term);
    expect(await screen.findByRole("tooltip")).toHaveTextContent(TERMS.upd.text);
  });

  it("uses the title of the term when no words are given", () => {
    render(<Term id="overdraft" />);
    expect(screen.getByText("Овердрафт")).toHaveClass("term");
  });
});

describe("WithTerms", () => {
  it("turns [words](termId) into terms and keeps the rest as text", () => {
    const { container } = render(<WithTerms text={NEED.receivable_delay.hint} />);
    expect(container).toHaveTextContent(
      "Средства под поставку, которую покупатель оплатит через 30–90 дней. Требуется УПД в ЭДО, подходит факторинг.",
    );
    const terms = Array.from(container.querySelectorAll(".term")).map((term) => term.textContent);
    expect(terms).toEqual(["УПД", "ЭДО", "факторинг"]);
  });

  it("an unknown term id stays plain text", () => {
    const { container } = render(<WithTerms text="Это [слово](nothing) без расшифровки" />);
    expect(container).toHaveTextContent("Это слово без расшифровки");
    expect(container.querySelector(".term")).toBeNull();
  });

  it("every marked term in the purposes of financing exists", () => {
    const ids = Object.values(NEED).flatMap((need) =>
      [...need.hint.matchAll(/\]\(([a-z_]+)\)/g)].map((match) => match[1]),
    );
    expect(ids.length).toBeGreaterThan(0);
    for (const id of ids) expect(TERMS).toHaveProperty(id as string);
  });
});
