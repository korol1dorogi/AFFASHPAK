import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { toast } from "sonner";

import type { Schemas } from "@/api/client";
import { routes } from "@/app/routes";
import { offerAmountSource } from "@/components/AmountSource";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { NextStep } from "@/components/NextStep";
import { OfferCard } from "@/components/OfferCard";
import { ImprovementList, ReasonList } from "@/components/ReasonList";
import { ErrorState, PageHeader, PageSkeleton } from "@/components/States";
import { StatusBadge } from "@/components/StatusBadge";
import { StatusTimeline } from "@/components/StatusTimeline";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/input";
import { ApprovalPlan } from "@/features/applications/ApprovalPlan";
import {
  type ApplicationDetail,
  useAcceptOffer,
  useApplication,
  useCancel,
  useDeclineOffer,
  useEvents,
  useProducts,
  useRespondInfo,
} from "@/features/applications/api";
import { BlockError, BlockSkeleton } from "@/features/applications/BlockState";
import { CreditHistory } from "@/features/applications/CreditHistory";
import { DocumentList, DocumentUpload } from "@/features/applications/Documents";
import { showsWhatIf, WhatIf } from "@/features/applications/WhatIf";
import { ApiError, errorMessage } from "@/lib/errors";
import { formatDate, formatMoney } from "@/lib/format";
import { ACTION, BLOCK_STATE, DECISION_OUTCOME, DOCUMENT_KIND, NEED } from "@/texts";

const FIELD_LABEL: Record<string, string> = {
  purpose: "цель",
  product_code: "продукт",
  requested_amount: "сумма",
  term_months: "срок",
  invoice_amount: "сумма отгрузки",
  collateral_description: "залог",
};

const ALL_KINDS = Object.keys(DOCUMENT_KIND) as Schemas["DocumentKind"][];

function useProductName(code: string | null): string | null {
  const products = useProducts();
  if (!code) return null;
  const product = products.data?.find((item) => item.code === code);
  return product ? product.name : null;
}

function InfoRequestCard({
  application,
  request,
}: {
  application: ApplicationDetail;
  request: Schemas["InfoRequest"];
}) {
  const respond = useRespondInfo(application.id);
  const [message, setMessage] = useState("");
  const canRespond = application.available_actions.includes("respond_info");
  const kinds = request.document_kinds.length ? request.document_kinds : ALL_KINDS;
  return (
    <Card className="border-status-action">
      <div className="flex flex-wrap items-center gap-2">
        <CardTitle>
          {request.origin === "officer" ? "Банк просит уточнить" : "Не хватает данных"}
        </CardTitle>
        <Badge variant="action">{formatDate(request.created_at)}</Badge>
      </div>
      <p className="m-0">{request.message}</p>
      {request.fields.length ? (
        <p className="m-0 text-sm text-ink-muted">
          Уточните: {request.fields.map((field) => FIELD_LABEL[field] ?? field).join(", ")}
        </p>
      ) : null}
      {request.document_kinds.length ? (
        <p className="m-0 text-sm text-ink-muted">
          Документы: {request.document_kinds.map((kind) => DOCUMENT_KIND[kind]).join(", ")}
        </p>
      ) : null}
      {application.available_actions.includes("upload_document") ? (
        <DocumentUpload applicationId={application.id} kinds={kinds} defaultKind={kinds[0]} />
      ) : null}
      {canRespond ? (
        <form
          className="flex flex-col gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            respond.mutate(
              { requestId: request.id, message: message.trim() },
              { onSuccess: () => toast.success("Ответ отправлен в банк") },
            );
          }}
        >
          <label htmlFor={`answer-${request.id}`} className="text-sm font-medium">
            Ответ банку
          </label>
          <Textarea
            id={`answer-${request.id}`}
            value={message}
            maxLength={2000}
            onChange={(event) => setMessage(event.target.value)}
            placeholder="Например: загрузили отчётность за 2025 год"
          />
          {respond.isError ? (
            <p className="m-0 text-sm text-status-danger">{errorMessage(respond.error)}</p>
          ) : null}
          <Button
            type="submit"
            className="self-start"
            disabled={!message.trim()}
            loading={respond.isPending}
          >
            {ACTION.respond_info}
          </Button>
        </form>
      ) : null}
    </Card>
  );
}

