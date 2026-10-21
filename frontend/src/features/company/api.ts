import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type Schemas } from "@/api/client";
import type { Me } from "@/app/session";
import { unwrap } from "@/lib/errors";

export const keys = {
  company: ["company"] as const,
  members: ["company", "members"] as const,
  lookup: (inn: string) => ["company", "lookup", inn] as const,
};

/** ЕГРЮЛ/ЕГРИП record by INN (simulator); runs once an INN has been submitted. */
export function useLookup(inn: string | null) {
  return useQuery({
    queryKey: keys.lookup(inn ?? ""),
    enabled: inn !== null,
    queryFn: async () =>
      unwrap(await api.GET("/api/company/lookup", { params: { query: { inn: inn ?? "" } } })),
    retry: false,
    staleTime: 5 * 60_000,
  });
}

/**
 * Company by INN: requisites come from the registry, the creator becomes signatory.
 * `me` gets the company at once, so RequireCompany lets the client into /app without a reload.
 */
export function useCreateCompany() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (inn: string) => unwrap(await api.POST("/api/company", { body: { inn } })),
    onSuccess: (company) => {
      queryClient.setQueryData(keys.company, company);
      queryClient.setQueryData<Me | null>(["me"], (me) =>
        me ? { ...me, company_id: company.id, company_role: company.my_role } : me,
      );
      void queryClient.invalidateQueries({ queryKey: ["me"] });
    },
  });
}

/** Only the short name is editable; registry requisites are not. */
export function useUpdateCompany() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: Schemas["CompanyUpdate"]) =>
      unwrap(await api.PATCH("/api/company", { body })),
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

/** Connect a data source (simulator): brings the statement snapshot, remembered in integrations. */
export function useConnectIntegration() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (source: Schemas["IntegrationSource"]) =>
      unwrap(
        await api.POST("/api/company/integrations/{source}/connect", {
          params: { path: { source } },
        }),
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: keys.company });
    },
  });
}

/** Key metrics from the latest statement snapshot, explained like a preliminary evaluation. */
export function useCompanyMetrics() {
  return useQuery({
    queryKey: [...keys.company, "metrics"],
    queryFn: async () => unwrap(await api.GET("/api/company/metrics")),
  });
}
