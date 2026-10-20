import { cloneElement, type ReactElement, useId } from "react";

import { cn } from "@/lib/utils";

/**
 * Label on top, control, hint or error below. The control gets id, aria-invalid and
 * aria-describedby automatically.
 */
export function Field({
  label,
  hint,
  error,
  children,
  className,
}: {
  label: string;
  hint?: string;
  error?: string;
  children: ReactElement<Record<string, unknown>>;
  className?: string;
}) {
  const id = useId();
  const noteId = `${id}-note`;
  const note = error ?? hint;
  return (
    <div className={cn("flex min-w-0 flex-col gap-1", className)}>
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      {cloneElement(children, {
        id,
        "aria-invalid": error ? true : undefined,
        "aria-describedby": note ? noteId : undefined,
      })}
      {note ? (
        <p
          id={noteId}
          className={cn("m-0 text-sm", error ? "text-status-danger" : "text-ink-muted")}
        >
          {note}
        </p>
      ) : null}
    </div>
  );
}