/**
 * Who decided and «что улучшить». Next to an active offer the reasons are already on the offer
 * card, so they are not repeated (withReasons=false), but the rest stays visible.
 */
function DecisionCard({
  decision,
  withReasons = true,
}: {
  decision: Schemas["Decision"];
  withReasons?: boolean;
}) {
  return (
    <Card>
      <div className="flex flex-wrap items-center gap-2">
        <CardTitle>
          {decision.is_preliminary ? "Предварительная оценка" : "Оценка сотрудника банка"}
        </CardTitle>
        <Badge variant={decision.outcome === "declined" ? "danger" : "neutral"}>
          {DECISION_OUTCOME[decision.outcome]}
        </Badge>
      </div>
      {decision.comment ? <p className="m-0">{decision.comment}</p> : null}
      {withReasons ? <ReasonList reasons={decision.reasons} /> : null}
      {decision.approval_plan && decision.grade ? (
        // The shortest way to grade C with targets; all the advice stays below it.
        <ApprovalPlan plan={decision.approval_plan} grade={decision.grade} />
      ) : null}
      {/* BKI1: a past overdue cannot be planned away — say what the bank saw and what to do. */}
      <CreditHistory reasons={decision.reasons} finished={decision.outcome === "declined"} />
      <ImprovementList items={decision.improvements} />
    </Card>
  );
}

function nextStepTitle(application: ApplicationDetail): string | undefined {
  if (application.status !== "offer" || !application.offer) return undefined;
  if (application.offer.product_changed) return "Банк предлагает другой продукт";
  if (application.offer.is_counteroffer) return "Банк предлагает другие условия";
  return "Банк готов выдать деньги";
}

