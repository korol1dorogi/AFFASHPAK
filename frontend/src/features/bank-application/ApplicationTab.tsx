import type { Schemas } from "@/api/client";
import { offerAmountSource, SourceTag } from "@/components/AmountSource";
import { Facts } from "@/components/Facts";
import { MoneyText, RateText } from "@/components/Money";
import { ImprovementList, ReasonList } from "@/components/ReasonList";
import { EmptyState } from "@/components/States";
import { Badge } from "@/components/ui/badge";
import { Card, CardTitle } from "@/components/ui/card";
import type { BankApplicationDetail } from "@/features/bank-application/api";
import { formatDate, formatDateTime } from "@/lib/format";
import {
  BANK_CARD,
  DECIDED_BY,
  DECISION_OUTCOME,
  DOCUMENT_KIND,
  INFO_REQUEST_ORIGIN,
  INFO_REQUEST_STATUS,
  NEED,
  OFFER_STATUS,
} from "@/texts";

const T = BANK_CARD.application;

function Params({ application }: { application: Schemas["Application"] }) {
  return (
    <Card>
      <CardTitle>{T.params}</CardTitle>
      <Facts
        items={[
          { label: T.need, value: NEED[application.need_type].title },
          { label: T.purpose, value: application.purpose },
          {
            label: T.requested,
            value: (
              <>
                <MoneyText value={application.requested_amount} />
                <SourceTag source="client" />
              </>
            ),
          },
          { label: T.term, value: T.months(application.term_months) },
          ...(application.invoice_amount === null
            ? []
            : [
                {
                  label: T.invoice,
                  value: (
                    <>
                      <MoneyText value={application.invoice_amount} />
                      <SourceTag source="client" />
                    </>
                  ),
                },
              ]),
          { label: T.collateral, value: application.collateral_description ?? T.noCollateral },
          { label: T.created, value: formatDateTime(application.created_at) },
          {
            label: T.submitted,
            value: application.submitted_at
              ? formatDateTime(application.submitted_at)
              : T.notSubmitted,
          },
          { label: T.statusChanged, value: formatDateTime(application.status_changed_at) },
        ]}
      />
    </Card>
  );
}

function OfferBlock({
  offer,
  decisions,
}: {
  offer: Schemas["Offer"];
  decisions: Schemas["Decision"][];
}) {
  return (
    <Card>
      <div className="flex flex-wrap items-center gap-2">
        <CardTitle>{T.offer}</CardTitle>
        <Badge variant="brand">{OFFER_STATUS[offer.status]}</Badge>
        {offer.is_counteroffer ? <Badge variant="action">{T.counteroffer}</Badge> : null}
        {offer.product_changed ? <Badge variant="action">{T.productChanged}</Badge> : null}
      </div>
      <Facts
        items={[
          { label: BANK_CARD.header.product, value: offer.product.name },
          {
            label: BANK_CARD.header.amount,
            value: (
              <>
                <MoneyText value={offer.amount} />
                <SourceTag source={offerAmountSource(decisions)} />
              </>
            ),
          },
          ...(offer.is_counteroffer
            ? [
                {
                  label: T.offerRequested,
                  value: (
                    <>
                      <MoneyText value={offer.requested_amount} />
                      <SourceTag source="client" />
                    </>
                  ),
                },
              ]
            : []),
          { label: T.rate, value: <RateText value={offer.rate} /> },
          { label: T.term, value: T.months(offer.term_months) },
          {
            label: T.payment,
            value:
              offer.monthly_payment === null ? (
                T.revolvingPayment
              ) : (
                <>
                  <MoneyText value={offer.monthly_payment} />
                  <SourceTag source="calc" />
                </>
              ),
          },
          { label: T.expires, value: formatDate(offer.expires_at) },
        ]}
      />
      <ReasonList reasons={offer.reasons} variant="bank" label={T.offerReasons} />
    </Card>
  );
}

function InfoRequests({ requests }: { requests: Schemas["InfoRequest"][] }) {
  return (
    <Card>
      <CardTitle>{T.infoRequests}</CardTitle>
      <ul className="m-0 flex list-none flex-col gap-3 p-0">
        {requests.map((request) => (
          <li key={request.id} className="flex flex-col gap-1 rounded-md border border-line p-3">
            <div className="flex flex-wrap items-center gap-2 text-sm text-ink-muted">
              <span>{INFO_REQUEST_ORIGIN[request.origin]}</span>
              <span>· {formatDateTime(request.created_at)}</span>
              <Badge variant={request.status === "open" ? "action" : "success"}>
                {INFO_REQUEST_STATUS[request.status]}
              </Badge>
            </div>
            <p className="m-0">{request.message}</p>
            {request.document_kinds.length ? (
              <p className="m-0 text-sm text-ink-muted">
                {T.documentsNeeded}:{" "}
                {request.document_kinds.map((kind) => DOCUMENT_KIND[kind]).join(", ")}
              </p>
            ) : null}
            {request.response_message ? (
              <p className="m-0 text-sm">
                <span className="text-ink-muted">{T.clientAnswer}: </span>
                {request.response_message}
              </p>
            ) : null}
          </li>
        ))}
      </ul>
    </Card>
  );
}

function DecisionItem({ decision }: { decision: Schemas["Decision"] }) {
  return (
    <li className="flex flex-col gap-4 rounded-md border border-line p-4">
      <div className="flex flex-wrap items-center gap-2">
        <p className="m-0 font-semibold">{DECISION_OUTCOME[decision.outcome]}</p>
        <span className="text-sm text-ink-muted">{formatDateTime(decision.created_at)}</span>
      </div>
      <Facts
        items={[
          {
            label: T.decidedBy,
            value: `${DECIDED_BY[decision.decided_by]}${decision.is_preliminary ? ` · ${T.preliminary}` : ""}`,
          },
          { label: BANK_CARD.header.grade, value: decision.grade ?? BANK_CARD.noGrade },
          { label: T.policy, value: decision.policy_version },
          ...(decision.comment ? [{ label: T.comment, value: decision.comment }] : []),
        ]}
      />
      <ReasonList reasons={decision.reasons} variant="bank" label={T.reasons} />
      <ImprovementList items={decision.improvements} />
    </li>
  );
}

function Decisions({ decisions }: { decisions: Schemas["Decision"][] }) {
  const newestFirst = [...decisions].sort((a, b) => b.created_at.localeCompare(a.created_at));
  return (
    <Card>
      <CardTitle>{T.decisions}</CardTitle>
      {newestFirst.length === 0 ? (
        <EmptyState title={T.noDecisions} text={T.noDecisionsText} />
      ) : (
        <ol aria-label={T.decisions} className="m-0 flex list-none flex-col gap-3 p-0">
          {newestFirst.map((decision) => (
            <DecisionItem key={decision.id} decision={decision} />
          ))}
        </ol>
      )}
    </Card>
  );
}

export function ApplicationTab({ card }: { card: BankApplicationDetail }) {
  return (
    <>
      <Params application={card.application} />
      {card.offer ? <OfferBlock offer={card.offer} decisions={card.decisions} /> : null}
      {card.info_requests.length ? <InfoRequests requests={card.info_requests} /> : null}
      <Decisions decisions={card.decisions} />
    </>
  );
}
