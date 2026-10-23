import type * as React from "react";

import { cn } from "@/lib/utils";

/*
 * Fields in the look of the Alfa-Bank design book (core-components «Input»): a filled grey box
 * 48 px high, radius 12, no frame; white with a frame on focus; red tint on error. Native
 * elements on purpose: the core input is always controlled (it keeps its own value state), so
 * react-hook-form's `register`, which writes the value into the DOM, would be wiped on re-render.
 * The visible label stays ours (components/Field.tsx), so `id` and `aria-*` reach the element.
 */
// On the grey page: white with a thin frame; inside a white card or dialog: the book's grey fill.
const fieldBox =
  "w-full rounded-md border border-line-strong bg-surface text-[16px] text-ink transition-colors placeholder:text-ink-muted in-data-[slot=card]:border-transparent in-data-[slot=card]:bg-sunken in-[[role=dialog]]:border-transparent in-[[role=dialog]]:bg-sunken hover:border-ink-muted focus:border-ink-muted focus:bg-surface focus:outline-none disabled:cursor-not-allowed disabled:opacity-60 aria-[invalid=true]:border-status-danger aria-[invalid=true]:bg-status-danger-soft";

function Input({ className, ...props }: React.ComponentProps<"input">) {
  return <input data-slot="input" className={cn(fieldBox, "h-12 px-4", className)} {...props} />;
}

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(fieldBox, "min-h-24 resize-y px-4 py-3", className)}
      {...props}
    />
  );
}

/** Native select: accessible and keyboard-friendly by default, in the book's field look. */
function NativeSelect({ className, ...props }: React.ComponentProps<"select">) {
  return <select data-slot="select" className={cn(fieldBox, "h-12 px-4", className)} {...props} />;
}

export { fieldBox, Input, NativeSelect, Textarea };
