import { Inbox, WifiOff } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { errorMessage } from "@/lib/errors";
import { cn } from "@/lib/utils";

export function EmptyState({
  title,
  text,
  action,
  icon = <Inbox className="size-6" aria-hidden="true" />,
}: {
  title: string;
  text?: string;
  action?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-line-strong bg-surface px-6 py-12 text-center">
      <span className="grid size-12 place-items-center rounded-full bg-primary-soft text-primary-ink">
        {icon}
      </span>
      <p className="m-0 text-lg font-semibold">{title}</p>
      {text ? <p className="m-0 max-w-[46ch] text-ink-muted">{text}</p> : null}
      {action}
    </div>
  );
}

export function ErrorState({
  error,
  onRetry,
  title = "Не получилось загрузить",
}: {
  error: unknown;
  onRetry?: () => void;
  title?: string;
}) {
  return (
    <div
      role="alert"
      className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-line-strong bg-surface px-6 py-12 text-center"
    >
      <span className="grid size-12 place-items-center rounded-full bg-status-danger-soft text-status-danger">
        <WifiOff className="size-6" aria-hidden="true" />
      </span>
      <p className="m-0 text-lg font-semibold">{title}</p>
      <p className="m-0 max-w-[46ch] text-ink-muted">{errorMessage(error)}</p>
      {onRetry ? (
        <Button variant="secondary" onClick={onRetry}>
          Повторить
        </Button>
      ) : null}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("h-4 rounded-sm bg-sunken", className)} />;
}

export function PageSkeleton() {
  return (
    <div role="status" aria-busy="true" aria-label="Загрузка" className="flex flex-col gap-4">
      <Skeleton className="h-8 w-1/3" />
      <Skeleton className="h-24 w-full rounded-lg" />
      <Skeleton className="h-48 w-full rounded-lg" />
    </div>
  );
}

/** «демо» next to anything from simulators or synthetic personas. */
export function DemoBadge() {
  return (
    <span className="inline-flex h-5 items-center rounded-sm bg-status-neutral-soft px-2 text-xs font-semibold tracking-[0.04em] text-status-neutral uppercase">
      демо
    </span>
  );
}

export function PageHeader({
  title,
  subtitle,
  actions,
  children,
}: {
  title: string;
  subtitle?: ReactNode;
  actions?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="m-0 font-display text-[28px] leading-[34px] font-bold tracking-[-0.01em]">
          {title}
        </h1>
        {children}
        {actions ? <div className="ml-auto flex flex-wrap gap-3">{actions}</div> : null}
      </div>
      {subtitle ? <p className="m-0 max-w-[70ch] text-ink-muted">{subtitle}</p> : null}
    </div>
  );
}
