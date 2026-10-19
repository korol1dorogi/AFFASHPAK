import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: async () => {
      // 503 also carries a valid Health body (database unavailable).
      const { data, error } = await api.GET("/api/health");
      const body = data ?? error;
      if (!body) throw new Error("Пустой ответ от API");
      return body;
    },
    retry: false,
  });
}

export function HealthPage() {
  const { data, isPending, isError } = useHealth();

  let status: { text: string; variant: "success" | "destructive" | "secondary" };
  if (isPending) status = { text: "Проверяем…", variant: "secondary" };
  else if (isError || !data) status = { text: "API недоступен", variant: "destructive" };
  else if (data.status === "ok") status = { text: "Бэкенд работает", variant: "success" };
  else status = { text: "База данных недоступна", variant: "destructive" };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Состояние системы</CardTitle>
        <CardDescription>Проверка связи кабинета с API (GET /api/health)</CardDescription>
      </CardHeader>
      <CardContent>
        <Badge variant={status.variant} data-testid="health-status">
          {status.text}
        </Badge>
      </CardContent>
    </Card>
  );
}
