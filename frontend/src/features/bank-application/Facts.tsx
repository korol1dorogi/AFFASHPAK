import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/** Label → value pairs of the card, two columns on wide screens. */
export function Facts({
  items,
  className,
}: {
  items: { label: string; value: ReactNode }[];
  className?: string;
}) {
  return (
    <dl className={cn("m-0 grid gap-x-6 gap-y-3 sm:grid-cols-2", className)}>
      {items.map((item) => (
        <div key={item.label} className="flex min-w-0 flex-col gap-0.5">
          <dt className="text-sm text-ink-muted">{item.label}</dt>
          <dd className="m-0 break-words">{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}
