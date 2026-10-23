import type { ReactNode } from "react";

import type { Schemas } from "@/api/client";
import { ROLE_LABEL } from "@/app/session";
import { DemoBadge } from "@/components/States";
import type { BankApplicationDetail } from "@/features/bank-application/api";
import {
  chronological,
  classifyOfficerDecision,
  type OfficerVerdict,
  officerName,
} from "@/features/bank-application/conclusion";
import { FACTOR_MAX_POINTS, factorValue } from "@/features/bank-application/ScoreBreakdown";
import { formatDate, formatDateTime, formatDecimal, formatMoney, formatRate } from "@/lib/format";
import { cn } from "@/lib/utils";
import {
  BANK_CARD,
  CHECK_SOURCE,
  CHECK_STATUS,
  DECIDED_BY,
  DECISION_OUTCOME,
  DOCUMENT_KIND,
  LEGAL_FORM,
  METRIC,
  metricTitle,
  NEED,
  REGISTRY_STATUS,
  SNAPSHOT_FIELD,
  SNAPSHOT_SOURCE,
  STATUS,
} from "@/texts";

const T = BANK_CARD.conclusion;
const C = BANK_CARD.client;
const A = BANK_CARD.application;
const SOURCES = Object.keys(CHECK_SOURCE) as Schemas["CheckSource"][];

/** A block of the conclusion: its heading stays with the content, the block is not split. */
function Section({
  title,
  children,
  split = false,
}: {
  title: string;
  children: ReactNode;
  /** Long blocks (decision history) may continue on the next page; their items do not split. */
  split?: boolean;
}) {
  return (
    <section
      aria-label={title}
      className={cn("flex flex-col gap-1.5", !split && "break-inside-avoid")}
    >
      <h2 className="m-0 break-after-avoid border-b border-line-strong pb-0.5 font-display text-[15px] font-bold print:text-[12.5px]">
        {title}
      </h2>
      {children}
    </section>
  );
}

