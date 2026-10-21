import type { Schemas } from "@/api/client";
import { StatusBadge } from "@/components/StatusBadge";
import { STATUSES } from "@/features/bank-queue/params";
import { cn } from "@/lib/utils";
import { BANK_QUEUE, STATUS } from "@/texts";

type Status = Schemas["ApplicationStatus"];

const chip =
  "inline-flex h-8 items-center gap-2 rounded-md border px-2 text-sm cursor-pointer transition-colors";

/** Status counters (without the status filter) as toggle chips; a click filters by that status. */
export function StatusChips({
  counters,
  selected,
  onToggle,
  onClear,
}: {
  counters: Record<string, number>;
  selected: Status[];
  onToggle: (status: Status) => void;
  onClear: () => void;
}) {
  const shown = STATUSES.filter((status) => status in counters);
  const total = shown.reduce((sum, status) => sum + (counters[status] ?? 0), 0);
  const tone = (pressed: boolean) =>
    pressed
      ? "border-primary bg-primary-soft text-ink"
      : "border-line bg-surface text-ink hover:bg-sunken";

  return (
    <fieldset className="m-0 flex flex-wrap gap-2 border-0 p-0">
      <legend className="sr-only">{BANK_QUEUE.statusFilter}</legend>
      <button
        type="button"
        aria-pressed={selected.length === 0}
        onClick={onClear}
        aria-label={BANK_QUEUE.statusChip(BANK_QUEUE.allStatuses, total)}
        className={cn(chip, tone(selected.length === 0), "px-3 font-medium")}
      >
        {BANK_QUEUE.allStatuses}
        <span className="tabular text-ink-muted">{total}</span>
      </button>
      {shown.map((status) => {
        const pressed = selected.includes(status);
        return (
          <button
            key={status}
            type="button"
            aria-pressed={pressed}
            onClick={() => onToggle(status)}
            aria-label={BANK_QUEUE.statusChip(STATUS[status].label, counters[status] ?? 0)}
            className={cn(chip, tone(pressed))}
          >
            <StatusBadge status={status} />
            <span className="tabular font-medium">{counters[status]}</span>
          </button>
        );
      })}
    </fieldset>
  );
}
