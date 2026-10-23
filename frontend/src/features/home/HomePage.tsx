import { Link } from "react-router";

import { routes } from "@/app/routes";
import { useMe } from "@/app/session";
import { MoneyText } from "@/components/Money";
import { EmptyState, ErrorState, PageHeader, PageSkeleton } from "@/components/States";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { useApplications } from "@/features/applications/api";
import { greetingName } from "@/lib/format";
import { NEED, STATUS } from "@/texts";

/** Home, first version: what needs the client's action first, then the rest (C8 adds metrics). */
export function HomePage() {
  const me = useMe();
  const applications = useApplications();
  const firstName = greetingName(me.data?.full_name ?? "");

  const cta = (
    <Button asChild size="lg">
      <Link to={routes.match}>Подобрать финансирование</Link>
    </Button>
  );

  if (applications.isPending) return <PageSkeleton />;
  if (applications.isError)
    return <ErrorState error={applications.error} onRetry={() => applications.refetch()} />;

  const active = applications.data.filter(
    (item) => !["issued", "declined", "cancelled"].includes(item.status),
  );
  const needsAction = active.filter((item) => STATUS[item.status].group === "action");
  const waiting = active.filter((item) => STATUS[item.status].group !== "action");

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        title={firstName ? `Здравствуйте, ${firstName}` : "Главная"}
        actions={active.length ? cta : undefined}
      />
      {active.length === 0 ? (
        <EmptyState
          title="Активных заявок нет"
          text="Расскажите, зачем бизнесу деньги, — подберём инструмент и сумму по данным вашего счёта."
          action={cta}
        />
      ) : null}
      {[
        { title: "Нужно ваше действие", items: needsAction },
        { title: "В работе у банка", items: waiting },
      ].map((group) =>
        group.items.length ? (
          <section key={group.title} className="flex flex-col gap-3">
            <h2 className="m-0 font-display text-[22px] leading-7 font-bold">{group.title}</h2>
            {group.items.map((item) => (
              <Card key={item.id} className="flex-row flex-wrap items-center gap-4">
                <div className="min-w-0 flex-[1_1_320px]">
                  <CardTitle className="text-base">
                    Заявка № {item.id} · {NEED[item.need_type].title}
                  </CardTitle>
                  <p className="m-0 text-sm text-ink-muted">{STATUS[item.status].next}</p>
                </div>
                <MoneyText value={item.requested_amount} className="font-semibold" />
                <StatusBadge status={item.status} />
                {/* One accent (red) button per screen, as in the design book: lists are secondary. */}
                <Button asChild variant="secondary">
                  <Link to={routes.application(item.id)}>Открыть</Link>
                </Button>
              </Card>
            ))}
          </section>
        ) : null,
      )}
    </div>
  );
}
