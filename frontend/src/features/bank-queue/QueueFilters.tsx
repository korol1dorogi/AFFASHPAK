import { Search } from "lucide-react";
import { type ReactNode, useEffect, useId, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input, NativeSelect } from "@/components/ui/input";
import {
  DEFAULT_ORDERING,
  type QueueFilters as Filters,
  GRADES,
  HOUR_PRESETS,
  ORDERINGS,
  PRODUCT_KINDS,
} from "@/features/bank-queue/params";
import { BANK_QUEUE, PRODUCT_KIND, QUEUE_ORDERING } from "@/texts";

export const SEARCH_DELAY_MS = 400;

function LabeledField({ label, children }: { label: string; children: (id: string) => ReactNode }) {
  const id = useId();
  return (
    <div className="flex min-w-44 flex-1 flex-col gap-1">
      <label htmlFor={id} className="text-sm font-medium text-ink-muted">
        {label}
      </label>
      {children(id)}
    </div>
  );
}

/** Typing stays local; the URL gets the trimmed text once typing pauses. */
function SearchField({
  value,
  onSearch,
}: {
  value: string | undefined;
  onSearch: (search: string | undefined) => void;
}) {
  const [draft, setDraft] = useState(value ?? "");

  // The URL changed from outside (reset, «back»): show what it says.
  useEffect(() => {
    setDraft((current) => (current.trim() === (value ?? "") ? current : (value ?? "")));
  }, [value]);

  useEffect(() => {
    const next = draft.trim();
    if (next === (value ?? "")) return;
    const timer = setTimeout(() => onSearch(next || undefined), SEARCH_DELAY_MS);
    return () => clearTimeout(timer);
  }, [draft, value, onSearch]);

  return (
    <LabeledField label={BANK_QUEUE.search}>
      {(id) => (
        <div className="relative">
          <Search
            aria-hidden="true"
            className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-ink-muted"
          />
          <Input
            id={id}
            type="search"
            maxLength={100}
            value={draft}
            placeholder={BANK_QUEUE.searchPlaceholder}
            onChange={(event) => setDraft(event.target.value)}
            className="h-10 pl-9"
          />
        </div>
      )}
    </LabeledField>
  );
}

/** Filters and ordering of the queue; every change goes to the URL via onChange. */
export function QueueFilters({
  filters,
  onChange,
  onSearch,
  onReset,
  canReset,
}: {
  filters: Filters;
  onChange: (patch: Partial<Filters>) => void;
  onSearch: (search: string | undefined) => void;
  onReset: () => void;
  canReset: boolean;
}) {
  const hours = filters.min_hours_in_status;
  const hourOptions: number[] =
    hours === undefined || (HOUR_PRESETS as readonly number[]).includes(hours)
      ? [...HOUR_PRESETS]
      : [...HOUR_PRESETS, hours].sort((a, b) => a - b);

  return (
    <section aria-label={BANK_QUEUE.filters} className="flex flex-wrap items-end gap-3">
      <div className="flex min-w-60 flex-[2_1_240px]">
        <SearchField value={filters.search} onSearch={onSearch} />
      </div>
      <LabeledField label={BANK_QUEUE.product}>
        {(id) => (
          <NativeSelect
            id={id}
            className="h-10"
            value={filters.product_kind ?? ""}
            onChange={(event) =>
              onChange({
                product_kind: (event.target.value || undefined) as Filters["product_kind"],
              })
            }
          >
            <option value="">{BANK_QUEUE.allProducts}</option>
            {PRODUCT_KINDS.map((kind) => (
              <option key={kind} value={kind}>
                {PRODUCT_KIND[kind]}
              </option>
            ))}
          </NativeSelect>
        )}
      </LabeledField>
      <LabeledField label={BANK_QUEUE.grade}>
        {(id) => (
          <NativeSelect
            id={id}
            className="h-10"
            value={filters.grade ?? ""}
            onChange={(event) =>
              onChange({ grade: (event.target.value || undefined) as Filters["grade"] })
            }
          >
            <option value="">{BANK_QUEUE.anyGrade}</option>
            {GRADES.map((grade) => (
              <option key={grade} value={grade}>
                {grade}
              </option>
            ))}
          </NativeSelect>
        )}
      </LabeledField>
      <LabeledField label={BANK_QUEUE.assignee}>
        {(id) => (
          <NativeSelect
            id={id}
            className="h-10"
            value={filters.assignee ?? ""}
            onChange={(event) => onChange({ assignee: event.target.value || undefined })}
          >
            <option value="">{BANK_QUEUE.assigneeAll}</option>
            <option value="me">{BANK_QUEUE.assigneeMe}</option>
            <option value="none">{BANK_QUEUE.assigneeNone}</option>
            {/* A link with an employee id keeps working; its name is not in the contract. */}
            {filters.assignee && !["me", "none"].includes(filters.assignee) ? (
              <option value={filters.assignee}>{BANK_QUEUE.assigneeId(filters.assignee)}</option>
            ) : null}
          </NativeSelect>
        )}
      </LabeledField>
      <LabeledField label={BANK_QUEUE.minHours}>
        {(id) => (
          <NativeSelect
            id={id}
            className="h-10"
            value={hours === undefined ? "" : String(hours)}
            onChange={(event) =>
              onChange({
                min_hours_in_status: event.target.value ? Number(event.target.value) : undefined,
              })
            }
          >
            <option value="">{BANK_QUEUE.anyHours}</option>
            {hourOptions.map((option) => (
              <option key={option} value={option}>
                {BANK_QUEUE.moreThanHours(option)}
              </option>
            ))}
          </NativeSelect>
        )}
      </LabeledField>
      <LabeledField label={BANK_QUEUE.ordering}>
        {(id) => (
          <NativeSelect
            id={id}
            className="h-10"
            value={filters.ordering ?? DEFAULT_ORDERING}
            onChange={(event) =>
              onChange({
                ordering:
                  event.target.value === DEFAULT_ORDERING
                    ? undefined
                    : (event.target.value as Filters["ordering"]),
              })
            }
          >
            {ORDERINGS.map((ordering) => (
              <option key={ordering} value={ordering}>
                {QUEUE_ORDERING[ordering]}
              </option>
            ))}
          </NativeSelect>
        )}
      </LabeledField>
      {canReset ? (
        <Button variant="ghost" onClick={onReset}>
          {BANK_QUEUE.resetFilters}
        </Button>
      ) : null}
    </section>
  );
}
