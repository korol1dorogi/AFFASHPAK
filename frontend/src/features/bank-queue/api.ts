import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import type { QueueQuery } from "@/features/bank-queue/params";
import { unwrap } from "@/lib/errors";

export const keys = {
  queue: (query: QueueQuery) => ["bank", "queue", query] as const,
};

/** One page of the bank queue with status counters; polls every 15 s, keeps the old page while the next loads. */
export function useBankQueue(query: QueueQuery) {
  return useQuery({
    queryKey: keys.queue(query),
    queryFn: async () => unwrap(await api.GET("/api/bank/applications", { params: { query } })),
    placeholderData: keepPreviousData,
    refetchInterval: 15_000,
  });
}
