import { AlarmClock, CloudOff } from "lucide-react";
import type { MouseEvent, ReactNode } from "react";
import { Link, useNavigate } from "react-router";

import type { Schemas } from "@/api/client";
import { routes } from "@/app/routes";
import { Skeleton } from "@/components/States";
import { StatusBadge } from "@/components/StatusBadge";
import { OVERDUE_HOURS, PAGE_SIZE } from "@/features/bank-queue/params";
import { formatMoney } from "@/lib/format";
import { cn } from "@/lib/utils";
import { BANK_QUEUE, PRODUCT_KIND } from "@/texts";

type Item = Schemas["BankQueueItem"];

const COLUMNS = BANK_QUEUE.columns;
const th = "h-10 px-3 text-left text-xs font-semibold tracking-[0.02em] text-ink-muted uppercase";
const td = "h-10 px-3 align-middle";

function Head() {
  return (
    <thead className="border-b border-line bg-sunken">
      <tr>
        <th scope="col" className={th}>
          {COLUMNS.id}
        </th>
        <th scope="col" className={th}>
          {COLUMNS.company}
        </th>
        <th scope="col" className={th}>
          {COLUMNS.product}
        </th>
        <th scope="col" className={cn(th, "text-right")}>
          {COLUMNS.amount}
        </th>
        <th scope="col" className={th}>
          {COLUMNS.status}
        </th>
        <th scope="col" className={th}>
          {COLUMNS.grade}
        </th>
        <th scope="col" className={th}>
          {COLUMNS.assignee}
        </th>
        <th scope="col" className={cn(th, "text-right")}>
          {COLUMNS.inStatus}
        </th>
      </tr>
    </thead>
  );
}

function InStatus({ hours }: { hours: number }) {
  if (hours <= OVERDUE_HOURS)
    return <span className="tabular">{BANK_QUEUE.hoursInStatus(hours)}</span>;
  return (
    <span className="inline-flex items-center gap-1 font-semibold text-status-danger">
      <AlarmClock className="size-4" aria-hidden="true" />
      <span className="tabular">{BANK_QUEUE.hoursInStatus(hours)}</span>
      <span className="sr-only">, {BANK_QUEUE.overdue}</span>
    </span>
  );
}

function Row({ item }: { item: Item }) {
  const navigate = useNavigate();
  const to = routes.bankApplication(item.id);
  // The whole row opens the card; the link in the first cell is what keyboard and screen readers use.
  const open = (event: MouseEvent) => {
    if (event.defaultPrevented || (event.target as HTMLElement).closest("a")) return;
    navigate(to);
  };
  return (
    <tr
      onClick={open}
      className="cursor-pointer border-b border-line last:border-b-0 hover:bg-sunken"
    >
      <td className={td}>
        <Link
          to={to}
          aria-label={BANK_QUEUE.openApplication(item.id)}
          className="tabular font-semibold text-primary-ink"
        >
          {item.id}
        </Link>
      </td>
      <td className={cn(td, "max-w-56")}>
        <div className="flex items-center gap-2">
          <div className="flex min-w-0 flex-col leading-4">
            <span className="truncate font-medium">{item.company_name}</span>
            <span className="tabular text-xs text-ink-muted">
              {BANK_QUEUE.inn(item.company_inn)}
            </span>
          </div>
          {item.source_unavailable ? (
            <CloudOff
              role="img"
              aria-label={BANK_QUEUE.sourceUnavailable}
              className="size-4 shrink-0 text-status-action"
            >
              <title>{BANK_QUEUE.sourceUnavailable}</title>
            </CloudOff>
          ) : null}
        </div>
      </td>
      <td className={cn(td, "max-w-40 leading-4")}>
        {item.product_kind ? PRODUCT_KIND[item.product_kind] : BANK_QUEUE.noValue}
      </td>
      <td className={cn(td, "tabular text-right whitespace-nowrap")}>
        {formatMoney(item.requested_amount)}
      </td>
      <td className={td}>
        <StatusBadge status={item.status} />
      </td>
      <td className={cn(td, "font-semibold")}>{item.grade ?? BANK_QUEUE.noValue}</td>
      <td className={cn(td, "max-w-36")}>
        {item.assignee ? (
          <span className="block truncate" title={item.assignee.full_name}>
            {item.assignee.full_name}
          </span>
        ) : (
          <span className="text-ink-muted">{BANK_QUEUE.unassigned}</span>
        )}
      </td>
      <td className={cn(td, "text-right whitespace-nowrap")}>
        <InStatus hours={item.hours_in_status} />
      </td>
    </tr>
  );
}

function Frame({ children, busy, label }: { children: ReactNode; busy?: boolean; label?: string }) {
  return (
    <div className="w-full overflow-x-auto rounded-lg border border-line bg-surface">
      <table
        aria-label={label}
        aria-hidden={label ? undefined : true}
        aria-busy={busy || undefined}
        className={cn("w-full border-collapse text-sm", busy && "opacity-60 transition-opacity")}
      >
        {children}
      </table>
    </div>
  );
}

/** Dense full-width queue table (design.md §4: 40 px rows). Candidate for B1 as `QueueTable`. */
export function QueueTable({ items, busy }: { items: Item[]; busy?: boolean }) {
  return (
    <Frame busy={busy} label={BANK_QUEUE.table}>
      <Head />
      <tbody>
        {items.map((item) => (
          <Row key={item.id} item={item} />
        ))}
      </tbody>
    </Frame>
  );
}

/** Loading state of the same shape as the table. */
export function QueueTableSkeleton() {
  return (
    <div role="status" aria-busy="true" aria-label={BANK_QUEUE.loading}>
      <Frame>
        <Head />
        <tbody>
          {Array.from({ length: PAGE_SIZE / 2 }, (_, row) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: static placeholder rows
            <tr key={row} className="border-b border-line last:border-b-0">
              {Array.from({ length: 8 }, (_, cell) => (
                // biome-ignore lint/suspicious/noArrayIndexKey: static placeholder cells
                <td key={cell} className={td}>
                  <Skeleton className={cell === 1 ? "w-40" : "w-16"} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </Frame>
    </div>
  );
}
