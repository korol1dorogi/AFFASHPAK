import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BellOff } from "lucide-react";
import { Link } from "react-router";

import { api } from "@/api/client";
import { routes } from "@/app/routes";
import { EmptyState, ErrorState, PageHeader, PageSkeleton } from "@/components/States";
import { Button } from "@/components/ui/button";
import { unwrap } from "@/lib/errors";
import { formatRelative } from "@/lib/format";
import { cn } from "@/lib/utils";
import { NOTIFICATIONS as T } from "@/texts";

const PAGE_SIZE = 50;

/** C8: every status change of the user's applications; updates itself (F5), no email or SMS. */
export function NotificationsPage() {
  const queryClient = useQueryClient();
  const list = useQuery({
    queryKey: ["notifications", { page_size: PAGE_SIZE }],
    queryFn: async () =>
      unwrap(await api.GET("/api/notifications", { params: { query: { page_size: PAGE_SIZE } } })),
    refetchInterval: 20_000,
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["notifications"] });
  const readOne = useMutation({
    mutationFn: async (id: number) =>
      unwrap(
        await api.POST("/api/notifications/{notification_id}/read", {
          params: { path: { notification_id: id } },
        }),
      ),
    onSuccess: refresh,
  });
  const readAll = useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/notifications/read-all")),
    onSuccess: refresh,
  });

  if (list.isPending) return <PageSkeleton />;
  if (list.isError)
    return (
      <ErrorState title={T.loadError} error={list.error} onRetry={() => void list.refetch()} />
    );
  const items = list.data.results;
  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <PageHeader
        title={T.title}
        subtitle={list.data.unread_count ? T.unread(list.data.unread_count) : T.allRead}
        actions={
          list.data.unread_count ? (
            <Button
              variant="secondary"
              onClick={() => readAll.mutate()}
              loading={readAll.isPending}
            >
              {T.readAll}
            </Button>
          ) : null
        }
      />
      {items.length === 0 ? (
        <EmptyState
          icon={<BellOff className="size-6" aria-hidden="true" />}
          title={T.emptyTitle}
          text={T.emptyText}
        />
      ) : (
        <ul aria-label={T.title} className="m-0 flex list-none flex-col gap-2 p-0">
          {items.map((item) => {
            const unread = item.read_at === null;
            return (
              <li
                key={item.id}
                className={cn(
                  "flex flex-wrap items-start gap-3 rounded-md border p-4",
                  unread ? "border-status-action bg-status-action-soft" : "border-line bg-surface",
                )}
              >
                <div className="min-w-0 flex-1">
                  <p className="m-0 font-semibold">
                    {unread ? <span className="sr-only">{T.new}: </span> : null}
                    {item.title}
                  </p>
                  <p className="m-0 text-sm">{item.message}</p>
                  <p className="m-0 text-xs text-ink-muted">{formatRelative(item.created_at)}</p>
                </div>
                <div className="flex gap-2">
                  {item.application_id ? (
                    <Button asChild size="sm" variant="secondary">
                      <Link
                        to={routes.application(item.application_id)}
                        onClick={() => (unread ? readOne.mutate(item.id) : undefined)}
                      >
                        {T.open}
                      </Link>
                    </Button>
                  ) : null}
                  {unread ? (
                    <Button size="sm" variant="ghost" onClick={() => readOne.mutate(item.id)}>
                      {T.markRead}
                    </Button>
                  ) : null}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
