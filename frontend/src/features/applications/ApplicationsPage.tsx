import { useState } from "react";
import { Link } from "react-router";

import type { Schemas } from "@/api/client";
import { routes } from "@/app/routes";
import { MoneyText } from "@/components/Money";
import { EmptyState, ErrorState, PageHeader, PageSkeleton } from "@/components/States";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { useApplications } from "@/features/applications/api";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import { NEED, STATUS } from "@/texts";

const FILTERS = [
  {
    key: "action",
    label: "Нужно действие",
    test: (s: Schemas["ApplicationStatus"]) => STATUS[s].group === "action",
  },
  {
    key: "progress",
    label: "В работе у банка",
    test: (s: Schemas["ApplicationStatus"]) => STATUS[s].group === "progress",
  },
  {
    key: "done",
    label: "Завершённые",
    test: (s: Schemas["ApplicationStatus"]) =>
      ["success", "danger", "neutral"].includes(STATUS[s].group),
  },
  { key: "all", label: "Все", test: () => true },
] as const;

export function ApplicationsPage() {
  const applications = useApplications();
  const [filter, setFilter] = useState<(typeof FILTERS)[number]["key"]>("all");

  if (applications.isPending) return <PageSkeleton />;
  if (applications.isError)
    return <ErrorState error={applications.error} onRetry={() => applications.refetch()} />;

  const active = FILTERS.find((item) => item.key === filter) ?? FILTERS[3];
  const visible = applications.data.filter((item) => active.test(item.status));

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Заявки"
        actions={
          <Button asChild>
            <Link to={routes.match}>Подобрать финансирование</Link>
          </Button>
        }
      />
      {applications.data.length === 0 ? (
        <EmptyState
          title="Заявок пока нет"
          text="Расскажите, зачем бизнесу деньги, и мы подберём подходящий вариант и сумму."
          action={
            <Button asChild>
              <Link to={routes.match}>Подобрать финансирование</Link>
            </Button>
          }
        />
      ) : (
        <>
          <fieldset className="m-0 flex flex-wrap gap-2 border-0 p-0">
            <legend className="sr-only">Фильтр заявок</legend>
            {FILTERS.map((item) => {
              const count = applications.data.filter((app) => item.test(app.status)).length;
              return (
                <button
                  key={item.key}
                  type="button"
                  aria-pressed={filter === item.key}
                  onClick={() => setFilter(item.key)}
                  className={cn(
                    "flex h-8 cursor-pointer items-center gap-2 rounded-full border px-3 text-sm font-medium",
                    filter === item.key
                      ? "border-primary bg-primary-soft text-primary-ink"
                      : "border-line-strong bg-surface text-ink",
                  )}
                >
                  {item.label} <b className="tabular">{count}</b>
                </button>
              );
            })}
          </fieldset>
          <ul className="m-0 flex list-none flex-col gap-3 p-0">
            {visible.map((item) => (
              <li key={item.id}>
                <Link
                  to={routes.application(item.id)}
                  className="flex flex-wrap items-center gap-4 rounded-lg border border-line bg-surface p-4 text-ink no-underline hover:border-line-strong"
                >
                  <span className="min-w-0 flex-[1_1_280px]">
                    <span className="block font-semibold">Заявка № {item.id}</span>
                    <span className="text-sm text-ink-muted">
                      {NEED[item.need_type].title} · {formatDate(item.created_at)}
                    </span>
                  </span>
                  <MoneyText value={item.requested_amount} className="font-semibold" />
                  <StatusBadge status={item.status} />
                </Link>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
