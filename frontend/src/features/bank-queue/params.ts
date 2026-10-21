/**
 * Queue filters live in the URL (docs/frontend.md §1.5, «Очередь банка»): URL keys are the
 * listBankApplications parameter names, defaults are left out of the URL and out of the request.
 */
import type { Schemas } from "@/api/client";
import type { operations } from "@/api/schema";
import { PRODUCT_KIND, QUEUE_ORDERING, type QueueOrdering, STATUS } from "@/texts";

export type QueueQuery = NonNullable<operations["listBankApplications"]["parameters"]["query"]>;
type Status = Schemas["ApplicationStatus"];
type ProductKind = Schemas["ProductKind"];
type Grade = Schemas["Grade"];

export const PAGE_SIZE = 20;
export const GRADES = ["A", "B", "C", "D", "E"] as const satisfies readonly Grade[];
export const HOUR_PRESETS = [4, 24, 72] as const;
export const OVERDUE_HOURS = 24;
const SEARCH_MAX = 100;

export const STATUSES = Object.keys(STATUS) as Status[];
export const PRODUCT_KINDS = Object.keys(PRODUCT_KIND) as ProductKind[];
export const ORDERINGS = Object.keys(QUEUE_ORDERING) as QueueOrdering[];
/** What the server sorts by when `ordering` is not sent: the longest-waiting first. */
export const DEFAULT_ORDERING: QueueOrdering = "status_changed_at";

export interface QueueFilters {
  status: Status[];
  product_kind?: ProductKind;
  grade?: Grade;
  /** "me", "none" or an employee id; absent = everyone. */
  assignee?: string;
  min_hours_in_status?: number;
  search?: string;
  ordering?: QueueOrdering;
  page: number;
}

const FILTER_KEYS = [
  "status",
  "product_kind",
  "grade",
  "assignee",
  "min_hours_in_status",
  "search",
] as const;

function oneOf<T extends string>(value: string | null, allowed: readonly T[]): T | undefined {
  return value !== null && (allowed as readonly string[]).includes(value)
    ? (value as T)
    : undefined;
}

function nonNegativeInt(value: string | null, min: number): number | undefined {
  if (value === null || !/^\d+$/.test(value)) return undefined;
  const number = Number(value);
  return Number.isSafeInteger(number) && number >= min ? number : undefined;
}

/** URL → filters; anything the contract would reject is dropped, so a stale link never gives 400. */
export function parseFilters(params: URLSearchParams): QueueFilters {
  const status = params
    .getAll("status")
    .filter((value): value is Status => !!oneOf(value, STATUSES));
  const assignee = params.get("assignee");
  const search = params.get("search")?.trim().slice(0, SEARCH_MAX);
  return {
    status: [...new Set(status)],
    product_kind: oneOf(params.get("product_kind"), PRODUCT_KINDS),
    grade: oneOf(params.get("grade"), GRADES),
    assignee: assignee && /^(me|none|\d+)$/.test(assignee) ? assignee : undefined,
    min_hours_in_status: nonNegativeInt(params.get("min_hours_in_status"), 0),
    search: search || undefined,
    ordering: oneOf(params.get("ordering"), ORDERINGS),
    page: nonNegativeInt(params.get("page"), 1) ?? 1,
  };
}

/** Filters → listBankApplications query: empty values are not sent, the page size always is. */
export function toQuery(filters: QueueFilters): QueueQuery {
  const query: QueueQuery = { page: filters.page, page_size: PAGE_SIZE };
  if (filters.status.length) query.status = filters.status;
  if (filters.product_kind) query.product_kind = filters.product_kind;
  if (filters.grade) query.grade = filters.grade;
  if (filters.assignee) query.assignee = filters.assignee;
  if (filters.min_hours_in_status !== undefined)
    query.min_hours_in_status = filters.min_hours_in_status;
  if (filters.search) query.search = filters.search;
  if (filters.ordering) query.ordering = filters.ordering;
  return query;
}

/** Filters → URL; defaults (page 1, no ordering, empty values) stay out of the address. */
export function toSearchParams(filters: QueueFilters): URLSearchParams {
  const params = new URLSearchParams();
  for (const status of filters.status) params.append("status", status);
  const single = {
    product_kind: filters.product_kind,
    grade: filters.grade,
    assignee: filters.assignee,
    min_hours_in_status: filters.min_hours_in_status,
    search: filters.search?.trim(),
    ordering: filters.ordering,
    page: filters.page > 1 ? filters.page : undefined,
  };
  for (const [key, value] of Object.entries(single)) {
    if (value !== undefined && value !== "") params.set(key, String(value));
  }
  return params;
}

/** Apply a change; any change except the page itself sends you back to page 1. */
export function patchFilters(filters: QueueFilters, patch: Partial<QueueFilters>): QueueFilters {
  return { ...filters, page: 1, ...patch };
}

export function toggleStatus(statuses: Status[], status: Status): Status[] {
  return statuses.includes(status) ? statuses.filter((s) => s !== status) : [...statuses, status];
}

/** Anything narrowing the list (ordering and page do not). */
export function hasActiveFilters(filters: QueueFilters): boolean {
  return FILTER_KEYS.some((key) => {
    const value = filters[key];
    return Array.isArray(value) ? value.length > 0 : value !== undefined;
  });
}

export function pageCount(count: number): number {
  return Math.max(1, Math.ceil(count / PAGE_SIZE));
}
