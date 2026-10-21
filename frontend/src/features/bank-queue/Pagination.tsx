import { ChevronLeft, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { pageCount } from "@/features/bank-queue/params";
import { BANK_QUEUE } from "@/texts";

export function Pagination({
  page,
  count,
  onPage,
}: {
  page: number;
  count: number;
  onPage: (page: number) => void;
}) {
  const pages = pageCount(count);
  return (
    <nav aria-label={BANK_QUEUE.pagination} className="flex flex-wrap items-center gap-3">
      <Button
        variant="secondary"
        size="sm"
        disabled={page <= 1}
        onClick={() => onPage(Math.min(page - 1, pages))}
      >
        <ChevronLeft aria-hidden="true" />
        {BANK_QUEUE.previous}
      </Button>
      <span className="tabular text-sm">
        {BANK_QUEUE.pageOf(page, pages)}
        <span className="text-ink-muted"> · {BANK_QUEUE.total(count)}</span>
      </span>
      <Button
        variant="secondary"
        size="sm"
        disabled={page >= pages}
        onClick={() => onPage(page + 1)}
      >
        {BANK_QUEUE.next}
        <ChevronRight aria-hidden="true" />
      </Button>
    </nav>
  );
}
