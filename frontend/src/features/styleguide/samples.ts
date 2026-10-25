import type { Schemas } from "@/api/client";

// Demo data for the styleguide: the figures of scenario 3 and 4 (docs/decision-model.md §8).

export const PRODUCT = {
  code: "working_capital_loan_basic",
  kind: "working_capital_loan",
  name: "Кредит на пополнение оборотных средств",
  description: "Демо-условия.",
  rate_min: "0.2200",
  rate_max: "0.3000",
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

export const REASONS: Schemas["Reason"][] = [
  {
    metric: "max_loan_by_dscr",
    value: "2009314.00",
    threshold: "5300000.00",
    passed: false,
    message: "Денежный поток выдержит не больше этой суммы",
  },
  { metric: "dscr", value: "1.25", threshold: "1.25", passed: true, message: "Запас на платежи" },
  {
    metric: "debt_to_ebitda",
    value: null,
    threshold: "3.5",
    passed: false,
    message: "Отчётности нет — нагрузку оценили по счёту",
  },
];

export const OFFER: Schemas["Offer"] = {
  id: 1,
  product: PRODUCT,
  amount: "2009314.00",
  requested_amount: "5300000.00",
  term_months: 12,
  rate: "0.2400",
  monthly_payment: "189999.92",
  is_counteroffer: true,
  product_changed: false,
  status: "active",
  expires_at: "2026-11-13T10:13:00Z",
  reasons: REASONS.slice(0, 1),
};

export const SCORE: Schemas["Score"] = {
  grade: "C",
  total: 65,
  model_version: "scorecard-2026.10",
  created_at: "2026-10-25T10:00:00Z",
  factors: [
    { name: "dscr", value: "1.80", points: 25, message: "Свободных денег на платежи хватает" },
    { name: "bki_history", value: null, points: 10, message: "Была просрочка до 30 дней" },
    { name: "debt_to_ebitda", value: null, points: 7, message: "Отчётности нет" },
    { name: "revenue_trend", value: "1.05", points: 15, message: "Выручка выросла" },
    {
      name: "counterparty_concentration",
      value: "0.40",
      points: 5,
      message: "Доля покупателя 40 %",
    },
    { name: "business_age_months", value: "36", points: 3, message: "Бизнесу 3 года" },
    {
      name: "transparent_business",
      value: null,
      points: 0,
      message: "Есть налоговая задолженность (демо)",
    },
  ],
};

const at = (minutes: number) => new Date(Date.now() - minutes * 60_000).toISOString();

export const EVENTS: Schemas["ApplicationEvent"][] = [
  {
    id: 1,
    kind: "status_changed",
    from_status: "draft",
    to_status: "submitted",
    actor_kind: "client",
    actor: { id: 1, full_name: "Соколова Марина (демо)" },
    message: "Заявка отправлена в банк",
    is_internal: false,
    created_at: at(40),
  },
  {
    id: 2,
    kind: "consent_given",
    from_status: null,
    to_status: null,
    actor_kind: "client",
    actor: { id: 1, full_name: "Соколова Марина (демо)" },
    message: "Согласие на запрос в БКИ",
    is_internal: false,
    created_at: at(40),
  },
  {
    id: 3,
    kind: "check_completed",
    from_status: null,
    to_status: null,
    actor_kind: "system",
    actor: null,
    message: "Проверки источников пройдены",
    is_internal: false,
    created_at: at(39),
  },
  {
    id: 4,
    kind: "decision",
    from_status: "processing",
    to_status: "offer",
    actor_kind: "system",
    actor: null,
    message: "Банк предлагает другие условия",
    is_internal: false,
    created_at: at(38),
  },
];

export const STATUSES: Schemas["ApplicationStatus"][] = [
  "draft",
  "submitted",
  "processing",
  "manual_review",
  "info_requested",
  "offer",
  "signing",
  "signed",
  "issued",
  "declined",
  "cancelled",
];

// The design tokens of src/index.css (light theme), for the swatches.
export const TOKENS = [
  "paper",
  "surface",
  "sunken",
  "ink",
  "ink-muted",
  "line",
  "line-strong",
  "primary",
  "primary-hover",
  "on-primary",
  "primary-soft",
  "primary-ink",
  "brass",
  "brass-soft",
  "status-action",
  "status-action-soft",
  "status-progress",
  "status-progress-soft",
  "status-success",
  "status-success-soft",
  "status-danger",
  "status-danger-soft",
  "status-neutral",
  "status-neutral-soft",
  "focus",
  "link",
] as const;
