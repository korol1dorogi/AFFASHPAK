import { AppLayout } from "@/components/layout/AppLayout";
import { HealthPage } from "@/features/health/HealthPage";

export function App() {
  return (
    <AppLayout>
      <div className="space-y-6">
        <h1 className="text-2xl font-semibold">Добро пожаловать</h1>
        <HealthPage />
      </div>
    </AppLayout>
  );
}
