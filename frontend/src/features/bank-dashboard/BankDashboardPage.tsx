import { useQuery } from "@tanstack/react-query";
import { useId } from "react";
import { Link, useSearchParams } from "react-router";

import { api, type Schemas } from "@/api/client";
import { routes } from "@/app/routes";
import { EmptyState, ErrorState, PageHeader, PageSkeleton } from "@/components/States";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { NativeSelect } from "@/components/ui/input";
import { unwrap } from "@/lib/errors";
import { formatDecimal } from "@/lib/format";
import { cn } from "@/lib/utils";
import { EMPTY, STATUS, type StatusGroup, BANK_DASHBOARD as T } from "@/texts";

const PERIODS = [7, 30, 90] as const;

/** B6: where the applications are now, average hours in each status, auto decisions; XP4: SLA. */
export function BankDashboardPage() {
  const [params, setParams] = useSearchParams();
  const periodId = useId();
  const days = PERIODS.find((p) => String(p) === params.get("days")) ?? 30;
  const dashboard = useQuery({
    queryKey: ["bank", "dashboard", days],
    queryFn: async () =>
      unwrap(await api.GET("/api/bank/dashboard", { params: { query: { days } } })),
    refetchInterval: 30_000,
  });
  const header = (
    <PageHeader
      title={T.title}
      subtitle={T.subtitle}
      actions={
        <div className="flex items-center gap-2 text-sm">
          <label htmlFor={periodId}>{T.period}</label>
          <NativeSelect
            id={periodId}
            className="w-36"
            value={String(days)}
            onChange={(event) => setParams({ days: event.target.value })}
          >
            {PERIODS.map((p) => (
              <option key={p} value={p}>
                {T.days(p)}
              </option>
            ))}
          </NativeSelect>
        </div>
      }
    />
  );
  if (dashboard.isPending) return <PageSkeleton />;
  if (dashboard.isError) {
    return (
      <div className="flex flex-col gap-6">
        {header}
        <ErrorState
          title={T.loadError}
          error={dashboard.error}
          onRetry={() => void dashboard.refetch()}
        />
      </div>
    );
  }
  const data = dashboard.data;
  if (data.total_applications === 0) {
    return (
      <div className="flex flex-col gap-6">
        {header}
        <EmptyState
          title={EMPTY.dashboardTitle}
          text={EMPTY.dashboardText}
          action={
            days < 90 ? (
              <Button variant="secondary" onClick={() => setParams({ days: "90" })}>
                {EMPTY.dashboardLonger}
              </Button>
            ) : (
              <Button asChild variant="secondary">
                <Link to={routes.bank}>{EMPTY.toQueue}</Link>
              </Button>
            )
          }
        />
      </div>
    );
  }
  const share = data.auto_decision_share;
  const hours = Object.entries(data.avg_hours_in_status).sort(
    (a, b) => Number(b[1]) - Number(a[1]),
  );
  return (
    <div className="flex flex-col gap-6">
      {header}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card>
          <p className="m-0 text-sm text-ink-muted">{T.total}</p>
          <p className="m-0 font-display text-3xl font-semibold tabular">
            {data.total_applications}
          </p>
        </Card>
        <Card>
          <p className="m-0 text-sm text-ink-muted">{T.autoShare}</p>
          <p className="m-0 font-display text-3xl font-semibold tabular">
            {share === null
              ? "—"
              : `${formatDecimal(String(Math.round(Number(share) * 1000) / 10))} %`}
          </p>
          <p className="m-0 text-xs text-ink-muted">{T.autoShareHint}</p>
        </Card>
        <Card>
          <p className="m-0 text-sm text-ink-muted">{T.issued}</p>
          <p className="m-0 font-display text-3xl font-semibold tabular">
            {data.by_status.find((row) => row.status === "issued")?.count ?? 0}
          </p>
        </Card>
        <OverdueCard data={data} />
      </div>
      <StatusCards data={data} />
      <Card>
        <CardTitle className="m-0">{T.hours}</CardTitle>
        {hours.length === 0 ? (
          <p className="m-0 text-sm text-ink-muted">{T.noData}</p>
        ) : (
          <dl className="m-0 grid gap-x-6 gap-y-2 sm:grid-cols-2">
            {hours.map(([status, value]) => (
              <div key={status} className="flex justify-between gap-3 border-b border-line py-1">
                <dt className="text-sm">
                  {STATUS[status as keyof typeof STATUS]?.label ?? status}
                </dt>
                <dd className="m-0 font-semibold tabular">{T.hoursValue(formatDecimal(value))}</dd>
              </div>
            ))}
          </dl>
        )}
      </Card>
    </div>
  );
}

type Dashboard = Schemas["BankDashboard"];
type Status = Schemas["ApplicationStatus"];
type Row = { key: keyof typeof T.rows; statuses: Status[] };

/*
 * The period's applications by their current status (by_status). Each is counted once, so «В работе
 * сейчас» and «Итоги за период» add up to the period's total; work is grouped by who has to act.
 */
