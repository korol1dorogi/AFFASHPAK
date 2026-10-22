import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Navigate } from "react-router";
import { toast } from "sonner";

import type { Schemas } from "@/api/client";
import { routes } from "@/app/routes";
import { ROLE_LABEL, useCompany, useMe } from "@/app/session";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Field } from "@/components/Field";
import { DemoBadge, ErrorState, PageHeader, PageSkeleton, Skeleton } from "@/components/States";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { Input, NativeSelect } from "@/components/ui/input";
import {
  useCancelInvitation,
  useInvitations,
  useInvite,
  useMembers,
  useRemoveMember,
  useUpdateCompany,
} from "@/features/company/api";
import { NotActiveWarning, RegistryFacts } from "@/features/company/RegistryFacts";
import { Integrations, Metrics } from "@/features/company/Sources";
import {
  type InviteValues,
  inviteSchema,
  type NameValues,
  nameSchema,
} from "@/features/company/schema";
import { ApiError, applyFieldErrors, errorMessage } from "@/lib/errors";
import { COMPANY, LEGAL_FORM } from "@/texts";

const P = COMPANY.profile;
const M = COMPANY.members;

type Company = Schemas["Company"];
type Member = Schemas["Member"];
type Invitation = Schemas["Invitation"];

function Requisites({ company }: { company: Company }) {
  return (
    <Card>
      <div className="flex flex-wrap items-center gap-2">
        <CardTitle>{P.requisites}</CardTitle>
        <Badge variant="brand">{COMPANY.fromRegistry}</Badge>
      </div>
      <CardDescription>{P.requisitesNote}</CardDescription>
      <RegistryFacts record={company} />
      <NotActiveWarning status={company.registry_status} />
    </Card>
  );
}

/** Signatory only (PATCH /api/company answers 403 to a preparer). */
function ShortNameForm({ company }: { company: Company }) {
  const update = useUpdateCompany();
  const [rest, setRest] = useState<string | null>(null);
  const form = useForm<NameValues>({
    resolver: zodResolver(nameSchema),
    defaultValues: { short_name: company.short_name ?? "" },
  });

  const submit = form.handleSubmit(({ short_name }) => {
    setRest(null);
    update.mutate(
      { short_name: short_name || null },
      {
        onSuccess: (saved) => {
          form.reset({ short_name: saved.short_name ?? "" });
          toast.success(P.saved);
        },
        onError: (error) => setRest(applyFieldErrors(error, form.setError, ["short_name"])),
      },
    );
  });

  return (
    <Card>
      <form noValidate onSubmit={submit} className="flex flex-col gap-4 sm:flex-row sm:items-start">
        <Field
          label={P.shortName}
          hint={P.shortNameHint}
          error={form.formState.errors.short_name?.message}
          className="flex-1"
        >
          <Input
            maxLength={300}
            autoComplete="organization"
            placeholder={company.name}
            {...form.register("short_name")}
          />
        </Field>
        <Button
          type="submit"
          variant="secondary"
          loading={update.isPending}
          disabled={!form.formState.isDirty}
          className="sm:mt-6"
        >
          {P.save}
        </Button>
      </form>
      {rest ? (
        <p role="alert" className="m-0 text-sm text-status-danger">
          {rest}
        </p>
      ) : null}
    </Card>
  );
}

/** The login is only invited: the person joins after accepting in their own cabinet. */
function InviteForm() {
  const invite = useInvite();
  const [rest, setRest] = useState<string | null>(null);
  const form = useForm<InviteValues>({
    resolver: zodResolver(inviteSchema),
    defaultValues: { username: "", position: "", role: "preparer" },
  });
  const { errors } = form.formState;

  const submit = form.handleSubmit((values) => {
    setRest(null);
    invite.mutate(values, {
      onSuccess: () => {
        form.reset({ username: "", position: "", role: "preparer" });
        toast.success(M.invited);
      },
      onError: (error) => {
        // 409 «уже в компании» / «уже приглашён» is about the login field.
        if (error instanceof ApiError && error.status === 409) {
          form.setError("username", { type: "server", message: error.message });
          return;
        }
        setRest(applyFieldErrors(error, form.setError, ["username", "position", "role"]));
      },
    });
  });

  return (
    <form noValidate onSubmit={submit} className="flex flex-col gap-4 border-t border-line pt-4">
      <div className="flex flex-col gap-1">
        <h3 className="m-0 text-base font-semibold">{M.invite}</h3>
        <p className="m-0 text-sm text-ink-muted">{M.inviteHint}</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label={M.username} error={errors.username?.message}>
          <Input autoComplete="off" maxLength={150} {...form.register("username")} />
        </Field>
        <Field label={M.position} error={errors.position?.message}>
          <Input
            maxLength={100}
            placeholder={M.positionPlaceholder}
            {...form.register("position")}
          />
        </Field>
        <Field label={M.role} error={errors.role?.message}>
          <NativeSelect {...form.register("role")}>
            <option value="preparer">{ROLE_LABEL.preparer}</option>
            <option value="signatory">{ROLE_LABEL.signatory}</option>
          </NativeSelect>
        </Field>
      </div>
      {rest ? (
        <p role="alert" className="m-0 text-sm text-status-danger">
          {rest}
        </p>
      ) : null}
      <div>
        <Button type="submit" variant="secondary" loading={invite.isPending}>
          {M.invite}
        </Button>
      </div>
    </form>
  );
}

