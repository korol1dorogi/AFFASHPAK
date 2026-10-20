import { type ComponentProps, useEffect, useState } from "react";

import { fieldBox } from "@/components/ui/input";
import { formatMoney, formatMoneyInput, parseMoneyInput } from "@/lib/format";
import { cn } from "@/lib/utils";

type Props = Omit<ComponentProps<"input">, "value" | "onChange" | "type"> & {
  /** API money string ("5300000.00") or "" when empty. */
  value: string;
  /** Called with the API string, "" when cleared, or null while the text is not a valid amount. */
  onValueChange: (value: string | null) => void;
  suffix?: string;
};

/** Amount input: groups digits while typing and hands the API a decimal string — never a float. */
export function MoneyInput({ value, onValueChange, suffix = "₽", className, ...props }: Props) {
  const [text, setText] = useState(() => (value ? formatMoney(value, { currency: false }) : ""));

  useEffect(() => {
    if (value === "") return;
    const current = parseMoneyInput(text);
    if (current !== value) setText(formatMoney(value, { currency: false }));
  }, [value, text]);

  return (
    <span
      className={cn(
        fieldBox,
        "flex h-11 items-center gap-2 px-3 focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-focus",
        className,
      )}
    >
      <input
        {...props}
        inputMode="decimal"
        autoComplete="off"
        className="tabular min-w-0 flex-1 bg-transparent outline-none"
        value={text}
        onChange={(event) => {
          const next = formatMoneyInput(event.target.value);
          setText(next);
          onValueChange(next === "" ? "" : parseMoneyInput(next));
        }}
      />
      <span className="text-ink-muted" aria-hidden="true">
        {suffix}
      </span>
    </span>
  );
}
