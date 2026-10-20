import { Building2, Check, CircleCheck, FileText, PenLine } from "lucide-react";

import type { Schemas } from "@/api/client";
import { formatRelative } from "@/lib/format";
import { cn } from "@/lib/utils";
import { STATUS } from "@/texts";

type Event = Schemas["ApplicationEvent"];

const ACTOR = { client: "Клиент", bank: "Банк", system: "Система" } as const;

function title(event: Event): string {
  if (event.kind === "comment") return "Внутренний комментарий";
  if (event.kind === "document_uploaded") return "Документ загружен";
  if (event.kind === "info_requested") return "Банк просит уточнить данные";
  if (event.kind === "info_responded") return "Ответ на запрос банка";
  if (event.kind === "assigned") return "Заявку взял сотрудник банка";
  if (event.to_status) return STATUS[event.to_status].label;
  return event.message;
}

function dot(event: Event) {
  if (event.to_status === "issued" || event.to_status === "signed") {
    return { tone: "bg-status-success-soft text-status-success", Icon: CircleCheck };
  }
  if (event.kind === "document_uploaded")
    return { tone: "bg-sunken text-ink-muted", Icon: FileText };
  if (event.actor_kind === "client")
    return { tone: "bg-status-action-soft text-status-action", Icon: PenLine };
  if (event.actor_kind === "bank")
    return { tone: "bg-status-progress-soft text-status-progress", Icon: Building2 };
  return { tone: "bg-sunken text-ink-muted", Icon: Check };
}

/** What happened to the application and who did it. Internal bank events only with showInternal. */
export function StatusTimeline({
  events,
  showInternal = false,
}: {
  events: Event[];
  showInternal?: boolean;
}) {
  const visible = showInternal ? events : events.filter((event) => !event.is_internal);
  if (visible.length === 0) {
    return <p className="m-0 text-sm text-ink-muted">Событий пока нет</p>;
  }
  return (
    <ol aria-label="История заявки" className="m-0 flex list-none flex-col p-0">
      {visible.map((event, index) => {
        const { tone, Icon } = dot(event);
        const last = index === visible.length - 1;
        const heading = title(event);
        return (
          <li key={event.id} className="relative grid grid-cols-[28px_1fr] gap-3 pb-4">
            {last ? null : (
              <span
                className="absolute top-7 bottom-0 left-[13px] w-0.5 bg-line"
                aria-hidden="true"
              />
            )}
            <span className={cn("grid size-7 place-items-center rounded-full", tone)}>
              <Icon className="size-4" aria-hidden="true" />
            </span>
            <div className="min-w-0">
              <p className="m-0 font-semibold">{heading}</p>
              <p className="m-0 text-xs text-ink-muted">
                {event.actor?.full_name ?? ACTOR[event.actor_kind]} ·{" "}
                {formatRelative(event.created_at)}
                {event.is_internal ? " · видно только банку" : ""}
              </p>
              {event.message && event.message !== heading ? (
                <p
                  className={cn(
                    "m-0 mt-1 text-sm",
                    event.is_internal && "rounded-sm bg-sunken px-3 py-2",
                  )}
                >
                  {event.message}
                </p>
              ) : null}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
