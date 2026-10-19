import { FileText, LayoutDashboard, MessageCircle, Wallet } from "lucide-react";
import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";

// Navigation stubs; real routes arrive with the features (docs/tasks.md).
const NAV_ITEMS = [
  { label: "Обзор", icon: LayoutDashboard },
  { label: "Подбор продукта", icon: Wallet },
  { label: "Заявки", icon: FileText },
  { label: "Ассистент", icon: MessageCircle },
] as const;

export function AppLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-muted/40">
      <header className="border-b bg-background">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
          <span className="font-semibold">Кредитный кабинет предпринимателя</span>
          <Badge variant="outline">прототип · демо-данные</Badge>
        </div>
      </header>
      <div className="mx-auto flex max-w-6xl gap-6 px-4 py-6">
        <nav aria-label="Разделы кабинета" className="hidden w-56 shrink-0 md:block">
          <ul className="space-y-1">
            {NAV_ITEMS.map(({ label, icon: Icon }) => (
              <li key={label}>
                <span
                  aria-disabled="true"
                  className="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-muted-foreground"
                >
                  <Icon className="size-4" aria-hidden="true" />
                  {label}
                </span>
              </li>
            ))}
          </ul>
        </nav>
        <main className="min-w-0 flex-1">{children}</main>
      </div>
    </div>
  );
}
