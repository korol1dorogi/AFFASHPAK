import { CircleAlert, CircleCheck, CircleHelp, CircleX, WifiOff } from "lucide-react";

import type { Schemas } from "@/api/client";
import { EmptyState } from "@/components/States";
import { Card, CardTitle } from "@/components/ui/card";
import { formatDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import { BANK_CARD, BANK_TAB, CHECK_SOURCE, CHECK_STATUS } from "@/texts";

type Check = Schemas["Check"];

const T = BANK_CARD.checks;
const SOURCES = Object.keys(CHECK_SOURCE) as Schemas["CheckSource"][];

const LOOK: Record<Check["status"], { Icon: typeof CircleCheck; tone: string }> = {
  ok: { Icon: CircleCheck, tone: "bg-status-success-soft text-status-success" },
  warning: { Icon: CircleAlert, tone: "bg-status-action-soft text-status-action" },
  failed: { Icon: CircleX, tone: "bg-status-danger-soft text-status-danger" },
  unavailable: { Icon: WifiOff, tone: "bg-status-neutral-soft text-status-neutral" },
};

function CheckRow({ source, check }: { source: Schemas["CheckSource"]; check?: Check }) {
  const { Icon, tone } = check
    ? LOOK[check.status]
    : { Icon: CircleHelp, tone: "bg-sunken text-ink-muted" };
  return (
    <li
      data-source={source}
      className="grid grid-cols-[32px_1fr] items-start gap-3 rounded-md border border-line p-4"
    >
      <span className={cn("grid size-8 place-items-center rounded-full", tone)}>
        <Icon className="size-4" aria-hidden="true" />
      </span>
      <div className="flex min-w-0 flex-col gap-1">
        <div className="flex flex-wrap items-baseline gap-x-3">
          <p className="m-0 font-semibold">{CHECK_SOURCE[source]}</p>
          <span className="text-sm font-medium">
            {check ? CHECK_STATUS[check.status] : T.missing}
          </span>
        </div>
        {check?.summary ? <p className="m-0 text-sm">{check.summary}</p> : null}
        {check ? (
          <p className="m-0 text-xs text-ink-muted">
            {T.checkedAt} {formatDateTime(check.checked_at)}
          </p>
        ) : null}
      </div>
    </li>
  );
}

/** The four sources in a fixed order; a source without a result says so instead of vanishing. */
export function ChecksTab({ checks }: { checks: Check[] }) {
  if (checks.length === 0) return <EmptyState title={T.empty} text={T.emptyText} />;
  return (
    <Card>
      <CardTitle>{BANK_TAB.checks}</CardTitle>
      <ul aria-label={T.list} className="m-0 flex list-none flex-col gap-3 p-0">
        {SOURCES.map((source) => (
          <CheckRow
            key={source}
            source={source}
            check={checks.find((check) => check.source === source)}
          />
        ))}
      </ul>
    </Card>
  );
}
