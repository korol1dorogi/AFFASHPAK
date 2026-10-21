import { useQuery } from "@tanstack/react-query";
import { useId } from "react";
import { useSearchParams } from "react-router";

import { api } from "@/api/client";
import { ErrorState, PageHeader, PageSkeleton } from "@/components/States";
import { Card, CardTitle } from "@/components/ui/card";
import { NativeSelect } from "@/components/ui/input";
import { unwrap } from "@/lib/errors";
import { formatDecimal } from "@/lib/format";
import { STATUS, BANK_DASHBOARD as T } from "@/texts";

const PERIODS = [7, 30, 90] as const;

/** B6: pipeline funnel, average hours in each status, share of automatic decisions. */
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
  const top = Math.max(1, ...data.funnel.map((row) => row.count));
  const share = data.auto_decision_share;
  const hours = Object.entries(data.avg_hours_in_status).sort(
    (a, b) => Number(b[1]) - Number(a[1]),
  );
  return (
    <div className="flex flex-col gap-6">
      {header}
      <div className="grid gap-4 md:grid-cols-3">
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
            {data.funnel.find((row) => row.stage === "issued")?.count ?? 0}
          </p>
        </Card>
      </div>
      <Card>
        <CardTitle className="m-0">{T.funnel}</CardTitle>
        <ul aria-label={T.funnel} className="m-0 flex list-none flex-col gap-2 p-0">
          {data.funnel.map((row) => (
            <li key={row.stage} className="grid grid-cols-[200px_1fr_56px] items-center gap-3">
              <span className="text-sm">{STATUS[row.stage].label}</span>
              <span className="h-3 rounded-full bg-sunken" aria-hidden="true">
                <span
                  className="block h-3 rounded-full bg-primary"
                  style={{ width: `${(row.count / top) * 100}%` }}
                />
              </span>
              <span className="text-right font-semibold tabular">{row.count}</span>
            </li>
          ))}
        </ul>
      </Card>
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