/** Invitations nobody has answered yet; the signatory can take one back. Hidden when empty. */
function PendingInvitations({ canManage }: { canManage: boolean }) {
  const invitations = useInvitations();
  const cancel = useCancelInvitation();
  const [cancelling, setCancelling] = useState<Invitation | null>(null);

  if (invitations.isPending) {
    return (
      <div role="status" aria-busy="true" aria-label={M.pendingLoading}>
        <Skeleton className="h-12 w-full" />
      </div>
    );
  }
  if (invitations.isError) {
    return <ErrorState error={invitations.error} onRetry={() => void invitations.refetch()} />;
  }
  if (invitations.data.length === 0) return null;

  return (
    <div className="flex flex-col gap-2">
      <h3 className="m-0 text-base font-semibold">{M.pending}</h3>
      <ul aria-label={M.pending} className="m-0 flex list-none flex-col gap-2 p-0">
        {invitations.data.map((invitation) => (
          <li
            key={invitation.id}
            className="flex flex-wrap items-center gap-3 rounded-md border border-dashed border-line p-3"
          >
            <div className="flex min-w-0 flex-1 flex-col">
              <span className="font-semibold">{invitation.username}</span>
              <span className="text-sm text-ink-muted">
                {M.invitedAs(ROLE_LABEL[invitation.role], invitation.position)}
              </span>
            </div>
            <Badge variant="neutral">{M.pending}</Badge>
            {canManage ? (
              <Button
                variant="ghost"
                size="sm"
                aria-label={M.cancel(invitation.username)}
                loading={cancel.isPending && cancelling?.id === invitation.id}
                onClick={() => {
                  setCancelling(invitation);
                  cancel.mutate(invitation.id, {
                    onSuccess: () => toast.success(M.cancelled),
                    onError: (error) => toast.error(errorMessage(error)),
                    onSettled: () => setCancelling(null),
                  });
                }}
              >
                {M.cancelShort}
              </Button>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Everyone sees who is in the company; only a signatory invites and removes (never themselves). */
function Members({ canManage, meId }: { canManage: boolean; meId: number | undefined }) {
  const members = useMembers();
  const remove = useRemoveMember();
  const [removing, setRemoving] = useState<Member | null>(null);

  return (
    <Card>
      <CardTitle>{M.title}</CardTitle>
      <CardDescription>{M.rolesHint}</CardDescription>
      {members.isPending ? (
        <div role="status" aria-busy="true" aria-label={M.loading} className="flex flex-col gap-2">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      ) : members.isError ? (
        <ErrorState error={members.error} onRetry={() => void members.refetch()} />
      ) : members.data.length === 0 ? (
        <p className="m-0 text-ink-muted">{M.empty}</p>
      ) : (
        <ul aria-label={M.title} className="m-0 flex list-none flex-col gap-2 p-0">
          {members.data.map((member) => {
            const isMe = member.user.id === meId;
            return (
              <li
                key={member.id}
                className="flex flex-wrap items-center gap-3 rounded-md border border-line p-3"
              >
                <div className="flex min-w-0 flex-1 flex-col">
                  <span className="font-semibold">
                    {member.user.full_name}
                    {isMe ? <span className="font-normal text-ink-muted"> · {M.you}</span> : null}
                  </span>
                  <span className="text-sm text-ink-muted">{member.position}</span>
                </div>
                <Badge variant={member.role === "signatory" ? "brand" : "neutral"}>
                  {ROLE_LABEL[member.role]}
                </Badge>
                {canManage && !isMe ? (
                  <Button
                    variant="ghost"
                    size="sm"
                    aria-label={M.remove(member.user.full_name)}
                    onClick={() => setRemoving(member)}
                  >
                    {M.removeShort}
                  </Button>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
      <PendingInvitations canManage={canManage} />
      {canManage ? <InviteForm /> : <p className="m-0 text-sm text-ink-muted">{M.readOnly}</p>}
      <ConfirmDialog
        open={removing !== null}
        onOpenChange={(open) => {
          if (!open) setRemoving(null);
        }}
        title={M.removeTitle}
        text={removing ? M.removeText(removing.user.full_name) : ""}
        confirmLabel={M.removeShort}
        danger
        pending={remove.isPending}
        onConfirm={() => {
          if (!removing) return;
          remove.mutate(removing.id, {
            onSuccess: () => toast.success(M.removed),
            onError: (error) => toast.error(errorMessage(error)),
            onSettled: () => setRemoving(null),
          });
        }}
      />
    </Card>
  );
}

/** Profile: requisites read-only «из ЕГРЮЛ», short name and members for the signatory. */
export function CompanyPage() {
  const company = useCompany();
  const me = useMe();

  if (company.isPending) return <PageSkeleton />;
  if (company.isError) {
    return <ErrorState error={company.error} onRetry={() => void company.refetch()} />;
  }
  if (!company.data) return <Navigate to={routes.companyNew} replace />;

  const data = company.data;
  const signatory = data.my_role === "signatory";
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={data.short_name ?? data.name}
        subtitle={`${LEGAL_FORM[data.legal_form]} · ${COMPANY.record.inn} ${data.inn}`}
      >
        {data.is_demo ? <DemoBadge /> : null}
      </PageHeader>
      <Requisites company={data} />
      {signatory ? <ShortNameForm company={data} /> : null}
      <Integrations company={data} />
      <Metrics />
      <Members canManage={signatory} meId={me.data?.id} />
    </div>
  );
}