function Pairs({
  items,
  numeric = false,
}: {
  items: { label: string; value: ReactNode }[];
  /** Figures: the label wraps on the left, the value stays whole on the right. */
  numeric?: boolean;
}) {
  return (
    <dl className="m-0 grid gap-x-6 gap-y-1 sm:grid-cols-2 print:grid-cols-2">
      {items.map((item) => (
        <div
          key={item.label}
          className={cn(
            "grid items-baseline gap-x-2 break-inside-avoid",
            numeric ? "grid-cols-[minmax(0,1fr)_auto]" : "grid-cols-[auto_1fr]",
          )}
        >
          <dt className="text-ink-muted">{item.label}:</dt>
          <dd className="m-0 min-w-0 break-words">{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}

function NoData() {
  return <span className="text-ink-muted">{BANK_CARD.noValue}</span>;
}

function Empty({ children }: { children: ReactNode }) {
  return <p className="m-0 text-ink-muted">{children}</p>;
}

function Head({ card, generatedAt }: { card: BankApplicationDetail; generatedAt: Date }) {
  const { application, company } = card;
  return (
    <header className="flex flex-col gap-1 border-b-2 border-ink pb-2">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h1 className="m-0 font-display text-[22px] leading-7 font-bold">{T.title}</h1>
        <span className="font-semibold">{T.number(application.id)}</span>
        {company.is_demo ? <DemoBadge /> : null}
      </div>
      <p className="m-0 text-ink-muted">
        {T.generatedAt} {formatDateTime(generatedAt.toISOString())} · {T.assignee}:{" "}
        <span className="text-ink">{card.assignee?.full_name ?? BANK_CARD.noAssignee}</span> ·{" "}
        {T.status}: <span className="text-ink">{STATUS[application.status].label}</span>
      </p>
    </header>
  );
}

function Client({ card }: { card: BankApplicationDetail }) {
  const { company, members, snapshot } = card;
  return (
    <Section title={T.client} split>
      <Pairs
        items={[
          { label: C.name, value: company.name },
          ...(company.short_name ? [{ label: C.shortName, value: company.short_name }] : []),
          { label: C.legalForm, value: LEGAL_FORM[company.legal_form] },
          { label: C.inn, value: <span className="tabular">{company.inn}</span> },
          { label: C.ogrn, value: <span className="tabular">{company.ogrn}</span> },
          { label: C.okved, value: `${company.okved} — ${company.okved_name}` },
          { label: C.registered, value: formatDate(company.registered_at) },
          { label: C.registryStatus, value: REGISTRY_STATUS[company.registry_status] },
          { label: C.director, value: company.director_name },
          { label: C.region, value: company.region },
          { label: C.address, value: company.address },
        ]}
      />
      <p className="m-0 break-after-avoid font-semibold">{C.members}</p>
      {members.length === 0 ? (
        <Empty>{C.noMembers}</Empty>
      ) : (
        <ul aria-label={C.members} className="m-0 list-none p-0">
          {members.map((member) => (
            <li key={member.id}>
              {member.user.full_name} — {member.position}, {ROLE_LABEL[member.role]}
            </li>
          ))}
        </ul>
      )}
      <p className="m-0 break-after-avoid font-semibold">
        {C.snapshot}
        {snapshot ? (
          <span className="font-normal text-ink-muted">
            {" "}
            · {C.period} {snapshot.period} · {SNAPSHOT_SOURCE[snapshot.source]}
          </span>
        ) : null}
      </p>
      {snapshot ? (
        <Pairs
          numeric
          items={(Object.keys(SNAPSHOT_FIELD) as (keyof typeof SNAPSHOT_FIELD)[]).map((key) => {
            const value = snapshot[key];
            const field = SNAPSHOT_FIELD[key];
            return {
              label: field.title,
              value:
                value === null ? (
                  <NoData />
                ) : (
                  <span className="tabular whitespace-nowrap">
                    {field.format === "money" ? formatMoney(value) : formatDecimal(value)}
                  </span>
                ),
            };
          })}
        />
      ) : (
        <Empty>{C.noSnapshotText}</Empty>
      )}
    </Section>
  );
}

function ApplicationBlock({
  application,
  product,
}: {
  application: Schemas["Application"];
  product: string;
}) {
  return (
    <Section title={T.application}>
      <Pairs
        items={[
          { label: A.need, value: NEED[application.need_type].title },
          { label: T.product, value: product },
          { label: A.purpose, value: application.purpose },
          {
            label: A.requested,
            value: <span className="tabular">{formatMoney(application.requested_amount)}</span>,
          },
          { label: A.term, value: A.months(application.term_months) },
          ...(application.invoice_amount === null
            ? []
            : [{ label: A.invoice, value: formatMoney(application.invoice_amount) }]),
          { label: A.collateral, value: application.collateral_description ?? A.noCollateral },
          {
            label: A.submitted,
            value: application.submitted_at
              ? formatDateTime(application.submitted_at)
              : A.notSubmitted,
          },
        ]}
      />
    </Section>
  );
}

function Checks({ checks }: { checks: Schemas["Check"][] }) {
  return (
    <Section title={T.checks}>
      {checks.length === 0 ? (
        <Empty>{T.noChecks}</Empty>
      ) : (
        <ul aria-label={T.checks} className="m-0 flex list-none flex-col gap-1 p-0">
          {SOURCES.map((source) => {
            const check = checks.find((item) => item.source === source);
            return (
              <li key={source} data-source={source} className="break-inside-avoid">
                <span className="font-semibold">{CHECK_SOURCE[source]}</span> —{" "}
                {check ? CHECK_STATUS[check.status] : T.checkMissing}
                {check?.summary ? <>. {check.summary}</> : null}
                {check ? (
                  <span className="text-ink-muted"> · {formatDateTime(check.checked_at)}</span>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
    </Section>
  );
}

function Scoring({ score }: { score: Schemas["Score"] | null }) {
  return (
    <Section title={T.scoring} split>
      {score ? (
        <>
          <p className="m-0 font-semibold">{T.scoreTotal(score.total, score.grade)}</p>
          <table className="w-full border-collapse text-left">
            <thead className="text-ink-muted">
              <tr className="border-b border-line">
                <th className="py-0.5 pr-3 font-medium">{T.factor}</th>
                <th className="py-0.5 pr-3 font-medium">{T.value}</th>
                <th className="py-0.5 pr-3 font-medium whitespace-nowrap">{T.points}</th>
                <th className="py-0.5 font-medium">{T.comment}</th>
              </tr>
            </thead>
            <tbody>
              {score.factors.map((factor) => (
                <tr
                  key={factor.name}
                  data-factor={factor.name}
                  className="break-inside-avoid border-b border-line align-top"
                >
                  <td className="py-0.5 pr-3">{metricTitle(factor.name)}</td>
                  <td
                    className={cn(
                      "tabular py-0.5 pr-3 whitespace-nowrap",
                      factor.value === null && "text-ink-muted",
                    )}
                  >
                    {factorValue(factor)}
                  </td>
                  <td className="tabular py-0.5 pr-3 whitespace-nowrap">
                    {BANK_CARD.scoring.points(factor.points, FACTOR_MAX_POINTS[factor.name])}
                  </td>
                  <td className="py-0.5">{factor.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="m-0 text-ink-muted">
            {T.scoreModel(score.model_version, formatDateTime(score.created_at))} ·{" "}
            {BANK_CARD.scoring.note}
          </p>
        </>
      ) : (
        <Empty>{T.noScore}</Empty>
      )}
    </Section>
  );
}

function reasonValue(reason: Schemas["Reason"], value: string | null): string | null {
  const format = METRIC[reason.metric]?.format;
  if (value === null) return format === "text" ? null : BANK_CARD.noValue;
  switch (format) {
    case "money":
      return formatMoney(value);
    case "percent":
      return formatRate(value);
    case "months":
      return `${formatDecimal(value)} мес`;
    case "days":
      return `${formatDecimal(value)} дн.`;
    case "text":
      return value;
    default:
      return formatDecimal(value);
  }
}

/** Reasons by their plain title; the metric code next to it, small (for the bank). */
function Reasons({ reasons }: { reasons: Schemas["Reason"][] }) {
  if (reasons.length === 0) return null;
  return (
    <ul aria-label={T.reasons} className="m-0 flex list-none flex-col gap-0.5 p-0">
      {reasons.map((reason) => {
        const value = reasonValue(reason, reason.value);
        const threshold = reason.threshold === null ? null : reasonValue(reason, reason.threshold);
        return (
          <li
            key={`${reason.metric}-${reason.message}`}
            data-passed={reason.passed}
            className="grid grid-cols-[14px_1fr] gap-1 break-inside-avoid"
          >
            <span
              role="img"
              aria-label={reason.passed ? T.passed : T.failed}
              className={reason.passed ? "text-status-success" : "text-status-danger"}
            >
              {reason.passed ? "✓" : "✗"}
            </span>
            <span>
              <span className="font-semibold">{metricTitle(reason.metric)}</span>{" "}
              <code className="font-mono text-[10px] text-ink-muted">{reason.metric}</code>
              {value ? <span className="tabular"> · {value}</span> : null}
              {threshold ? (
                <span className="text-ink-muted">
                  {" "}
                  ({T.threshold} {threshold})
                </span>
              ) : null}
              <span className="text-ink-muted"> — {reason.message}</span>
            </span>
          </li>
        );
      })}
    </ul>
  );
}

function Verdict({
  verdict,
  decision,
  who,
}: {
  verdict: OfficerVerdict;
  decision: Schemas["Decision"];
  who: string;
}) {
  const outcome = DECISION_OUTCOME[decision.outcome];
  if (verdict.kind === "handoff") {
    return (
      <p className="m-0 rounded-sm bg-sunken px-2 py-1">
        {T.handoff(verdict.cause?.message ?? T.handoffNoCause, outcome)}
      </p>
    );
  }
  if (verdict.kind === "plain") return null;
  return (
    <div
      role="note"
      aria-label={T.override}
      data-override="true"
      className="flex flex-col gap-0.5 rounded-sm border-2 border-status-danger bg-status-danger-soft px-2 py-1"
    >
      <p className="m-0 font-bold text-status-danger">{T.override}</p>
      <p className="m-0">
        {verdict.kind === "override_outcome"
          ? T.overrideOutcome(DECISION_OUTCOME[verdict.auto.outcome], outcome)
          : T.overrideAmount(
              formatMoney(verdict.amount),
              formatMoney(verdict.limit.value),
              metricTitle(verdict.limit.metric),
            )}
      </p>
      <p className="m-0">{T.overrideWho(who, formatDateTime(decision.created_at))}</p>
      <p className="m-0">
        {T.overrideWhy}: {decision.comment ?? T.noReason}
      </p>
    </div>
  );
}

function DecisionItem({
  card,
  decision,
}: {
  card: BankApplicationDetail;
  decision: Schemas["Decision"];
}) {
  const byOfficer = decision.decided_by === "officer";
  const who = byOfficer
    ? (officerName(decision, card.events) ?? T.officer)
    : `${DECIDED_BY.auto} · ${A.preliminary}`;
  const verdict = byOfficer
    ? classifyOfficerDecision(decision, card.decisions, card.offer)
    : ({ kind: "plain" } as const);
  return (
    <li
      data-decision={decision.id}
      className="flex flex-col gap-1 break-inside-avoid border-l-2 border-line-strong pl-2"
    >
      <p className="m-0">
        <span className="font-semibold">{DECISION_OUTCOME[decision.outcome]}</span>
        <span className="text-ink-muted">
          {" "}
          · {formatDateTime(decision.created_at)} · {who} · {BANK_CARD.header.grade}{" "}
          {decision.grade ?? BANK_CARD.noGrade} · {A.policy} {decision.policy_version}
        </span>
      </p>
      <Verdict verdict={verdict} decision={decision} who={who} />
      {decision.comment &&
      verdict.kind !== "override_outcome" &&
      verdict.kind !== "override_amount" ? (
        <p className="m-0">
          <span className="text-ink-muted">{T.officerComment}: </span>
          {decision.comment}
        </p>
      ) : null}
      <Reasons reasons={decision.reasons} />
      {decision.improvements.length ? (
        <p className="m-0">
          <span className="text-ink-muted">{T.improvements}: </span>
          {decision.improvements.join("; ")}
        </p>
      ) : null}
    </li>
  );
}

function Decisions({ card }: { card: BankApplicationDetail }) {
  const decisions = chronological(card.decisions);
  return (
    <Section title={T.decisions} split>
      {decisions.length === 0 ? (
        <Empty>{T.noDecisions}</Empty>
      ) : (
        <ol aria-label={T.decisions} className="m-0 flex list-none flex-col gap-2 p-0">
          {decisions.map((decision) => (
            <DecisionItem key={decision.id} card={card} decision={decision} />
          ))}
        </ol>
      )}
    </Section>
  );
}

function InfoRequests({ requests }: { requests: Schemas["InfoRequest"][] }) {
  if (requests.length === 0) return null;
  return (
    <Section title={T.infoRequests}>
      <ul aria-label={T.infoRequests} className="m-0 flex list-none flex-col gap-1 p-0">
        {requests.map((request) => (
          <li key={request.id} className="break-inside-avoid">
            <span className="text-ink-muted">{formatDateTime(request.created_at)} · </span>
            {request.message}
            {request.document_kinds.length ? (
              <span className="text-ink-muted">
                {" "}
                ({A.documentsNeeded}:{" "}
                {request.document_kinds.map((kind) => DOCUMENT_KIND[kind]).join(", ")})
              </span>
            ) : null}
            <br />
            <span className="text-ink-muted">{T.clientAnswer}: </span>
            {request.response_message ?? T.noAnswer}
          </li>
        ))}
      </ul>
    </Section>
  );
}

function Offer({ offer }: { offer: Schemas["Offer"] | null }) {
  return (
    <Section title={T.offer}>
      {offer ? (
        <Pairs
          items={[
            {
              label: T.product,
              value: (
                <>
                  {offer.product.name}
                  {offer.is_counteroffer ? ` · ${A.counteroffer}` : ""}
                  {offer.product_changed ? ` · ${A.productChanged}` : ""}
                </>
              ),
            },
            { label: BANK_CARD.header.amount, value: formatMoney(offer.amount) },
            { label: A.rate, value: formatRate(offer.rate) },
            { label: A.term, value: A.months(offer.term_months) },
            {
              label: A.payment,
              value:
                offer.monthly_payment === null
                  ? A.revolvingPayment
                  : formatMoney(offer.monthly_payment),
            },
            { label: A.expires, value: formatDate(offer.expires_at) },
          ]}
        />
      ) : (
        <Empty>{T.noOffer}</Empty>
      )}
    </Section>
  );
}

function Footer({ card }: { card: BankApplicationDetail }) {
  return (
    <footer className="mt-2 flex break-inside-avoid flex-col gap-4 border-t border-line-strong pt-2">
      <p className="m-0 text-ink-muted">{T.footerDemo}</p>
      <div className="grid grid-cols-[auto_1fr_1fr] items-end gap-4">
        <span>
          {T.signature}: {card.assignee?.full_name ?? ""}
        </span>
        {[T.signatureLine, T.signatureDate].map((caption) => (
          <span key={caption} className="flex flex-col items-center gap-0.5">
            <span className="h-6 w-full border-b border-ink" />
            <span className="text-[10px] text-ink-muted">{caption}</span>
          </span>
        ))}
      </div>
    </footer>
  );
}

/**
 * XP3: the credit conclusion — everything from BankApplicationDetail, nothing computed here.
 * Sized for A4: compact type, blocks that do not split across pages.
 */
export function CreditConclusion({
  card,
  product,
  generatedAt,
}: {
  card: BankApplicationDetail;
  product: string;
  generatedAt: Date;
}) {
  return (
    <article
      aria-label={T.title}
      className="flex flex-col gap-3 bg-surface text-[12px] leading-[1.4] text-ink print:gap-2 print:text-[10.5px] print:leading-[1.35]"
    >
      <Head card={card} generatedAt={generatedAt} />
      <Client card={card} />
      <ApplicationBlock application={card.application} product={product} />
      <Checks checks={card.checks} />
      <Scoring score={card.score} />
      <Decisions card={card} />
      <InfoRequests requests={card.info_requests} />
      <Offer offer={card.offer} />
      <Footer card={card} />
    </article>
  );
}