export function ApplicationPage() {
  const id = Number(useParams().id);
  const navigate = useNavigate();
  const application = useApplication(id);
  const events = useEvents(id);
  const accept = useAcceptOffer(id);
  const decline = useDeclineOffer(id);
  const cancel = useCancel(id);
  const [confirm, setConfirm] = useState<"decline" | "cancel" | null>(null);
  const productName = useProductName(application.data?.product_code ?? null);

  if (application.isPending) return <PageSkeleton />;
  if (application.isError) {
    const notFound = application.error instanceof ApiError && application.error.status === 404;
    return (
      <ErrorState
        title={notFound ? "Заявка не найдена" : "Не получилось загрузить заявку"}
        error={application.error}
        onRetry={notFound ? undefined : () => application.refetch()}
      />
    );
  }

  const data = application.data;
  const actions = data.available_actions;

  const mainAction = actions.includes("edit") ? (
    <Button asChild size="lg">
      <Link to={routes.applicationEdit(id, "params")}>Продолжить заполнение</Link>
    </Button>
  ) : actions.includes("sign") ? (
    <Button asChild size="lg">
      <Link to={routes.applicationSign(id)}>{ACTION.sign}</Link>
    </Button>
  ) : null;

  return (
    <div className="flex flex-col gap-6">
      <Link to={routes.applications} className="w-fit text-sm no-underline">
        ← Все заявки
      </Link>
      <PageHeader
        title={`Заявка № ${data.id}`}
        subtitle={[
          productName ?? NEED[data.need_type].title,
          `${formatMoney(data.requested_amount)} на ${data.term_months} мес`,
          data.submitted_at ? `отправлена ${formatDate(data.submitted_at)}` : "не отправлена",
        ].join(" · ")}
        actions={
          actions.includes("cancel") ? (
            <Button variant="ghost" onClick={() => setConfirm("cancel")}>
              {ACTION.cancel}
            </Button>
          ) : undefined
        }
      >
        <StatusBadge status={data.status} size="md" />
      </PageHeader>

      <NextStep status={data.status} title={nextStepTitle(data)} action={mainAction}>
        {data.status === "offer" && data.offer ? (
          <p className="m-0 text-sm">
            Предложение действует до {formatDate(data.offer.expires_at)}.
          </p>
        ) : null}
      </NextStep>

      <div className="flex flex-wrap items-start gap-6">
        <div className="flex min-w-0 flex-[2_1_520px] flex-col gap-6">
          {data.offer ? (
            <OfferCard
              offer={data.offer}
              actions={actions}
              amountSource={offerAmountSource(data.decision ? [data.decision] : [])}
              pending={accept.isPending ? "accept" : decline.isPending ? "decline" : null}
              onAccept={() =>
                accept.mutate(undefined, {
                  onSuccess: () => navigate(routes.applicationSign(id)),
                  onError: (error) => toast.error(errorMessage(error)),
                })
              }
              onDecline={() => setConfirm("decline")}
            />
          ) : null}
          {data.offer && showsWhatIf(data) ? (
            // A new offer starts the calculation from its own terms.
            <WhatIf key={data.offer.id} application={data} offer={data.offer} />
          ) : null}
          {data.open_info_requests.map((request) => (
            <InfoRequestCard key={request.id} application={data} request={request} />
          ))}
          {data.decision ? (
            <DecisionCard
              decision={data.decision}
              // OfferCard lists the reasons only for a changed amount or product
              withReasons={
                !(
                  data.offer &&
                  data.status === "offer" &&
                  (data.offer.is_counteroffer || data.offer.product_changed)
                )
              }
            />
          ) : null}
        </div>

        <aside className="flex min-w-0 flex-[1_1_300px] flex-col gap-6">
          <Card>
            <CardTitle>История</CardTitle>
            {/* A failed background poll keeps the history it already has. */}
            {events.data ? (
              events.data.length === 0 ? (
                <p className="m-0 text-sm text-ink-muted">{BLOCK_STATE.historyEmpty}</p>
              ) : (
                <StatusTimeline events={events.data} />
              )
            ) : events.isError ? (
              <BlockError
                title={BLOCK_STATE.historyError}
                error={events.error}
                onRetry={() => void events.refetch()}
              />
            ) : (
              <BlockSkeleton label={BLOCK_STATE.historyLoading} rows={3} />
            )}
          </Card>
          <Card>
            <CardTitle>Документы</CardTitle>
            <DocumentList applicationId={id} />
            {actions.includes("upload_document") && data.open_info_requests.length === 0 ? (
              <DocumentUpload applicationId={id} kinds={ALL_KINDS} />
            ) : null}
          </Card>
        </aside>
      </div>

      <ConfirmDialog
        open={confirm === "decline"}
        onOpenChange={(open) => setConfirm(open ? "decline" : null)}
        title="Отказаться от предложения?"
        text="Заявка будет закрыта. Чтобы получить деньги позже, придётся подать новую."
        confirmLabel="Отказаться"
        cancelLabel="Оставить"
        danger
        pending={decline.isPending}
        onConfirm={() => decline.mutate(undefined, { onSettled: () => setConfirm(null) })}
      />
      <ConfirmDialog
        open={confirm === "cancel"}
        onOpenChange={(open) => setConfirm(open ? "cancel" : null)}
        title="Отозвать заявку?"
        text="Банк перестанет её рассматривать. Это нельзя отменить."
        confirmLabel="Отозвать"
        cancelLabel="Оставить"
        danger
        pending={cancel.isPending}
        onConfirm={() => cancel.mutate(undefined, { onSettled: () => setConfirm(null) })}
      />
    </div>
  );
}
