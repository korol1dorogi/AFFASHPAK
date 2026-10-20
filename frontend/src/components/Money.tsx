import { formatMoney, formatRate } from "@/lib/format";
import { cn } from "@/lib/utils";

const SIZE = {
  lg: "font-display text-[32px] leading-9 font-bold",
  md: "font-display text-xl leading-[26px] font-bold",
  inline: "",
} as const;

export function MoneyText({
  value,
  size = "inline",
  className,
}: {
  value: string | null | undefined;
  size?: keyof typeof SIZE;
  className?: string;
}) {
  return <span className={cn("tabular", SIZE[size], className)}>{formatMoney(value)}</span>;
}

export function RateText({
  value,
  size = "inline",
  className,
}: {
  value: string | null | undefined;
  size?: keyof typeof SIZE;
  className?: string;
}) {
  return <span className={cn("tabular", SIZE[size], className)}>{formatRate(value)}</span>;
}
