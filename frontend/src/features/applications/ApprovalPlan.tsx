import { useId } from "react";

import type { Schemas } from "@/api/client";
import { Badge } from "@/components/ui/badge";
import { metricTitle, APPROVAL_PLAN as T } from "@/texts";

/**
 * «Как получить одобрение» (XP2): the fewest steps after which the grade would be C, each with
 * its target and the points it adds. Counted by the backend from the stored scorecard.
 */
export function ApprovalPlan({
  plan,
  grade,
}: {
  plan: Schemas["ApprovalPlan"];
  grade: Schemas["Grade"];
}) {
  const titleId = useId();
  return (
    <section aria-labelledby={titleId} className="flex flex-col gap-3">
      <h3 id={titleId} className="m-0 text-base font-semibold">
        {T.title}
      </h3>
      <p className="m-0 text-sm">
        {T.summary(plan.current_total, grade, plan.target_total, plan.target_grade)}
      </p>
      <p className="m-0 text-xs text-ink-muted">{T.gradeHint}</p>
      <ol aria-label={T.title} className="m-0 flex list-none flex-col gap-2 p-0">
        {plan.steps.map((step, index) => (
          <li
            key={step.metric}
            className="grid grid-cols-[28px_1fr] items-start gap-3 rounded-md border border-line p-3"
          >
            <span className="grid size-7 place-items-center rounded-full bg-primary-soft text-sm font-semibold text-primary-ink">
              {index + 1}
            </span>
            <div className="flex min-w-0 flex-col gap-1">
              <div className="flex flex-wrap items-center gap-2">
                <p className="m-0 font-semibold">{metricTitle(step.metric)}</p>
                <Badge variant="success">{T.points(step.points)}</Badge>
              </div>
              <p className="m-0 text-sm">{step.message}</p>
            </div>
          </li>
        ))}
      </ol>
      <p className="m-0 text-xs text-ink-muted">{T.note}</p>
    </section>
  );
}