const IN_WORK: { key: keyof typeof T.groups; rows: Row[] }[] = [
  {
    key: "bank",
    rows: [
      { key: "checking", statuses: ["submitted", "processing"] },
      { key: "manual_review", statuses: ["manual_review"] },
    ],
  },
  {
    key: "client",
    rows: [
      { key: "info_requested", statuses: ["info_requested"] },
      { key: "offer", statuses: ["offer"] },
      { key: "signing", statuses: ["signing"] },
    ],
  },
  { key: "payout", rows: [{ key: "signed", statuses: ["signed"] }] },
];

const RESULTS: Row[] = [
  { key: "issued", statuses: ["issued"] },
  { key: "declined", statuses: ["declined"] },
  { key: "cancelled", statuses: ["cancelled"] },
];

// The same colours as the status badges in the queue.
const BAR: Record<StatusGroup, string> = {
  action: "bg-status-action",
  progress: "bg-status-progress",
  success: "bg-status-success",
  danger: "bg-status-danger",
  neutral: "bg-status-neutral",
};

/** «В работе сейчас» and «Итоги за период» side by side. */
function StatusCards({ data }: { data: Dashboard }) {
  const now = new Map(data.by_status.map((row) => [row.status, row.count]));
  const count = (rows: Row[]) =>
    rows.flatMap((row) => row.statuses).reduce((sum, status) => sum + (now.get(status) ?? 0), 0);
  const inWork = count(IN_WORK.flatMap((group) => group.rows));
  const finished = count(RESULTS);
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <StatusCard title={T.inWork} hint={T.inWorkHint} total={inWork}>
        {IN_WORK.map((group) => (
          <section key={group.key} aria-label={T.groups[group.key]} className="flex flex-col gap-3">
            <h3 className="m-0 flex justify-between gap-3 text-sm font-semibold">
              {T.groups[group.key]}
              <span className="tabular">{count(group.rows)}</span>
            </h3>
            <ul className="m-0 flex list-none flex-col gap-3 p-0">
              {group.rows.map((row) => (
                <StatusRow key={row.key} row={row} value={count([row])} total={inWork} />
              ))}
            </ul>
          </section>
        ))}
      </StatusCard>
      <StatusCard title={T.results} hint={T.resultsHint} total={finished}>
        <ul className="m-0 flex list-none flex-col gap-3 p-0">
          {RESULTS.map((row) => (
            <StatusRow key={row.key} row={row} value={count([row])} total={finished} share />
          ))}
        </ul>
      </StatusCard>
    </div>
  );
}

function StatusCard({
  title,
  hint,
  total,
  children,
}: {
  title: string;
  hint: string;
  total: number;
  children: React.ReactNode;
}) {
  const titleId = useId();
  return (
    <Card aria-labelledby={titleId} className="gap-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <CardTitle id={titleId} className="m-0">
            {title}
          </CardTitle>
          <p className="m-0 text-sm text-ink-muted">{hint}</p>
        </div>
        <span className="font-display text-3xl font-semibold tabular">{total}</span>
      </div>
      {children}
    </Card>
  );
}

/** The label and the number side by side, a thin bar below; a zero row is muted. */
function StatusRow({
  row,
  value,
  total,
  share = false,
}: {
  row: Row;
  value: number;
  total: number;
  share?: boolean;
}) {
  const percent = total ? Math.round((value / total) * 100) : 0;
  return (
    <li data-row={row.key} className={cn("flex flex-col gap-1.5", value === 0 && "text-ink-muted")}>
      <span className="flex items-baseline justify-between gap-3 text-sm">
        <span>{T.rows[row.key]}</span>
        <span className="flex items-baseline gap-3 tabular">
          <span className="font-semibold">{value}</span>
          {share ? (
            <span className="w-24 text-right text-ink-muted">{T.share(value, percent)}</span>
          ) : null}
        </span>
      </span>
      <span className="h-1.5 rounded-full bg-sunken" aria-hidden="true">
        <span
          className={cn("block h-1.5 rounded-full", BAR[STATUS[row.statuses[0] as Status].group])}
          style={{ width: `${percent}%` }}
        />
      </span>
    </li>
  );
}

/** XP4: how many applications waiting for the bank are past their status norm, and the norms. */
function OverdueCard({ data }: { data: Dashboard }) {
  const share = data.overdue_share;
  const norms = Object.entries(data.sla_hours).map(([status, hours]) =>
    T.normValue(STATUS[status as keyof typeof STATUS]?.label ?? status, hours),
  );
  return (
    <Card aria-label={T.overdue}>
      <p className="m-0 text-sm text-ink-muted">{T.overdue}</p>
      {share === null ? (
        <p className="m-0 text-sm">{T.overdueNone}</p>
      ) : (
        <p className="m-0 flex items-baseline gap-2">
          <span
            className={cn(
              "font-display text-3xl font-semibold tabular",
              data.overdue_count > 0 && "text-status-danger",
            )}
          >
            {`${formatDecimal(String(Math.round(Number(share) * 1000) / 10))} %`}
          </span>
          <span className="text-sm text-ink-muted tabular">
            {T.overdueValue(data.overdue_count, data.sla_open_count)}
          </span>
        </p>
      )}
      <p className="m-0 text-xs text-ink-muted">
        {T.norms}: {norms.join(", ")}
      </p>
      {data.overdue_count > 0 ? (
        <Link to={`${routes.bank}?overdue=1`} className="link w-fit text-sm">
          {T.overdueLink}
        </Link>
      ) : null}
    </Card>
  );
}
