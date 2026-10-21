import { Check, Minus, X } from "lucide-react";

import type { Schemas } from "@/api/client";
import { formatDecimal, formatMoney } from "@/lib/format";
import { cn } from "@/lib/utils";
import { METRIC, type MetricText, metricTitle } from "@/texts";

type Reason = Schemas["Reason"];

function formatValue(value: string | null, format: MetricText["format"] | undefined): string {
  if (value === null) return "нет данных";
  switch (format) {
    case "money":
      return formatMoney(value);
    case "percent":
      return `${formatDecimal(String(Math.round(Number(value) * 100)))} %`;
    case "months":
      return `${formatDecimal(value)} мес`;
    case "days":
      return `${formatDecimal(value)} дн.`;
    case "points":
      return formatDecimal(value);
    default:
      return formatDecimal(value);
  }
}

function mark(reason: Reason) {
  if (reason.value === null && !reason.passed)
    return { tone: "none", Icon: Minus, label: "нет данных" } as const;
  return reason.passed
    ? ({ tone: "pass", Icon: Check, label: "пройдено" } as const)
    : ({ tone: "fail", Icon: X, label: "не пройдено" } as const);
}

const MARK_TONE = {
  pass: "bg-status-success-soft text-status-success",
  fail: "bg-status-danger-soft text-status-danger",
  none: "bg-status-neutral-soft text-status-neutral",
} as const;

/**
 * Reasons of a preliminary evaluation or decision. `client`: plain titles and hints from texts/;
 * `bank`: metric codes and raw values. A null value is «нет данных», never 0.
 */
export function ReasonList({
  reasons,
  variant = "client",
  label = "Причины",
}: {
  reasons: Reason[];
  variant?: "client" | "bank";
  label?: string;
}) {
  if (reasons.length === 0) return null;
  return (
    <ul aria-label={label} className="m-0 flex list-none flex-col gap-2 p-0">
      {reasons.map((reason) => {
        const text = METRIC[reason.metric];
        const { tone, Icon, label: markLabel } = mark(reason);
        const title = variant === "bank" ? reason.metric : metricTitle(reason.metric);
        return (
          <li
            key={`${reason.metric}-${reason.message}`}
            data-passed={reason.passed}
            className="grid grid-cols-[24px_1fr_auto] items-start gap-3 rounded-md border border-line bg-surface p-3"
          >
            <span className={cn("grid size-6 place-items-center rounded-full", MARK_TONE[tone])}>
              <Icon className="size-4" role="img" aria-label={markLabel} />
            </span>
            <div className="min-w-0">
              <p className="m-0 font-semibold">{title}</p>
              <p className="m-0 text-sm text-ink-muted">{reason.message}</p>
            </div>
            <span className="tabular text-right text-sm whitespace-nowrap">
              {reason.value === null && reason.passed ? null : (
                <b
                  className={cn(
                    "font-semibold",
                    reason.value === null && "font-normal text-ink-muted",
                  )}
                >
                  {formatValue(reason.value, text?.format)}
                </b>
              )}
              {reason.threshold !== null ? (
                <span className="block text-ink-muted">
                  порог {formatValue(reason.threshold, text?.format)}
                </span>
              ) : null}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

export function ImprovementList({
  items,
  title = "Что можно улучшить",
}: {
  items: string[];
  title?: string;
}) {
  if (items.length === 0) return null;
  return (
    <div className="flex flex-col gap-3">
      <p className="m-0 font-semibold">{title}</p>
      <ol className="m-0 flex list-none flex-col gap-2 p-0">
        {items.map((item, index) => (
          <li key={item} className="grid grid-cols-[28px_1fr] items-start gap-3">
            <span className="grid size-7 place-items-center rounded-full bg-primary-soft font-display text-sm font-bold text-primary-ink">
              {index + 1}
            </span>
            <span>{item}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}
