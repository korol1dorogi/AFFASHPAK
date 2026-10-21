import { describe, expect, it } from "vitest";

import {
  hasActiveFilters,
  pageCount,
  parseFilters,
  patchFilters,
  toggleStatus,
  toQuery,
  toSearchParams,
} from "@/features/bank-queue/params";

const fromUrl = (search: string) => toQuery(parseFilters(new URLSearchParams(search)));

describe("URL → listBankApplications query", () => {
  it("sends only the page and the page size without filters", () => {
    expect(fromUrl("")).toEqual({ page: 1, page_size: 20 });
  });

  it("keeps several statuses in order and drops duplicates", () => {
    expect(
      fromUrl("status=manual_review&status=info_requested&status=manual_review").status,
    ).toEqual(["manual_review", "info_requested"]);
  });

  it("passes every filter with its contract name", () => {
    expect(
      fromUrl(
        "product_kind=factoring&grade=B&assignee=me&min_hours_in_status=24&search=Кофейня&ordering=-requested_amount&page=3",
      ),
    ).toEqual({
      page: 3,
      page_size: 20,
      product_kind: "factoring",
      grade: "B",
      assignee: "me",
      min_hours_in_status: 24,
      search: "Кофейня",
      ordering: "-requested_amount",
    });
  });

  it.each([
    ["me", "me"],
    ["none", "none"],
    ["17", "17"],
    ["", undefined],
    ["someone", undefined],
  ])("assignee=%s → %s", (value, expected) => {
    expect(fromUrl(`assignee=${value}`).assignee).toBe(expected);
  });

  it("does not send empty or invalid values", () => {
    const query = fromUrl(
      "status=foo&product_kind=&grade=Z&assignee=&min_hours_in_status=-1&search=%20%20&ordering=name&page=0",
    );
    expect(query).toEqual({ page: 1, page_size: 20 });
  });

  it("keeps a non-preset hours value and zero", () => {
    expect(fromUrl("min_hours_in_status=10").min_hours_in_status).toBe(10);
    expect(fromUrl("min_hours_in_status=0").min_hours_in_status).toBe(0);
  });

  it("trims the search and cuts it to the contract's 100 characters", () => {
    expect(fromUrl("search=%20%207701234567%20").search).toBe("7701234567");
    expect(fromUrl(`search=${"я".repeat(150)}`).search).toHaveLength(100);
  });
});

describe("filters → URL", () => {
  it("leaves defaults out of the address", () => {
    expect(toSearchParams({ status: [], page: 1 }).toString()).toBe("");
  });

  it("round-trips through the URL", () => {
    const search =
      "status=offer&status=declined&product_kind=leasing&grade=A&assignee=none&min_hours_in_status=72&search=%D0%9E%D0%9E%D0%9E&ordering=created_at&page=2";
    const params = toSearchParams(parseFilters(new URLSearchParams(search)));
    expect(params.toString()).toBe(search);
  });

  it("goes back to page 1 when a filter changes, but not when the page does", () => {
    const filters = parseFilters(new URLSearchParams("grade=C&page=4"));
    expect(patchFilters(filters, { grade: "D" }).page).toBe(1);
    expect(patchFilters(filters, { page: 5 }).page).toBe(5);
  });
});

describe("helpers", () => {
  it("toggles a status on and off", () => {
    expect(toggleStatus(["offer"], "declined")).toEqual(["offer", "declined"]);
    expect(toggleStatus(["offer", "declined"], "offer")).toEqual(["declined"]);
  });

  it("ordering and page are not filters", () => {
    expect(hasActiveFilters(parseFilters(new URLSearchParams("ordering=created_at&page=2")))).toBe(
      false,
    );
    expect(hasActiveFilters(parseFilters(new URLSearchParams("assignee=me")))).toBe(true);
  });

  it("counts pages of 20", () => {
    expect(pageCount(0)).toBe(1);
    expect(pageCount(20)).toBe(1);
    expect(pageCount(250)).toBe(13);
  });
});
