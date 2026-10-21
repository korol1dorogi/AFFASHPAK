import { UserMinus } from "lucide-react";
import { type FormEvent, useState } from "react";
import { toast } from "sonner";

import type { Schemas } from "@/api/client";
import { ROLE_LABEL, useCompany, useMe } from "@/app/session";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Facts } from "@/components/Facts";
import { Field } from "@/components/Field";
import { ReasonList } from "@/components/ReasonList";
import { DemoBadge, ErrorState, PageHeader, PageSkeleton } from "@/components/States";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { Input, NativeSelect } from "@/components/ui/input";
import {
  useAddMember,
  useCompanyMetrics,
  useMembers,
  useRemoveMember,
  useRenameCompany,
} from "@/features/company/api";
import { errorMessage } from "@/lib/errors";
import { formatDate } from "@/lib/format";
import { COMPANY as T } from "@/texts";

/** C3: requisites from the registry (read-only), a short name, members and roles, metrics. */
export function CompanyPage() {
  const company = useCompany();
  const me = useMe();
  if (company.isPending || me.isPending) return <PageSkeleton />;
  if (company.isError || !company.data) {
    return (
      <ErrorState
        title={T.loadError}
        error={company.error}
        onRetry={() => void company.refetch()}
      />
    );
  }
  const isSignatory = company.data.my_role === "signatory";
  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={company.data.name} subtitle={T.profileSubtitle} />
      <Requisites company={company.data} canRename={isSignatory} />
      <Members canManage={isSignatory} myId={me.data?.id ?? 0} />
      <Metrics />
    </div>
  );
}

function Requisites({ company, canRename }: { company: Schemas["Company"]; canRename: boolean }) {
  const rename = useRenameCompany();
  const [name, setName] = useState(company.name);
  const changed = name.trim() !== company.name && name.trim().length > 0;
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!changed) return;
    rename.mutate(name.trim(), {
      onSuccess: () => toast.success(T.renamed),
      onError: (error) => toast.error(errorMessage(error)),
    });
  };
  return (
    <Card>
      <div className="flex flex-wrap items-center gap-2">
        <CardTitle className="m-0">{T.requisites}</CardTitle>
        {company.is_demo ? <DemoBadge /> : null}
      </div>
      <p className="m-0 text-sm text-ink-muted">{T.fromRegistryReadOnly}</p>
      <Facts
        items={[
          { label: T.inn, value: company.inn },
          { label: T.ogrn, value: company.ogrn },
          { label: T.okved, value: `${company.okved} ${company.okved_name}` },
          { label: T.registeredAt, value: formatDate(company.registered_at) },
          { label: T.director, value: company.director_name },
          { label: T.address, value: company.address },
          { label: T.status, value: T.registryStatus[company.registry_status] },
          { label: T.myRole, value: company.my_role ? ROLE_LABEL[company.my_role] : "—" },
        ]}
      />
      {canRename ? (
        <form onSubmit={submit} className="flex flex-wrap items-end gap-3">
          <Field label={T.shortName} hint={T.shortNameHint} className="min-w-72 flex-1">
            <Input value={name} maxLength={300} onChange={(event) => setName(event.target.value)} />
          </Field>
          <Button type="submit" variant="secondary" disabled={!changed} loading={rename.isPending}>
            {T.save}
          </Button>
        </form>
      ) : null}
    </Card>
  );
}

function Members({ canManage, myId }: { canManage: boolean; myId: number }) {
  const members = useMembers();
  const remove = useRemoveMember();
  const [removing, setRemoving] = useState<Schemas["Member"] | null>(null);
  return (
    <Card>
      <CardTitle className="m-0">{T.members}</CardTitle>
      {members.isError ? (
        <p className="m-0 text-status-danger">{errorMessage(members.error)}</p>
      ) : null}
      <ul aria-label={T.members} className="m-0 flex list-none flex-col gap-2 p-0">
        {(members.data ?? []).map((member) => (
          <li
            key={member.id}
            className="flex flex-wrap items-center gap-3 rounded-md border border-line p-3"
          >
            <span className="min-w-0 flex-1">
              <span className="block font-medium">{member.user.full_name}</span>
              <span className="text-sm text-ink-muted">
                {member.position} · {ROLE_LABEL[member.role]}
              </span>
            </span>
            {canManage && member.user.id !== myId ? (
              <Button variant="ghost" size="sm" onClick={() => setRemoving(member)}>
                <UserMinus aria-hidden="true" />
                {T.remove}
              </Button>
            ) : null}
          </li>
        ))}
      </ul>
      {canManage ? <AddMember /> : <p className="m-0 text-sm text-ink-muted">{T.onlySignatory}</p>}
      <ConfirmDialog
        open={removing !== null}
        onOpenChange={(open) => (open ? null : setRemoving(null))}
        title={T.removeTitle}
        text={removing ? T.removeText(removing.user.full_name) : ""}
        confirmLabel={T.remove}
        danger
        pending={remove.isPending}
        onConfirm={() => {
          if (!removing) return;
          remove.mutate(removing.id, {
            onSuccess: () => {
              toast.success(T.removed);
              setRemoving(null);
            },
            onError: (error) => toast.error(errorMessage(error)),
          });
        }}
      />
    </Card>
  );
}

function AddMember() {
  const add = useAddMember();
  const [username, setUsername] = useState("");
  const [position, setPosition] = useState("");
  const [role, setRole] = useState<Schemas["MemberRole"]>("preparer");
  const valid = username.trim() && position.trim();
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!valid) return;
    add.mutate(
      { username: username.trim(), position: position.trim(), role },
      {
        onSuccess: () => {
          toast.success(T.added);
          setUsername("");
          setPosition("");
        },
        onError: (error) => toast.error(errorMessage(error)),
      },
    );
  };
  return (
    <form onSubmit={submit} className="flex flex-col gap-3 border-t border-line pt-4">
      <p className="m-0 font-medium">{T.addTitle}</p>
      <p className="m-0 text-sm text-ink-muted">{T.addHint}</p>
      <div className="flex flex-wrap items-end gap-3">
        <Field label={T.username} className="min-w-44 flex-1">
          <Input value={username} onChange={(event) => setUsername(event.target.value)} />
        </Field>
        <Field label={T.position} className="min-w-44 flex-1">
          <Input value={position} onChange={(event) => setPosition(event.target.value)} />
        </Field>
        <Field label={T.role} className="min-w-44">
          <NativeSelect
            value={role}
            onChange={(event) => setRole(event.target.value as Schemas["MemberRole"])}
          >
            <option value="preparer">{ROLE_LABEL.preparer}</option>
            <option value="signatory">{ROLE_LABEL.signatory}</option>
          </NativeSelect>
        </Field>
        <Button type="submit" disabled={!valid} loading={add.isPending}>
          {T.add}
        </Button>
      </div>
    </form>
  );
}

function Metrics() {
  const metrics = useCompanyMetrics();
  if (!metrics.data) return null;
  return (
    <Card>
      <div className="flex flex-wrap items-center gap-2">
        <CardTitle className="m-0">{T.metrics}</CardTitle>
        {metrics.data.is_demo ? <DemoBadge /> : null}
      </div>
      {metrics.data.snapshot ? (
        <p className="m-0 text-sm text-ink-muted">
          {T.metricsPeriod(metrics.data.snapshot.period)}
        </p>
      ) : (
        <p className="m-0 text-sm text-ink-muted">{T.noStatement}</p>
      )}
      <ReasonList reasons={metrics.data.metrics} label={T.metrics} />
    </Card>
  );
}
