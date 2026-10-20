import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import type * as React from "react";

import { cn } from "@/lib/utils";

// Tones are the design system's status groups; colour never travels without a word or icon.
const badgeVariants = cva(
  "inline-flex w-fit shrink-0 items-center gap-1 whitespace-nowrap rounded-sm px-2 py-0.5 text-xs font-medium tracking-[0.02em] [&>svg]:size-3.5 [&>svg]:pointer-events-none",
  {
    variants: {
      variant: {
        action: "bg-status-action-soft text-status-action",
        progress: "bg-status-progress-soft text-status-progress",
        success: "bg-status-success-soft text-status-success",
        danger: "bg-status-danger-soft text-status-danger",
        neutral: "bg-status-neutral-soft text-status-neutral",
        brand: "bg-primary-soft text-primary-ink",
      },
      size: {
        sm: "",
        md: "px-3 py-1 text-sm [&>svg]:size-4",
      },
    },
    defaultVariants: { variant: "neutral", size: "sm" },
  },
);

function Badge({
  className,
  variant,
  size,
  asChild = false,
  ...props
}: React.ComponentProps<"span"> & VariantProps<typeof badgeVariants> & { asChild?: boolean }) {
  const Comp = asChild ? Slot : "span";
  return (
    <Comp
      data-slot="badge"
      className={cn(badgeVariants({ variant, size }), className)}
      {...props}
    />
  );
}

export { Badge, badgeVariants };
