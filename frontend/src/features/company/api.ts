import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type Schemas } from "@/api/client";
import { ApiError, unwrap } from "@/lib/errors";

export const keys = {
  company: ["company"] as const,
  members: ["company", "members"] as const,
  metrics: ["company", "metrics"] as const,
  me: ["me"] as const,
};

/** ЕГРЮЛ/ЕГРИП record by INN (simulator); null — not in the registry. */
export function useLookup(inn: string | null) {
  return useQuery({
    queryKey: ["company", "lookup", inn],
    enabled: inn !== null,
    retry: false,
    queryFn: async () => {
      const result = await api.GET("/api/company/lookup", {
        params: { query: { inn: inn ?? "" } },
      });
      if (result.response.status === 404) return null;
      return unwrap(result);
    },
  });
}

export function useCreateCompany() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (inn: string) => unwrap(await api.POST("/api/company", { body: { inn } })),
    onSuccess: (company) => {
      queryClient.setQueryData(keys.company, company);
      void queryClient.invalidateQueries({ queryKey: keys.me });
    },
  });
}

export function useRenameCompany() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (name: string) => unwrap(await api.PATCH("/api/company", { body: { name } })),
    onSuccess: (company) => queryClient.setQueryData(keys.company, company),
  });
}

export function useMembers() {
  return useQuery({
    queryKey: keys.members,
    queryFn: async () => unwrap(await api.GET("/api/company/members")),
  });
}

export function useAddMember() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: Schemas["MemberCreate"]) =>
      unwrap(await api.POST("/api/company/members", { body })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.members }),
  });
}

export function useRemoveMember() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (memberId: number) =>
      unwrap(
        await api.DELETE("/api/company/members/{member_id}", {
          params: { path: { member_id: memberId } },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.members }),
  });
}

export function useCompanyMetrics() {
  return useQuery({
    queryKey: keys.metrics,
    queryFn: async () => unwrap(await api.GET("/api/company/metrics")),
  });
}

export const isNotFound = (error: unknown) => error instanceof ApiError && error.status === 404;
