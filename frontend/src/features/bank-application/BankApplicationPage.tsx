import { Lock, SearchX, WifiOff } from "lucide-react";
import { Link, useParams } from "react-router";

import { routes } from "@/app/routes";
import { MoneyText } from "@/components/Money";
import { DemoBadge, EmptyState, ErrorState, PageHeader, PageSkeleton } from "@/components/States";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { ApplicationTab } from "@/features/bank-application/ApplicationTab";
import {
  type BankApplicationDetail,
  useBankApplication,
  useProducts,
} from "@/features/bank-application/api";
import { CardTabs } from "@/features/bank-application/CardTabs";
import { ChecksTab } from "@/features/bank-application/ChecksTab";
import { ClientTab } from "@/features/bank-application/ClientTab";
import { DocumentsTab } from "@/features/bank-application/DocumentsTab";
import { JournalTab } from "@/features/bank-application/JournalTab";
import { ScoringTab } from "@/features/bank-application/ScoringTab";
import { ApiError } from "@/lib/errors";
import { BANK_CARD } from "@/texts";

function useProductName(card: BankApplicationDetail): string {
  const products = useProducts();
  const code = card.application.product_code;
  const fromCatalog = code ? products.data?.find((item) => item.code === code)?.name : undefined;
  return fromCatalog ?? card.offer?.product.name ?? code ?? BANK_CARD.noProduct;
}

function Header({ card }: { card: BankApplicationDetail }) {
  const product = useProductName(card);
  const { application, company } = card;
  const latest = [...card.decisions].sort((a, b) => b.created_at.localeCompare(a.created_at))[0];
  const grade = card.score?.grade ?? latest?.grade ?? BANK_CARD.noGrade;
  // The card has no source_unavailable of its own (the queue item has); it is the same fact.
  const sourceUnavailable = card.checks.some((check) => check.status === "unavailable");
  const facts = [
    { label: BANK_CARD.header.amount, value: <MoneyText value={application.requested_amount} /> },
    { label: BANK_CARD.header.product, value: product },
    { label: BANK_CARD.header.grade, value: grade },
    { label: BANK_CARD.header.assignee, value: card.assignee?.full_name ?? BANK_CARD.noAssignee },
  ];
  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title={company.name}
        subtitle={`${BANK_CARD.title(application.id)} · ИНН ${company.inn}`}
      >
        <StatusBadge status={application.status} size="md" />
        {company.is_demo ? <DemoBadge /> : null}
      </PageHeader>
      <dl className="m-0 flex flex-wrap gap-x-10 gap-y-3">
        {facts.map((fact) => (
          <div key={fact.label} className="flex flex-col gap-0.5">
            <dt className="text-sm text-ink-muted">{fact.label}</dt>
            <dd className="m-0 font-semibold">{fact.value}</dd>
          </div>
        ))}
      </dl>
      {sourceUnavailable ? (
        <p
          role="status"
          className="m-0 flex items-start gap-2 rounded-md bg-status-neutral-soft px-4 py-3 text-sm text-status-neutral"
        >
          <WifiOff className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          {BANK_CARD.sourceUnavailable}
        </p>
      ) : null}
    </div>
  );
}

function CardView({ card }: { card: BankApplicationDetail }) {
  const id = card.application.id;
  return (
    <div className="flex flex-col gap-6">
      <Header card={card} />
      {/* TODO(B5): action buttons from application.available_actions go here. */}
      <aside aria-label={BANK_CARD.actionsLabel} />
      <CardTabs
        panels={{
          application: <ApplicationTab card={card} />,
          client: <ClientTab card={card} />,
          checks: <ChecksTab checks={card.checks} />,
          scoring: <ScoringTab score={card.score} />,
          documents: <DocumentsTab applicationId={id} documents={card.documents} />,
          journal: <JournalTab applicationId={id} events={card.events} />,
        }}
      />
    </div>
  );
}

function BackToQueue() {
  return (
    <Button asChild variant="secondary">
      <Link to={routes.bank}>{BANK_CARD.backToQueue}</Link>
    </Button>
  );
}

export function BankApplicationPage() {
  const id = Number(useParams().id);
  const card = useBankApplication(id);

  if (card.isPending) return <PageSkeleton />;
  if (card.isError) {
    const status = card.error instanceof ApiError ? card.error.status : 0;
    if (status === 404) {
      return (
        <EmptyState
          icon={<SearchX className="size-6" aria-hidden="true" />}
          title={BANK_CARD.notFoundTitle}
          text={BANK_CARD.notFoundText}
          action={<BackToQueue />}
        />
      );
    }
    if (status === 403) {
      return (
        <EmptyState
          icon={<Lock className="size-6" aria-hidden="true" />}
          title={BANK_CARD.forbiddenTitle}
          text={BANK_CARD.forbiddenText}
          action={<BackToQueue />}
        />
      );
    }
    return <ErrorState error={card.error} onRetry={() => void card.refetch()} />;
  }
  return <CardView card={card.data} />;
}
