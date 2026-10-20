import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router";

import { api, type Schemas } from "@/api/client";
import { routes } from "@/app/routes";
import { unwrap } from "@/lib/errors";

export type Me = Schemas["Me"];

/** The signed-in user, or null when there is no session (401) or no auth API yet (404). */
export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: async (): Promise<Me | null> => {
      const result = await api.GET("/api/auth/me");
      if (result.response.status === 401 || result.response.status === 404) return null;
      return unwrap(result);
    },
    staleTime: 60_000,
  });
}

/** The current user's company (header, wizard «О бизнесе»); null until it is created. */
export function useCompany(enabled = true) {
  return useQuery({
    queryKey: ["company"],
    enabled,
    queryFn: async () => {
      const result = await api.GET("/api/company");
      if (result.response.status === 404) return null;
      return unwrap(result);
    },
    staleTime: 60_000,
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  return useMutation({
    mutationFn: async () => {
      await api.POST("/api/auth/logout");
    },
    onSettled: () => {
      queryClient.clear();
      navigate(routes.login, { replace: true });
    },
  });
}

export const ROLE_LABEL: Record<Schemas["MemberRole"], string> = {
  signatory: "Подписант",
  preparer: "Готовит заявки",
};
