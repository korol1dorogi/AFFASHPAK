import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type Schemas } from "@/api/client";
import type { Me } from "@/app/session";
import { unwrap } from "@/lib/errors";

export const keys = {
  company: ["company"] as const,
  members: ["company", "members"] as const,
  invitations: ["company", "invitations"] as const,
  myInvitations: ["invitations"] as const,
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

/** The company's invitations still waiting for an answer. */
export function useInvitations() {
  return useQuery({
    queryKey: keys.invitations,
    queryFn: async () => unwrap(await api.GET("/api/company/invitations")),
  });
}

/** Nobody joins without consent: the invitee accepts on their side (useAcceptInvitation). */
export function useInvite() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: Schemas["InvitationCreate"]) =>
      unwrap(await api.POST("/api/company/invitations", { body })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.invitations }),
  });
}

export function useCancelInvitation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (invitationId: number) =>
      unwrap(
        await api.DELETE("/api/company/invitations/{invitation_id}", {
          params: { path: { invitation_id: invitationId } },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.invitations }),
  });
}

/** Invitations addressed to the current user (a client without a company sees them first). */
export function useMyInvitations() {
  return useQuery({
    queryKey: keys.myInvitations,
    queryFn: async () => unwrap(await api.GET("/api/invitations")),
  });
}

/** Like creating a company: `me` gets it at once, so RequireCompany lets the client into /app. */
export function useAcceptInvitation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (invitationId: number) =>
      unwrap(
        await api.POST("/api/invitations/{invitation_id}/accept", {
          params: { path: { invitation_id: invitationId } },
        }),
      ),
    onSuccess: (company) => {
      queryClient.setQueryData(keys.company, company);
      queryClient.setQueryData<Me | null>(["me"], (me) =>
        me ? { ...me, company_id: company.id, company_role: company.my_role } : me,
      );
      void queryClient.invalidateQueries({ queryKey: ["me"] });
      void queryClient.invalidateQueries({ queryKey: keys.myInvitations });
    },
  });
}

export function useDeclineInvitation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (invitationId: number) =>
      unwrap(
        await api.POST("/api/invitations/{invitation_id}/decline", {
          params: { path: { invitation_id: invitationId } },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.myInvitations }),
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
