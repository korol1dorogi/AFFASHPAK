import type * as React from "react";

import { cn } from "@/lib/utils";

const fieldBox =
  "w-full rounded-md border border-line-strong bg-surface text-ink placeholder:text-ink-muted disabled:opacity-50 aria-[invalid=true]:border-status-danger";

function Input({ className, ...props }: React.ComponentProps<"input">) {
  return <input data-slot="input" className={cn(fieldBox, "h-11 px-3", className)} {...props} />;
}

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(fieldBox, "min-h-24 px-3 py-2.5 resize-y", className)}
      {...props}
    />
  );
}

/** Native select: accessible and keyboard-friendly by default. */
function NativeSelect({ className, ...props }: React.ComponentProps<"select">) {
  return <select data-slot="select" className={cn(fieldBox, "h-11 px-3", className)} {...props} />;
}

export { fieldBox, Input, NativeSelect, Textarea };
