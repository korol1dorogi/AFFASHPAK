import { CheckCircle2 } from "lucide-react";
import { toast } from "sonner";

import type { Schemas } from "@/api/client";
import { ReasonList } from "@/components/ReasonList";
import { DemoBadge } from "@/components/States";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { BlockError, BlockSkeleton } from "@/features/applications/BlockState";
import { useCompanyMetrics, useConnectIntegration } from "@/features/company/api";
import { ApiError, errorMessage } from "@/lib/errors";
import { formatDate } from "@/lib/format";
import { BLOCK_STATE, COMPANY } from "@/texts";

const I = COMPANY.integrations;
const M = COMPANY.metrics;
const SOURCES = ["bank_account", "edo"] as const;

/** «Счёт» and «ЭДО» (simulators): what is connected and since when; members can connect. */
export function Integrations({ company }: { company: Schemas["Company"] }) {
  const connect = useConnectIntegration();
  return (
    <Card>
      <div className="flex flex-wrap items-center gap-2">
        <CardTitle className="m-0">{I.title}</CardTitle>
        <DemoBadge />
      </div>
      <p className="m-0 text-sm text-ink-muted">{I.hint}</p>
      <ul aria-label={I.title} className="m-0 flex list-none flex-col gap-2 p-0">
        {SOURCES.map((source) => {
          const since = company.integrations[source];
          return (
            <li
              key={source}
              className="flex flex-wrap items-center gap-3 rounded-md border border-line p-3"
            >
              <span className="min-w-0 flex-1 font-medium">{I.sources[source]}</span>
              {since ? (
                <span className="inline-flex items-center gap-1 text-sm text-status-success">
                  <CheckCircle2 className="size-4" aria-hidden="true" />
                  {I.connected(formatDate(since))}
                </span>
              ) : (
                <Button
                  size="sm"
                  variant="secondary"
                  loading={connect.isPending && connect.variables === source}
                  onClick={() =>
                    connect.mutate(source, {
                      onSuccess: () => toast.success(I.done),
                      onError: (error) => toast.error(errorMessage(error)),
                    })
                  }
                >
                  {I.connect}
                </Button>
              )}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

/** Metrics of the latest snapshot — what the preliminary evaluation will see. */
export function Metrics() {
  const metrics = useCompanyMetrics();
  if (!metrics.data) {
    // 404 — no company: nothing to show; any other failure is said out loud.
    if (metrics.error instanceof ApiError && metrics.error.status === 404) return null;
    return (
      <Card>
        <CardTitle className="m-0">{M.title}</CardTitle>
        {metrics.isError ? (
          <BlockError
            title={BLOCK_STATE.metricsError}
            error={metrics.error}
            onRetry={() => void metrics.refetch()}
          />
        ) : (
          <BlockSkeleton label={BLOCK_STATE.metricsLoading} rows={3} />
        )}
      </Card>
    );
  }
  const { snapshot } = metrics.data;
  return (
    <Card>
      <CardTitle className="m-0">{M.title}</CardTitle>
      <p className="m-0 text-sm text-ink-muted">{snapshot ? M.period(snapshot.period) : M.empty}</p>
      {snapshot ? <ReasonList reasons={metrics.data.metrics} label={M.title} /> : null}
    </Card>
  );
}
