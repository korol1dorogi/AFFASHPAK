import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type Schemas } from "@/api/client";
import { unwrap } from "@/lib/errors";

export type ApplicationDetail = Schemas["ApplicationDetail"];
type Status = Schemas["ApplicationStatus"];

/** While the pipeline works the status changes in seconds; otherwise the bank takes its time. */
const FAST_POLL: ReadonlySet<Status> = new Set(["submitted", "processing", "signed"]);

export const keys = {
  list: ["applications"] as const,
  one: (id: number) => ["application", id] as const,
  events: (id: number) => ["application", id, "events"] as const,
  documents: (id: number) => ["application", id, "documents"] as const,
};

export function useApplications() {
  return useQuery({
    queryKey: keys.list,
    queryFn: async () => unwrap(await api.GET("/api/applications")),
  });
}

/** Application with offer, open info requests, decision and available_actions; polls for changes (F5). */
export function useApplication(id: number, { poll = true } = {}) {
  return useQuery({
    queryKey: keys.one(id),
    queryFn: async () =>
      unwrap(await api.GET("/api/applications/{id}", { params: { path: { id } } })),
    refetchInterval: (query) => {
      if (!poll) return false;
      const status = query.state.data?.status;
      return status && FAST_POLL.has(status) ? 3_000 : 15_000;
    },
  });
}

export function useEvents(id: number) {
  return useQuery({
    queryKey: keys.events(id),
    queryFn: async () =>
      unwrap(await api.GET("/api/applications/{id}/events", { params: { path: { id } } })),
    refetchInterval: 15_000,
  });
}

export function useDocuments(id: number) {
  return useQuery({
    queryKey: keys.documents(id),
    queryFn: async () =>
      unwrap(await api.GET("/api/applications/{id}/documents", { params: { path: { id } } })),
  });
}

export function useProducts() {
  return useQuery({
    queryKey: ["products"],
    queryFn: async () => unwrap(await api.GET("/api/products")),
    staleTime: 5 * 60_000,
  });
}

/** Mutations that return ApplicationDetail put it into the cache and refresh lists and timeline. */
function useDetailMutation<A>(id: number, run: (arg: A) => Promise<ApplicationDetail>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: run,
    onSuccess: (detail) => {
      queryClient.setQueryData(keys.one(id), detail);
      void queryClient.invalidateQueries({ queryKey: keys.list });
      void queryClient.invalidateQueries({ queryKey: keys.events(id) });
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
    onError: () => {
      // 409: someone changed it meanwhile — show the current state.
      void queryClient.invalidateQueries({ queryKey: keys.one(id) });
    },
  });
}

const path = (id: number) => ({ params: { path: { id } } });

export function useCreateApplication() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: Schemas["ApplicationCreate"]) =>
      unwrap(await api.POST("/api/applications", { body })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.list }),
  });
}

export function useUpdateApplication(id: number) {
  return useDetailMutation(id, async (body: Schemas["ApplicationUpdate"]) =>
    unwrap(await api.PATCH("/api/applications/{id}", { ...path(id), body })),
  );
}

export function useSubmit(id: number) {
  return useDetailMutation(id, async (key: string) =>
    unwrap(
      await api.POST("/api/applications/{id}/submit", {
        params: { path: { id }, header: { "Idempotency-Key": key } },
      }),
    ),
  );
}

export function useCancel(id: number) {
  return useDetailMutation(id, async () =>
    unwrap(await api.POST("/api/applications/{id}/cancel", path(id))),
  );
}

export function useAcceptOffer(id: number) {
  return useDetailMutation(id, async () =>
    unwrap(await api.POST("/api/applications/{id}/offer/accept", path(id))),
  );
}

export function useDeclineOffer(id: number) {
  return useDetailMutation(id, async () =>
    unwrap(await api.POST("/api/applications/{id}/offer/decline", path(id))),
  );
}

export function useRespondInfo(id: number) {
  return useDetailMutation(
    id,
    async ({ requestId, message }: { requestId: number; message: string }) =>
      unwrap(
        await api.POST("/api/applications/{id}/info-requests/{request_id}/respond", {
          params: { path: { id, request_id: requestId } },
          body: { message },
        }),
      ),
  );
}

export function useStartSignature(id: number) {
  return useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/applications/{id}/signature", path(id))),
  });
}

export function useConfirmSignature(id: number) {
  return useDetailMutation(id, async (code: string) =>
    unwrap(
      await api.POST("/api/applications/{id}/signature/confirm", { ...path(id), body: { code } }),
    ),
  );
}

export function useUploadDocument(id: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ kind, file }: { kind: Schemas["DocumentKind"]; file: File }) =>
      unwrap(
        await api.POST("/api/applications/{id}/documents", {
          ...path(id),
          // The contract types `file` as a binary string; the browser sends the File itself.
          body: { kind, file: file as unknown as string },
          bodySerializer: (body) => {
            const form = new FormData();
            form.append("kind", body.kind);
            form.append("file", body.file as unknown as Blob);
            return form;
          },
        }),
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: keys.documents(id) });
      void queryClient.invalidateQueries({ queryKey: keys.events(id) });
    },
  });
}
