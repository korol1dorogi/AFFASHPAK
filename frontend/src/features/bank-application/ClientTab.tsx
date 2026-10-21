import { ROLE_LABEL } from "@/app/session";
import { MoneyText } from "@/components/Money";
import { DemoBadge, EmptyState } from "@/components/States";
import { Card, CardTitle } from "@/components/ui/card";
import type { BankApplicationDetail } from "@/features/bank-application/api";
import { Facts } from "@/features/bank-application/Facts";
import { formatDate, formatDecimal } from "@/lib/format";
import { BANK_CARD, LEGAL_FORM, REGISTRY_STATUS, SNAPSHOT_FIELD, SNAPSHOT_SOURCE } from "@/texts";

const T = BANK_CARD.client;

function NoData() {
  return <span className="text-ink-muted">{BANK_CARD.noValue}</span>;
}

function Snapshot({ snapshot }: { snapshot: NonNullable<BankApplicationDetail["snapshot"]> }) {
  const metrics = Object.entries(SNAPSHOT_FIELD) as [
    keyof typeof SNAPSHOT_FIELD,
    (typeof SNAPSHOT_FIELD)[keyof typeof SNAPSHOT_FIELD],
  ][];
  return (
    <>
      <Facts
        items={[
          { label: T.period, value: snapshot.period },
          { label: T.source, value: SNAPSHOT_SOURCE[snapshot.source] },
        ]}
      />
      <dl aria-label={T.snapshot} className="m-0 flex flex-col">
        {metrics.map(([key, field]) => {
          const value = snapshot[key];
          return (
            <div
              key={key}
              className="flex items-baseline justify-between gap-4 border-b border-line py-2 last:border-b-0"
            >
              <dt className="text-sm">{field.title}</dt>
              <dd className="tabular m-0 text-right">
                {value === null ? (
                  <NoData />
                ) : field.format === "money" ? (
                  <MoneyText value={value} />
                ) : (
                  formatDecimal(value)
                )}
              </dd>
            </div>
          );
        })}
      </dl>
    </>
  );
}

export function ClientTab({ card }: { card: BankApplicationDetail }) {
  const { company, members, snapshot } = card;
  return (
    <>
      <Card>
        <div className="flex flex-wrap items-center gap-2">
          <CardTitle>{T.requisites}</CardTitle>
          <span className="text-sm text-ink-muted">{T.requisitesNote}</span>
          {company.is_demo ? <DemoBadge /> : null}
        </div>
        <Facts
          items={[
            { label: T.name, value: company.name },
            { label: T.legalForm, value: LEGAL_FORM[company.legal_form] },
            { label: T.inn, value: <span className="tabular">{company.inn}</span> },
            { label: T.ogrn, value: <span className="tabular">{company.ogrn}</span> },
            { label: T.okved, value: `${company.okved} — ${company.okved_name}` },
            { label: T.registered, value: formatDate(company.registered_at) },
            { label: T.registryStatus, value: REGISTRY_STATUS[company.registry_status] },
            { label: T.director, value: company.director_name },
            { label: T.region, value: company.region },
            { label: T.address, value: company.address },
          ]}
        />
      </Card>

      <Card>
        <CardTitle>{T.members}</CardTitle>
        {members.length === 0 ? (
          <p className="m-0 text-ink-muted">{T.noMembers}</p>
        ) : (
          <ul aria-label={T.members} className="m-0 flex list-none flex-col gap-2 p-0">
            {members.map((member) => (
              <li key={member.id} className="flex flex-wrap items-baseline gap-x-3">
                <span className="font-medium">{member.user.full_name}</span>
                <span className="text-sm text-ink-muted">{member.position}</span>
                <span className="text-sm">{ROLE_LABEL[member.role]}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card>
        <CardTitle>{T.snapshot}</CardTitle>
        {snapshot ? (
          <Snapshot snapshot={snapshot} />
        ) : (
          <EmptyState title={T.noSnapshot} text={T.noSnapshotText} />
        )}
      </Card>
    </>
  );
}
