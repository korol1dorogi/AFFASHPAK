import { fireEvent, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StyleguidePage } from "@/features/styleguide/StyleguidePage";
import { renderRoutes } from "@/test/utils";
import { STYLEGUIDE } from "@/texts";

describe("StyleguidePage (UX4)", () => {
  it("shows every design-system section on one page", () => {
    renderRoutes([{ path: "/dev/ui", element: <StyleguidePage /> }], "/dev/ui");
    for (const title of Object.values(STYLEGUIDE.sections)) {
      expect(screen.getByText(title)).toBeInTheDocument();
    }
    // every status as a badge with a word, the score factor by factor, the counteroffer
    expect(document.querySelectorAll("[data-status]").length).toBeGreaterThanOrEqual(11);
    expect(screen.getByRole("list", { name: "Факторы скоринга" })).toBeInTheDocument();
    expect(screen.getByRole("article", { name: "Предложение банка" })).toBeInTheDocument();
  });

  it("the confirm dialog opens from its section", () => {
    renderRoutes([{ path: "/dev/ui", element: <StyleguidePage /> }], "/dev/ui");
    fireEvent.click(screen.getByRole("button", { name: STYLEGUIDE.openDialog }));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText(STYLEGUIDE.dialogTitle)).toBeInTheDocument();
  });
});
