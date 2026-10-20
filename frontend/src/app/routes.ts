/**
 * Every route of the app (docs/frontend.md §2). Components never write path strings:
 * they use these constants and builders.
 */
export const WIZARD_STEPS = ["params", "business", "documents", "review"] as const;
export type WizardStep = (typeof WIZARD_STEPS)[number];

export const BANK_TABS = [
  "application",
  "client",
  "checks",
  "scoring",
  "documents",
  "journal",
] as const;
export type BankTab = (typeof BANK_TABS)[number];

type Id = number | string;

export const routes = {
  landing: "/",
  login: "/login",
  register: "/register",
  status: "/status",

  home: "/app",
  companyNew: "/app/company/new",
  company: "/app/company",
  match: "/app/match",
  products: "/app/products",
  applications: "/app/applications",
  applicationNew: "/app/applications/new",
  application: (id: Id) => `/app/applications/${id}`,
  applicationEdit: (id: Id, step: WizardStep = "params") => `/app/applications/${id}/edit/${step}`,
  applicationSign: (id: Id) => `/app/applications/${id}/sign`,
  notifications: "/app/notifications",

  bank: "/bank",
  bankApplication: (id: Id, tab?: BankTab) => `/bank/applications/${id}${tab ? `?tab=${tab}` : ""}`,
  bankDashboard: "/bank/dashboard",
  bankDemo: "/bank/demo",

  devUi: "/dev/ui",
} as const;

/** Where a signed-in user lands. */
export function homeFor(kind: "client" | "bank"): string {
  return kind === "bank" ? routes.bank : routes.home;
}

/** Only same-app paths are allowed as ?next= targets (no open redirects). */
export function safeNext(next: string | null): string | null {
  if (!next?.startsWith("/") || next.startsWith("//")) return null;
  return next;
}
