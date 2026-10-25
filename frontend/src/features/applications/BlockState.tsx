import { Skeleton } from "@/components/States";
import { Button } from "@/components/ui/button";
import { errorMessage } from "@/lib/errors";
import { BLOCK_STATE } from "@/texts";

/** Loading of a block inside a screen: rows of the block's own shape, announced once. */
export function BlockSkeleton({ label, rows = 2 }: { label: string; rows?: number }) {
  return (
    <div role="status" aria-busy="true" aria-label={label} className="flex flex-col gap-3">
      {Array.from({ length: rows }, (_, row) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: static placeholder rows
        <Skeleton key={row} className="h-9 w-full rounded-md" />
      ))}
    </div>
  );
}

/** A block that failed to load: what happened (the server's text) and «Повторить». */
export function BlockError({
  title,
  error,
  onRetry,
}: {
  title: string;
  error: unknown;
  onRetry: () => void;
}) {
  return (
    <div role="alert" className="flex flex-col items-start gap-2 text-sm">
      <p className="m-0 font-semibold text-status-danger">{title}</p>
      <p className="m-0">{errorMessage(error)}</p>
      <Button variant="secondary" size="sm" onClick={onRetry}>
        {BLOCK_STATE.retry}
      </Button>
    </div>
  );
}
