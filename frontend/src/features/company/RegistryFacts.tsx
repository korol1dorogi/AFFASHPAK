import { TriangleAlert } from "lucide-react";

import type { Schemas } from "@/api/client";
import { Badge } from "@/components/ui/badge";
import { COMPANY } from "@/features/company/texts";
import { formatDate } from "@/lib/format";
import { LEGAL_FORM, REGISTRY_STATUS } from "@/texts";

const T = COMPANY.record;

/** Requisites of an ЕГРЮЛ/ЕГРИП record, read-only: nobody types them in again (F12). */
export function RegistryFacts({ record }: { record: Schemas["RegistryRecord"] }) {
  const facts = [
    { label: T.name, value: record.name },
    { label: T.legalForm, value: LEGAL_FORM[record.legal_form] },
    { label: T.inn, value: record.inn },
    { label: T.ogrn, value: record.ogrn },
    { label: T.okved, value: `${record.okved} — ${record.okved_name}` },
    { label: T.registered, value: formatDate(record.registered_at) },
    { label: T.region, value: record.region },
    { label: T.address, value: record.address },
    { label: T.director, value: record.director_name },
  ];
  return (
    <dl className="m-0 grid gap-x-8 gap-y-3 sm:grid-cols-2">
      {facts.map((fact) => (
        <div key={fact.label} className="flex min-w-0 flex-col gap-0.5">
          <dt className="text-sm text-ink-muted">{fact.label}</dt>
          <dd className="m-0 break-words">{fact.value}</dd>
        </div>
      ))}
      <div className="flex flex-col gap-0.5">
        <dt className="text-sm text-ink-muted">{T.status}</dt>
        <dd className="m-0">
          <Badge variant={record.registry_status === "active" ? "success" : "danger"}>
            {REGISTRY_STATUS[record.registry_status]}
          </Badge>
        </dd>
      </div>
    </dl>
  );
}

/** Liquidating or liquidated: the company can be connected, but no loan will be issued. */
export function NotActiveWarning({ status }: { status: Schemas["RegistryStatus"] }) {
  if (status === "active") return null;
  return (
    <p
      role="status"
      className="m-0 flex items-start gap-2 rounded-md bg-status-danger-soft px-4 py-3 text-sm text-status-danger"
    >
      <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      {COMPANY.notActive}
    </p>
  );
}
