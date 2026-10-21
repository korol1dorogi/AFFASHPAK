import { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router";

import { EmptyState, ErrorState, PageHeader } from "@/components/States";
import { Button } from "@/components/ui/button";
import { useBankQueue } from "@/features/bank-queue/api";
import { Pagination } from "@/features/bank-queue/Pagination";
import {
  type QueueFilters as Filters,
  hasActiveFilters,
  parseFilters,
  patchFilters,
  toggleStatus,
  toQuery,
  toSearchParams,
} from "@/features/bank-queue/params";
import { QueueFilters } from "@/features/bank-queue/QueueFilters";
import { QueueTable, QueueTableSkeleton } from "@/features/bank-queue/QueueTable";
import { StatusChips } from "@/features/bank-queue/StatusChips";
import { BANK_QUEUE } from "@/texts";

/** /bank — the queue (B3, F4): counters, filters and ordering in the URL, 20 rows a page. */
export function BankQueuePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const filters = useMemo(() => parseFilters(searchParams), [searchParams]);
  const queue = useBankQueue(useMemo(() => toQuery(filters), [filters]));

  // Chips, selects and pages are history entries («back» returns them); typing is not.
  const update = useCallback(
    (patch: Partial<Filters>, { replace = false } = {}) =>
      setSearchParams((current) => toSearchParams(patchFilters(parseFilters(current), patch)), {
        replace,
      }),
    [setSearchParams],
  );
  const onSearch = useCallback(
    (search: string | undefined) => update({ search }, { replace: true }),
    [update],
  );
  const reset = () => setSearchParams(toSearchParams({ status: [], page: 1 }));
  const canReset = hasActiveFilters(filters);

  const data = queue.data;
  return (
    <div className="flex flex-col gap-4">
      <PageHeader title={BANK_QUEUE.title} subtitle={BANK_QUEUE.subtitle}>
        <span aria-live="polite" className="text-sm text-ink-muted">
          {queue.isPlaceholderData ? BANK_QUEUE.refreshing : ""}
        </span>
      </PageHeader>

      {data ? (
        <StatusChips
          counters={data.counters}
          selected={filters.status}
          onToggle={(status) => update({ status: toggleStatus(filters.status, status) })}
          onClear={() => update({ status: [] })}
        />
      ) : null}

      <QueueFilters
        filters={filters}
        onChange={(patch) => update(patch)}
        onSearch={onSearch}
        onReset={reset}
        canReset={canReset}
      />

      {queue.isPending ? (
        <QueueTableSkeleton />
      ) : !data ? (
        <ErrorState
          title={BANK_QUEUE.error}
          error={queue.error}
          onRetry={() => void queue.refetch()}
        />
      ) : data.results.length === 0 ? (
        <EmptyState
          title={canReset || filters.page > 1 ? BANK_QUEUE.empty : BANK_QUEUE.emptyQueue}
          text={canReset || filters.page > 1 ? BANK_QUEUE.emptyText : undefined}
          action={
            canReset || filters.page > 1 ? (
              <Button variant="secondary" onClick={reset}>
                {BANK_QUEUE.resetFilters}
              </Button>
            ) : null
          }
        />
      ) : (
        <>
          <QueueTable items={data.results} busy={queue.isPlaceholderData} />
          <Pagination page={filters.page} count={data.count} onPage={(page) => update({ page })} />
        </>
      )}
    </div>
  );
}
