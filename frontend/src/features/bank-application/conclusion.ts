import type { Schemas } from "@/api/client";

type Decision = Schemas["Decision"];
type Event = Schemas["ApplicationEvent"];
type Reason = Schemas["Reason"];

/** The system handed the application to an officer instead of a verdict. */
const HANDOFF: ReadonlySet<Decision["outcome"]> = new Set(["manual_review", "info_requested"]);
const OFFER_LIKE: ReadonlySet<Decision["outcome"]> = new Set([
  "offer",
  "counteroffer",
  "alternative_product",
]);
/** Reasons of an auto decision that carry the amount the system allows (decision-model.md §5). */
const AMOUNT_LIMITS: ReadonlySet<string> = new Set([
  "max_loan_by_dscr",
  "overdraft_limit",
  "factoring_advance",
  "working_capital_need",
]);
/** The decision and its journal event are written in one transaction: seconds apart at most. */
const EVENT_WINDOW_MS = 60_000;

export function chronological(decisions: Decision[]): Decision[] {
  return [...decisions].sort((a, b) => a.created_at.localeCompare(b.created_at));
}

const DECIMAL_RE = /^(\d+)(?:\.(\d+))?$/;

/**
 * Compares two non-negative decimal strings without floats: −1, 0, 1; null if either is not a
 * decimal. Only a comparison — no arithmetic with money on the frontend.
 */
export function compareDecimal(a: string, b: string): number | null {
  const left = DECIMAL_RE.exec(a.trim());
  const right = DECIMAL_RE.exec(b.trim());
  if (!left || !right) return null;
  const intA = (left[1] ?? "0").replace(/^0+(?=\d)/, "");
  const intB = (right[1] ?? "0").replace(/^0+(?=\d)/, "");
  if (intA.length !== intB.length) return intA.length < intB.length ? -1 : 1;
  if (intA !== intB) return intA < intB ? -1 : 1;
  const width = Math.max(left[2]?.length ?? 0, right[2]?.length ?? 0);
  const fracA = (left[2] ?? "").padEnd(width, "0");
  const fracB = (right[2] ?? "").padEnd(width, "0");
  if (fracA === fracB) return 0;
  return fracA < fracB ? -1 : 1;
}

/**
 * Who of the bank made an officer decision. The contract's Decision has no officer, so the name
 * comes from the journal: a bank event of the same action (a decision, or an info request for
 * `info_requested`) closest in time. Null — no such event, the caller says «Сотрудник банка».
 */
export function officerName(decision: Decision, events: Event[]): string | null {
  const kind: Event["kind"] = decision.outcome === "info_requested" ? "info_requested" : "decision";
  const at = Date.parse(decision.created_at);
  let best: { name: string; distance: number } | null = null;
  for (const event of events) {
    if (event.kind !== kind || event.actor_kind !== "bank" || !event.actor) continue;
    const distance = Math.abs(Date.parse(event.created_at) - at);
    if (distance > EVENT_WINDOW_MS) continue;
    if (!best || distance < best.distance) best = { name: event.actor.full_name, distance };
  }
  return best?.name ?? null;
}

export type OfficerVerdict =
  /** The system made no verdict and passed the application on; `cause` — its failed reason. */
  | { kind: "handoff"; auto: Decision; cause: Reason | null }
  /** The system's verdict was different. */
  | { kind: "override_outcome"; auto: Decision }
  /** The officer approved more than the system allows. */
  | { kind: "override_amount"; auto: Decision; amount: string; limit: Reason }
  /** The officer agreed with the system's verdict, or there was nothing to compare with. */
  | { kind: "plain" };

function amountOverLimit(auto: Decision, amount: string): Reason | null {
  for (const reason of auto.reasons) {
    if (!AMOUNT_LIMITS.has(reason.metric) || reason.value === null) continue;
    if (compareDecimal(amount, reason.value) === 1) return reason;
  }
  return null;
}

/**
 * How an officer decision relates to the system's last preliminary evaluation before it:
 * a handoff (the system asked for an officer) or an override (the system had a verdict and the
 * officer decided otherwise, or approved above the amount it allows). Amounts are checked only for
 * the decision behind the current offer — the contract keeps no terms of older ones.
 */
export function classifyOfficerDecision(
  decision: Decision,
  decisions: Decision[],
  offer: Schemas["Offer"] | null,
): OfficerVerdict {
  const ordered = chronological(decisions);
  const index = ordered.findIndex((item) => item.id === decision.id);
  const auto = ordered
    .slice(0, index)
    .reverse()
    .find((item) => item.decided_by === "auto");
  if (!auto) return { kind: "plain" };

  const latestOffer = [...ordered].reverse().find((item) => OFFER_LIKE.has(item.outcome));
  if (offer && latestOffer?.id === decision.id) {
    const limit = amountOverLimit(auto, offer.amount);
    if (limit) return { kind: "override_amount", auto, amount: offer.amount, limit };
  }
  if (HANDOFF.has(auto.outcome)) {
    return { kind: "handoff", auto, cause: auto.reasons.find((reason) => !reason.passed) ?? null };
  }
  if (auto.outcome !== decision.outcome) return { kind: "override_outcome", auto };
  return { kind: "plain" };
}
