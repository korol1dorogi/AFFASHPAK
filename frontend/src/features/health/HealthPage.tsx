import { useQuery } from "@tanstack/react-query";

import { api, type Schemas } from "@/api/client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError, errorMessage } from "@/lib/errors";
import { BLOCK_STATE, HEALTH as T } from "@/texts";

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/health");
      if (data) return data;
      // 503 carries a valid Health body (database unavailable); anything else is a failure.
      if (response.status === 503 && error && "database" in error) return error;
      throw new ApiError(response.status, error as unknown as Schemas["Error"] | undefined);
    },
    retry: false,
  });
}

export function HealthPage() {
  const health = useHealth();
  const { data, isPending, isError } = health;

  let status: { text: string; variant: "success" | "danger" | "neutral" };
  if (isPending) status = { text: T.checking, variant: "neutral" };
  else if (isError) status = { text: T.unavailable, variant: "danger" };
  else if (data.status === "ok") status = { text: T.ok, variant: "success" };
  else status = { text: T.degraded, variant: "danger" };

  return (
    <Card>
      <CardHeader>
        <CardTitle>{T.title}</CardTitle>
        <CardDescription>{T.subtitle}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col items-start gap-3">
        <span aria-live="polite">
          <Badge variant={status.variant} data-testid="health-status">
            {status.text}
          </Badge>
        </span>
        {isError ? (
          <p role="alert" className="m-0 text-sm">
            {errorMessage(health.error)}
          </p>
        ) : null}
        {status.variant === "danger" ? (
          <Button
            variant="secondary"
            size="sm"
            loading={health.isFetching}
            onClick={() => void health.refetch()}
          >
            {BLOCK_STATE.retry}
          </Button>
        ) : null}
      </CardContent>
    </Card>
  );
}
