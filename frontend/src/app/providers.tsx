import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode, useEffect, useState } from "react";
import { Toaster } from "sonner";

import { api } from "@/api/client";
import { ApiError } from "@/lib/errors";

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 15_000,
        refetchOnWindowFocus: false,
        // 4xx are answers, not glitches: do not retry them.
        retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 2,
      },
      mutations: { retry: false },
    },
  });
}

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(makeQueryClient);

  useEffect(() => {
    // Sets the csrftoken cookie before the first unsafe request (docs/frontend.md §4).
    void api.GET("/api/auth/csrf");
  }, []);

  return (
    <QueryClientProvider client={client}>
      {children}
      <Toaster
        position="bottom-right"
        toastOptions={{
          className: "!bg-surface !text-ink !border-line !rounded-md !font-sans",
        }}
      />
    </QueryClientProvider>
  );
}
