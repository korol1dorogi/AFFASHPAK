import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type Schemas } from "@/api/client";
import { isConflict, unwrap } from "@/lib/errors";

export type BankApplicationDetail = Schemas["BankApplicationDetail"];

export const keys = {
  one: (id: number) => ["bank", "application", id] as const,
  products: ["products"] as const,
};

const path = (id: number) => ({ params: { path: { id } } });

/** The whole card for a bank employee; polls like the queue so client answers show up (F5). */
export function useBankApplication(id: number, { enabled = true } = {}) {
  return useQuery({
    queryKey: keys.one(id),
    enabled,
    queryFn: async () => unwrap(await api.GET("/api/bank/applications/{id}", path(id))),
    refetchInterval: 15_000,
  });
}

export function useProducts() {
  return useQuery({
    queryKey: keys.products,
    queryFn: async () => unwrap(await api.GET("/api/products")),
    staleTime: 5 * 60_000,
  });
}

/** Internal journal comment. The answer is the new event, not the card, so the card is re-read. */
export function useComment(id: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (message: string) =>
      unwrap(
        await api.POST("/api/bank/applications/{id}/comments", { ...path(id), body: { message } }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.one(id) }),
  });
}

/**
 * Employee actions answer with the whole card: put it into the cache and refresh the queue.
 * 409 (version_conflict, invalid_transition): someone changed the application — re-read the card.
 */
function useCardMutation<A>(id: number, run: (arg: A) => Promise<BankApplicationDetail>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: run,
    onSuccess: (card) => {
      queryClient.setQueryData(keys.one(id), card);
      void queryClient.invalidateQueries({ queryKey: ["bank", "queue"] });
    },
    onError: (error) => {
      if (isConflict(error)) void queryClient.invalidateQueries({ queryKey: keys.one(id) });
    },
  });
}

export function useAssign(id: number) {
  return useCardMutation(id, async (body: Schemas["VersionedAction"]) =>
    unwrap(await api.POST("/api/bank/applications/{id}/assign", { ...path(id), body })),
  );
}

export function useApprove(id: number) {
  return useCardMutation(id, async (body: Schemas["VersionedAction"]) =>
    unwrap(await api.POST("/api/bank/applications/{id}/approve", { ...path(id), body })),
  );
}

export function useCounteroffer(id: number) {
  return useCardMutation(id, async (body: Schemas["CounterofferAction"]) =>
    unwrap(await api.POST("/api/bank/applications/{id}/counteroffer", { ...path(id), body })),
  );
}

export function useRequestInfo(id: number) {
  return useCardMutation(id, async (body: Schemas["RequestInfoAction"]) =>
    unwrap(await api.POST("/api/bank/applications/{id}/request-info", { ...path(id), body })),
  );
}

export function useDecline(id: number) {
  return useCardMutation(id, async (body: Schemas["DeclineAction"]) =>
    unwrap(await api.POST("/api/bank/applications/{id}/decline", { ...path(id), body })),
  );
}

/** Download through the API client (session + attachment), then hand the file to the browser. */
export async function downloadDocument(applicationId: number, document: Schemas["Document"]) {
  const blob = unwrap(
    await api.GET("/api/bank/applications/{id}/documents/{document_id}", {
      params: { path: { id: applicationId, document_id: document.id } },
      parseAs: "blob",
    }),
  ) as Blob;
  const url = URL.createObjectURL(blob);
  try {
    const link = globalThis.document.createElement("a");
    link.href = url;
    link.download = document.filename;
    link.click();
  } finally {
    // After the click has started the download; revoking synchronously can cancel it in Firefox.
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }
}
