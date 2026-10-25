import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type Schemas } from "@/api/client";
import { unwrap } from "@/lib/errors";

export type AssistantMessage = Schemas["AssistantMessage"];
export type AssistantReply = Schemas["AssistantReply"];
export type AssistantToolCall = Schemas["AssistantToolCall"];
export type PendingAction = Schemas["PendingAction"];
export type AssistantSummary = Schemas["AssistantSummary"];

export const assistantKeys = {
  client: (applicationId: number | null) => ["assistant", "client", applicationId] as const,
  bank: (applicationId: number) => ["assistant", "bank", applicationId] as const,
};

/** The client's dialogue: on an application page about it, elsewhere the general one. */
export function useClientHistory(applicationId: number | null, enabled: boolean) {
  return useQuery({
    queryKey: assistantKeys.client(applicationId),
    enabled,
    queryFn: async () =>
      unwrap(
        await api.GET("/api/assistant/messages", {
          params: { query: applicationId ? { application_id: applicationId } : {} },
        }),
      ),
  });
}

export function useSendClientMessage(applicationId: number | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (text: string) =>
      unwrap(
        await api.POST("/api/assistant/messages", {
          body: applicationId ? { text, application_id: applicationId } : { text },
        }),
      ),
    onSettled: () =>
      queryClient.invalidateQueries({ queryKey: assistantKeys.client(applicationId) }),
  });
}

/** «Подтвердить» on what the assistant proposed: the only way it changes anything. */
export function useConfirmAction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (actionId: string) =>
      unwrap(
        await api.POST("/api/assistant/actions/{action_id}/confirm", {
          params: { path: { action_id: actionId } },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["applications"] }),
  });
}

export function useBankHistory(applicationId: number) {
  return useQuery({
    queryKey: assistantKeys.bank(applicationId),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/bank/applications/{id}/assistant/messages", {
          params: { path: { id: applicationId } },
        }),
      ),
  });
}

export function useSendBankMessage(applicationId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (text: string) =>
      unwrap(
        await api.POST("/api/bank/applications/{id}/assistant/messages", {
          params: { path: { id: applicationId } },
          body: { text },
        }),
      ),
    onSettled: () => queryClient.invalidateQueries({ queryKey: assistantKeys.bank(applicationId) }),
  });
}

export function useBankSummary(applicationId: number) {
  return useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/bank/applications/{id}/assistant/summary", {
          params: { path: { id: applicationId } },
        }),
      ),
  });
}
