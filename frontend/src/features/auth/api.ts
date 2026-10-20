import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router";

import { api, type Schemas } from "@/api/client";
import { homeFor, safeNext } from "@/app/routes";
import { unwrap } from "@/lib/errors";

/** After any successful sign-in: remember the user and go to ?next= or the own home. */
function useSignedIn() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  return (me: Schemas["Me"], fallback?: string) => {
    queryClient.clear();
    queryClient.setQueryData(["me"], me);
    navigate(safeNext(params.get("next")) ?? fallback ?? homeFor(me.kind), { replace: true });
  };
}

export function useLogin() {
  const signedIn = useSignedIn();
  return useMutation({
    mutationFn: async (body: Schemas["LoginRequest"]) =>
      unwrap(await api.POST("/api/auth/login", { body })),
    onSuccess: (me) => signedIn(me),
  });
}

export function useRegister() {
  const signedIn = useSignedIn();
  return useMutation({
    mutationFn: async (body: Schemas["RegisterRequest"]) =>
      unwrap(await api.POST("/api/auth/register", { body })),
    onSuccess: (me) => signedIn(me),
  });
}

/** Demo personas exist only on the stand (DEMO_MODE): 404 → null, the block is hidden. */
export function useDemoPersonas() {
  return useQuery({
    queryKey: ["demo", "personas"],
    queryFn: async () => {
      const result = await api.GET("/api/demo/personas");
      if (result.response.status === 404) return null;
      return unwrap(result);
    },
    staleTime: Number.POSITIVE_INFINITY,
  });
}

export function useDemoLogin() {
  const signedIn = useSignedIn();
  return useMutation({
    mutationFn: async (persona: string) =>
      unwrap(await api.POST("/api/demo/login", { body: { persona } })),
    onSuccess: (me) => signedIn(me),
  });
}
