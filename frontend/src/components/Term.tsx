import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";
import { TERMS, type TermId } from "@/texts";

/**
 * A word with its explanation on hover or keyboard focus: a dotted underline, the help cursor.
 * A focusable span, not a button: terms also sit inside the labels of radio cards and fields.
 */
export function Hint({
  title,
  text,
  children,
  className,
}: {
  title?: string;
  text: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <TooltipPrimitive.Provider delayDuration={150}>
      <TooltipPrimitive.Root>
        <TooltipPrimitive.Trigger asChild>
          {/* biome-ignore lint/a11y/noNoninteractiveTabindex: the trigger of a tooltip must take focus */}
          <span tabIndex={0} className={cn("term", className)}>
            {children}
          </span>
        </TooltipPrimitive.Trigger>
        <TooltipPrimitive.Portal>
          <TooltipPrimitive.Content
            sideOffset={6}
            collisionPadding={16}
            className="z-50 max-w-80 rounded-md bg-ink px-3 py-2 text-sm leading-5 font-normal text-white shadow-pop"
          >
            {title ? <span className="block font-semibold">{title}</span> : null}
            {text}
            <TooltipPrimitive.Arrow className="fill-ink" />
          </TooltipPrimitive.Content>
        </TooltipPrimitive.Portal>
      </TooltipPrimitive.Root>
    </TooltipPrimitive.Provider>
  );
}

/** A banking term with its definition from TERMS; the visible words can be inflected. */
export function Term({ id, children }: { id: TermId; children?: ReactNode }) {
  const term = TERMS[id];
  return (
    <Hint title={term.title} text={term.text}>
      {children ?? term.title}
    </Hint>
  );
}

const MARKED = /\[([^\]]+)\]\(([a-z_]+)\)/g;

/** A text of src/texts with its terms marked as [visible words](termId). */
export function WithTerms({ text }: { text: string }) {
  const parts: ReactNode[] = [];
  let last = 0;
  for (const match of text.matchAll(MARKED)) {
    const [whole, words, id] = match;
    const at = match.index ?? 0;
    parts.push(text.slice(last, at));
    parts.push(
      id && id in TERMS ? (
        <Term key={at} id={id as TermId}>
          {words}
        </Term>
      ) : (
        words
      ),
    );
    last = at + whole.length;
  }
  parts.push(text.slice(last));
  return <>{parts}</>;
}
