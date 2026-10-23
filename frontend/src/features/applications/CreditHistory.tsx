import { useId } from "react";

import type { Schemas } from "@/api/client";
import { CREDIT_HISTORY as T } from "@/texts";

type Reason = Schemas["Reason"];

function whole(value: string | null): number | null {
  if (value === null) return null;
  const number = Number(value);
  return Number.isFinite(number) ? Math.round(number) : null;
}

/** apps/scoring/factors.py: a current overdue under the stop limit keeps the factor's value as the
 * past one and says «Сейчас есть просрочка…» in the message. */
function isCurrent(reason: Reason): boolean {
  return reason.message.startsWith("Сейчас есть просрочка");
}

/** What the bureau showed, in words; null — a clean history or no bureau data: nothing to explain. */
export function creditHistoryFinding(reasons: Reason[]): string | null {
  const stop = reasons.find((reason) => reason.metric === "bki_current_overdue_days");
  const stopDays = whole(stop?.value ?? null);
  if (stop && stopDays !== null && stopDays > 0) {
    return T.currentStop(stopDays, whole(stop.threshold) ?? 0);
  }
  const history = reasons.find((reason) => reason.metric === "bki_history");
  const past = whole(history?.value ?? null);
  if (!history || past === null) return null;
  // The factor's value is the past overdue; a current one (≤ the stop limit) is in its message.
  if (isCurrent(history)) return T.current(history.message);
  if (past <= 0) return null;
  const limit = whole(history.threshold) ?? 0;
  return history.passed ? T.pastWithin(past, limit) : T.pastOver(past, limit);
}

/**
 * BKI1: when the credit history weighed on the decision, say what the bank saw, where it comes
 * from and what the client can do — the bank does not send them to «разбирайтесь сами» (L01).
 */
export function CreditHistory({
  reasons,
  finished,
}: {
  reasons: Reason[];
  /** The application is closed (declined, cancelled): the advice is for the next one. */
  finished: boolean;
}) {
  const titleId = useId();
  const finding = creditHistoryFinding(reasons);
  if (finding === null) return null;
  const current = reasons.some(
    (reason) =>
      (reason.metric === "bki_current_overdue_days" && Number(reason.value) > 0) ||
      (reason.metric === "bki_history" && isCurrent(reason)),
  );
  const steps = [...(current ? [T.payCurrent] : []), ...T.steps, T.attach(finished)];
  return (
    <section
      aria-labelledby={titleId}
      className="flex flex-col gap-3 rounded-md border border-line bg-sunken p-4"
    >
      <h3 id={titleId} className="m-0 text-base font-semibold">
        {T.title}
      </h3>
      <p className="m-0">{finding}</p>
      <p className="m-0 text-sm text-ink-muted">{T.source}</p>
      <p className="m-0 font-semibold">{T.stepsTitle}</p>
      <ol aria-label={T.stepsTitle} className="m-0 flex list-none flex-col gap-2 p-0">
        {steps.map((step, index) => (
          <li key={step} className="grid grid-cols-[28px_1fr] items-start gap-3">
            <span className="grid size-7 place-items-center rounded-full bg-primary-soft text-sm font-semibold text-primary-ink">
              {index + 1}
            </span>
            <span className="text-sm">{step}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}
