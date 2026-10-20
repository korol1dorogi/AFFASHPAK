import { CircleAlert, CircleCheck, CircleX, Clock } from "lucide-react";
import type { ReactNode } from "react";

import type { Schemas } from "@/api/client";
import { cn } from "@/lib/utils";
import { STATUS } from "@/texts";

const TONE = {
  action: { box: "bg-status-action-soft", icon: "text-status-action", Icon: CircleAlert },
  progress: { box: "bg-status-progress-soft", icon: "text-status-progress", Icon: Clock },
  success: { box: "bg-status-success-soft", icon: "text-status-success", Icon: CircleCheck },
  danger: { box: "bg-status-danger-soft", icon: "text-status-danger", Icon: CircleX },
  neutral: { box: "bg-sunken", icon: "text-ink-muted", Icon: CircleX },
} as const;

/** «Что это значит / что дальше» under the application header — always first on the page. */
export function NextStep({
  status,
  title,
  children,
  action,
}: {
  status: Schemas["ApplicationStatus"];
  /** Overrides the status meaning, e.g. «Банк предлагает другие условия». */
  title?: string;
  /** Extra line under the text (deadline, who can act). */
  children?: ReactNode;
  /** The main action button, if any. */
  action?: ReactNode;
}) {
  const text = STATUS[status];
  const tone = TONE[text.group];
  return (
    <div
      role="status"
      aria-live="polite"
      className={cn("flex flex-wrap items-start gap-4 rounded-lg p-6", tone.box)}
    >
      <tone.Icon className={cn("mt-0.5 size-5 shrink-0", tone.icon)} aria-hidden="true" />
      <div className="flex min-w-0 flex-1 basis-80 flex-col gap-1">
        <p className="m-0 font-semibold">{title ?? text.meaning}</p>
        <p className="m-0">{text.next}</p>
        {children}
      </div>
      {action}
    </div>
  );
}
