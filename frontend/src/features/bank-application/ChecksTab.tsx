import {
  CircleAlert,
  CircleCheck,
  CircleHelp,
  CircleX,
  EyeOff,
  SearchX,
  ShieldOff,
  WifiOff,
} from "lucide-react";

import type { Schemas } from "@/api/client";
import { Facts } from "@/components/Facts";
import { EmptyState } from "@/components/States";
import { Badge } from "@/components/ui/badge";
import { Card, CardTitle } from "@/components/ui/card";
import { type CheckFact, checkFacts, checkMeaning } from "@/features/bank-application/checkFacts";
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
  not_found: { Icon: SearchX, tone: "bg-status-danger-soft text-status-danger" },
  // No data is not «bad» (SRC2): the same neutral tone as an outage.
  restricted: { Icon: EyeOff, tone: "bg-status-neutral-soft text-status-neutral" },
  consent_missing: { Icon: ShieldOff, tone: "bg-status-neutral-soft text-status-neutral" },
};

function FactValue({ fact }: { fact: CheckFact }) {
  const value = Array.isArray(fact.value) ? (
    <ul className="m-0 flex list-none flex-col gap-1 p-0">
      {fact.value.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  ) : (
    fact.value
  );
  if (!fact.risk) return value;
  return (
    <span className="inline-flex flex-wrap items-center gap-2 font-medium text-status-danger">
      {value}
      <Badge variant="danger">{T.risk}</Badge>
    </span>
  );
}

/** SRC6: the source's answer with a label for every field — no keys, no codes. */
function SourceFacts({ check }: { check: Check }) {
  const facts = checkFacts(check);
  if (facts.length === 0) return null;
  return (
    <div className="mt-1 flex flex-col gap-2">
      <p className="m-0 text-sm font-medium">{T.facts}</p>
      <Facts
        className="text-sm"
        items={facts.map((fact) => ({ label: fact.label, value: <FactValue fact={fact} /> }))}
      />
    </div>
  );
}

/** SRC4: when the answer came, which simulator answered and the sha256 of its answer. */
function Provenance({ check }: { check: Check }) {
  const P = T.provenance;
  if (!check.response_sha256) return <p className="m-0 text-xs text-ink-muted">{P.none}</p>;
  return (
    <div className="mt-1 flex flex-col gap-1 rounded-md bg-sunken p-2 text-xs">
      <p className="m-0 font-medium">{P.title}</p>
      <dl className="m-0 flex flex-col gap-1">
        <div className="flex flex-wrap gap-x-2">
          <dt className="text-ink-muted">{P.receivedAt}</dt>
          <dd className="m-0">{formatDateTime(check.received_at)}</dd>
        </div>
        <div className="flex flex-wrap gap-x-2">
          <dt className="text-ink-muted">{P.version}</dt>
          <dd className="m-0">{check.simulator_version ?? "—"}</dd>
        </div>
        <div className="flex flex-wrap gap-x-2">
          <dt className="text-ink-muted">{P.sha256}</dt>
          <dd className="m-0 min-w-0 font-mono break-all">{check.response_sha256}</dd>
        </div>
      </dl>
    </div>
  );
}

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
        {check ? <p className="m-0 text-sm text-ink-muted">{checkMeaning(check)}</p> : null}
        {check ? (
          <p className="m-0 text-xs text-ink-muted">
            {T.checkedAt} {formatDateTime(check.checked_at)}
          </p>
        ) : null}
        {check ? <SourceFacts check={check} /> : null}
        {check ? <Provenance check={check} /> : null}
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
