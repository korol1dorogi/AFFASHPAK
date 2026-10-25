import { useQuery } from "@tanstack/react-query";
import { Bell, LogOut } from "lucide-react";
import type { ReactNode } from "react";
import { Link, NavLink, Outlet } from "react-router";

import { api } from "@/api/client";
import { routes } from "@/app/routes";
import { ROLE_LABEL, useCompany, useLogout, useMe } from "@/app/session";
import { DemoBadge } from "@/components/States";
import { Button } from "@/components/ui/button";
import { AssistantPanel } from "@/features/assistant/AssistantPanel";
import { AssistantProvider } from "@/features/assistant/context";
import { unwrap } from "@/lib/errors";
import { cn } from "@/lib/utils";
import { PRODUCT_NAME } from "@/texts";

function Brand() {
  return (
    <Link
      to={routes.landing}
      className="font-display text-[22px] font-extrabold tracking-[-0.02em] text-ink no-underline"
    >
      {PRODUCT_NAME}
    </Link>
  );
}

function Header({ children }: { children: ReactNode }) {
  return (
    <header className="flex h-14 items-center gap-4 border-b border-line bg-surface px-6">
      {children}
    </header>
  );
}

function NavItem({ to, end, children }: { to: string; end?: boolean; children: ReactNode }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        cn(
          "flex h-10 items-center rounded-md px-3 font-medium no-underline",
          isActive
            ? "bg-primary-soft font-semibold text-primary-ink"
            : "text-ink-muted hover:bg-sunken hover:text-ink",
        )
      }
    >
      {children}
    </NavLink>
  );
}

function UserBlock() {
  const me = useMe();
  const logout = useLogout();
  if (!me.data) return null;
  const role = me.data.company_role
    ? ROLE_LABEL[me.data.company_role]
    : me.data.kind === "bank"
      ? "Менеджер банка"
      : "";
  return (
    <div className="flex items-center gap-3">
      <span className="flex flex-col text-right text-sm leading-4">
        <span className="font-semibold">{me.data.full_name}</span>
        <span className="text-ink-muted">{role}</span>
      </span>
      <Button variant="ghost" size="icon" aria-label="Выйти" onClick={() => logout.mutate()}>
        <LogOut aria-hidden="true" />
      </Button>
    </div>
  );
}

function NotificationBell() {
  const unread = useQuery({
    queryKey: ["notifications", { unread: true, page_size: 5 }],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/notifications", { params: { query: { unread: true, page_size: 5 } } }),
      ),
    refetchInterval: 20_000,
  });
  const count = unread.data?.unread_count ?? 0;
  return (
    <Button asChild variant="ghost" size="sm">
      <Link
        to={routes.notifications}
        aria-label={count ? `Уведомления, непрочитанных: ${count}` : "Уведомления"}
      >
        <Bell aria-hidden="true" />
        {count ? (
          <span className="min-w-5 rounded-full bg-status-action px-1.5 text-center text-xs leading-5 text-surface">
            {count}
          </span>
        ) : null}
      </Link>
    </Button>
  );
}

function Shell({
  header,
  nav,
  children,
}: {
  header: ReactNode;
  nav: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="min-h-screen bg-paper">
      <Header>{header}</Header>
      <div className="flex flex-wrap gap-8 p-6">
        <nav aria-label="Разделы" className="flex max-w-60 flex-[1_1_200px] flex-col gap-1">
          {nav}
        </nav>
        <main className="flex min-w-0 max-w-[1120px] flex-[999_1_560px] flex-col gap-6">
          {children}
        </main>
      </div>
    </div>
  );
}

export function ClientLayout() {
  const me = useMe();
  const company = useCompany(Boolean(me.data?.company_id !== null));
  return (
    // One assistant for the whole cabinet: context buttons on any page open the same panel (AI6).
    <AssistantProvider>
      <Shell
        header={
          <>
            <Brand />
            {me.data?.is_demo || company.data?.is_demo ? <DemoBadge /> : null}
            {company.data ? (
              <span className="text-sm text-ink-muted">
                {company.data.short_name ?? company.data.name}
              </span>
            ) : null}
            <div className="flex-1" />
            <AssistantPanel />
            <NotificationBell />
            <UserBlock />
          </>
        }
        nav={
          <>
            <NavItem to={routes.home} end>
              Главная
            </NavItem>
            <NavItem to={routes.match}>Подобрать финансирование</NavItem>
            <NavItem to={routes.applications}>Заявки</NavItem>
            <NavItem to={routes.products}>Продукты</NavItem>
            <NavItem to={routes.company}>Компания</NavItem>
          </>
        }
      >
        <Outlet />
      </Shell>
    </AssistantProvider>
  );
}

export function BankLayout() {
  // /api/demo/* exists only on the stand (DEMO_MODE=1): no panel item where it answers 404.
  const demo = useQuery({
    queryKey: ["demo", "failures"],
    queryFn: async () => unwrap(await api.GET("/api/demo/failures")),
    retry: false,
  });
  return (
    <Shell
      header={
        <>
          <Brand />
          <span className="rounded-sm bg-status-progress-soft px-2 py-0.5 text-sm font-semibold text-status-progress">
            Рабочее место банка
          </span>
          <div className="flex-1" />
          <UserBlock />
        </>
      }
      nav={
        <>
          <NavItem to={routes.bank} end>
            Очередь
          </NavItem>
          <NavItem to={routes.bankDashboard}>Сводка</NavItem>
          <NavItem to={routes.bankPolicy}>Кредитная политика</NavItem>
          {demo.isSuccess ? <NavItem to={routes.bankDemo}>Демо-панель</NavItem> : null}
        </>
      }
    >
      <Outlet />
    </Shell>
  );
}

export function PublicLayout() {
  return (
    <div className="min-h-screen bg-paper">
      <Header>
        <Brand />
      </Header>
      <main className="mx-auto flex max-w-[1120px] flex-col gap-6 p-6">
        <Outlet />
      </main>
    </div>
  );
}
