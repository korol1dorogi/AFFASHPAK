import { Check } from "lucide-react";
import { Link } from "react-router";

import { cn } from "@/lib/utils";

export interface Step {
  key: string;
  label: string;
  /** Link for a passed step; absent = not clickable. */
  to?: string;
}

export function Stepper({
  steps,
  current,
  label = "Шаги",
}: {
  steps: Step[];
  current: string;
  label?: string;
}) {
  const currentIndex = steps.findIndex((step) => step.key === current);
  return (
    <ol aria-label={label} className="m-0 flex list-none gap-2 p-0">
      {steps.map((step, index) => {
        const state = index < currentIndex ? "done" : index === currentIndex ? "current" : "todo";
        const content = (
          <>
            <span
              className={cn(
                "block h-1 rounded-full",
                state === "todo" ? "bg-sunken" : "bg-primary",
              )}
            />
            <span
              className={cn(
                "flex items-center gap-1 text-sm font-medium",
                state === "current" && "font-semibold text-ink",
                state === "done" && "text-primary-ink",
                state === "todo" && "text-ink-muted",
              )}
            >
              {state === "done" ? <Check className="size-4" aria-hidden="true" /> : null}
              {step.label}
            </span>
          </>
        );
        return (
          <li
            key={step.key}
            className="flex min-w-0 flex-1 flex-col"
            aria-current={state === "current" ? "step" : undefined}
          >
            {state === "done" && step.to ? (
              <Link to={step.to} className="flex flex-col gap-2 no-underline">
                {content}
              </Link>
            ) : (
              <span className="flex flex-col gap-2">{content}</span>
            )}
          </li>
        );
      })}
    </ol>
  );
}
