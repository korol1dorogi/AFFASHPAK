import type { Schemas } from "@/api/client";
import { cn } from "@/lib/utils";
import { AMOUNT_SOURCE, SNAPSHOT_FIELD } from "@/texts";

export type AmountSource = keyof typeof AMOUNT_SOURCE;

/**
 * «по выписке», «со слов клиента», «расчёт» or «решение банка» next to an amount (SRC7).
 * A word, not a colour: a screen reader reads it right after the amount.
 */
export function SourceTag({ source, className }: { source: AmountSource; className?: string }) {
  const text = AMOUNT_SOURCE[source];
  return (
    <span
      data-amount-source={source}
      title={text.hint}
      className={cn(
        "ml-1.5 inline-block rounded-sm border border-line px-1 align-middle font-sans text-[11px] leading-4 font-normal tracking-normal whitespace-nowrap text-ink-muted",
        className,
      )}
    >
      {text.label}
    </span>
  );
}

/** A money metric of a Reason: a snapshot field is from the statement, anything else is counted. */
export function metricSource(metric: string): AmountSource {
  return metric in SNAPSHOT_FIELD ? "statement" : "calc";
}

/** Snapshot amounts: typed in by hand is the client's word, everything else is the statement. */
export function snapshotSource(source: Schemas["SnapshotSource"]): AmountSource {
  return source === "manual" ? "client" : "statement";
}

const OFFER_OUTCOMES = new Set(["offer", "counteroffer", "alternative_product"]);

/**
 * An offer amount: counted by an automatic decision, typed in by an officer. The offer comes from
 * the newest decision with an offer outcome; none known — the automatic one.
 */
export function offerAmountSource(decisions: Schemas["Decision"][]): AmountSource {
  const made = decisions
    .filter((decision) => OFFER_OUTCOMES.has(decision.outcome))
    .sort((a, b) => b.created_at.localeCompare(a.created_at))[0];
  return made?.decided_by === "officer" ? "officer" : "calc";
}
