import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Navigate, useNavigate } from "react-router";
import { toast } from "sonner";

import type { Schemas } from "@/api/client";
import { routes } from "@/app/routes";
import { ROLE_LABEL, useMe } from "@/app/session";
import { Field } from "@/components/Field";
import { DemoBadge, PageHeader, Skeleton } from "@/components/States";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  useAcceptInvitation,
  useCreateCompany,
  useDeclineInvitation,
  useLookup,
  useMyInvitations,
} from "@/features/company/api";
import { NotActiveWarning, RegistryFacts } from "@/features/company/RegistryFacts";
import { type InnValues, innSchema } from "@/features/company/schema";
import { ApiError, errorMessage } from "@/lib/errors";
import { COMPANY } from "@/texts";

const T = COMPANY.create;
const I = COMPANY.invitations;

type IncomingInvitation = Schemas["IncomingInvitation"];

/**
 * Invitations into existing companies: joining one is an alternative to connecting your own.
 * Nothing is shown while loading fails or there are none — the INN path below still works.
 * `accept` lives in the page: the page must not bounce to the profile once `me` has a company.
 */
function Invitations({ accept }: { accept: ReturnType<typeof useAcceptInvitation> }) {
  const navigate = useNavigate();
  const invitations = useMyInvitations();
  const decline = useDeclineInvitation();
  const [busy, setBusy] = useState<number | null>(null);
  const [rest, setRest] = useState<string | null>(null);

  if (invitations.isPending) {
    return (
      <div role="status" aria-busy="true" aria-label={I.loading}>
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }
  if (invitations.isError || invitations.data.length === 0) return null;

  const companyName = (invitation: IncomingInvitation) =>
    invitation.company.short_name ?? invitation.company.name;

  return (
    <Card>
      <CardTitle>{I.title}</CardTitle>
      <CardDescription>{I.hint}</CardDescription>
      <ul aria-label={I.list} className="m-0 flex list-none flex-col gap-3 p-0">
        {invitations.data.map((invitation) => {
          const name = companyName(invitation);
          return (
            <li
              key={invitation.id}
              className="flex flex-col gap-3 rounded-md border border-line p-4 sm:flex-row sm:items-center"
            >
              <div className="flex min-w-0 flex-1 flex-col gap-1">
                <span className="font-semibold">{name}</span>
                <span className="text-sm">
                  {ROLE_LABEL[invitation.role]} · {invitation.position}
                </span>
                <span className="text-sm text-ink-muted">
                  {COMPANY.record.inn} {invitation.company.inn}
                  {invitation.invited_by
                    ? ` · ${I.invitedBy(invitation.invited_by.full_name)}`
                    : ""}
                </span>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  aria-label={I.acceptLabel(name)}
                  loading={accept.isPending && busy === invitation.id}
                  disabled={busy !== null && busy !== invitation.id}
                  onClick={() => {
                    setRest(null);
                    setBusy(invitation.id);
                    accept.mutate(invitation.id, {
                      onSuccess: () => {
                        toast.success(I.accepted);
                        navigate(routes.home, { replace: true });
                      },
                      onError: (error) => setRest(errorMessage(error)),
                      onSettled: () => setBusy(null),
                    });
                  }}
                >
                  {I.accept}
                </Button>
                <Button
                  variant="secondary"
                  aria-label={I.declineLabel(name)}
                  loading={decline.isPending && busy === invitation.id}
                  disabled={busy !== null && busy !== invitation.id}
                  onClick={() => {
                    setRest(null);
                    setBusy(invitation.id);
                    decline.mutate(invitation.id, {
                      onSuccess: () => toast.success(I.declined),
                      onError: (error) => setRest(errorMessage(error)),
                      onSettled: () => setBusy(null),
                    });
                  }}
                >
                  {I.decline}
                </Button>
              </div>
            </li>
          );
        })}
      </ul>
      {rest ? (
        <p role="alert" className="m-0 text-sm text-status-danger">
          {rest}
        </p>
      ) : null}
      <p className="m-0 text-sm text-ink-muted">{I.orOwn}</p>
    </Card>
  );
}

/** ИНН → record from ЕГРЮЛ/ЕГРИП → «Это моя компания». Nothing but the INN is typed. */
export function CompanyNewPage() {
  const me = useMe();
  const navigate = useNavigate();
  const [inn, setInn] = useState<string | null>(null);
  const lookup = useLookup(inn);
  const create = useCreateCompany();
  const accept = useAcceptInvitation();
  // Pending too: `me` gets the company in onSuccess, a moment before the mutation settles.
  const joined = accept.isPending || accept.isSuccess;
  const [rest, setRest] = useState<string | null>(null);
  const form = useForm<InnValues>({ resolver: zodResolver(innSchema), defaultValues: { inn: "" } });

  // Already has a company (and did not just create or join it here) → the profile.
  if (me.data?.company_id && !create.isSuccess && !joined) {
    return <Navigate to={routes.company} replace />;
  }

  const lookupError = lookup.isError ? lookup.error : null;
  const unavailable = lookupError instanceof ApiError && lookupError.status === 503;
  const innError =
    form.formState.errors.inn?.message ??
    (lookupError && !unavailable ? errorMessage(lookupError) : undefined);
  const record = inn !== null ? lookup.data : undefined;

  const find = form.handleSubmit((values) => {
    setRest(null);
    if (values.inn === inn) void lookup.refetch();
    else setInn(values.inn);
  });

  const startOver = () => {
    setInn(null);
    setRest(null);
    form.reset({ inn: "" });
    form.setFocus("inn");
  };

  return (
    <div className="mx-auto flex w-full max-w-[640px] flex-col gap-6">
      <PageHeader title={T.title} subtitle={T.subtitle} />
      <Invitations accept={accept} />
      <Card>
        <form noValidate onSubmit={find} className="flex flex-col gap-4 sm:flex-row sm:items-start">
          <Field label={T.inn} hint={T.innHint} error={innError} className="flex-1">
            <Input
              inputMode="numeric"
              autoComplete="off"
              maxLength={12}
              {...form.register("inn", {
                // A changed INN is a new search: the old record and errors go.
                onChange: () => {
                  setInn(null);
                  setRest(null);
                },
              })}
            />
          </Field>
          <Button
            type="submit"
            variant={record ? "secondary" : "default"}
            loading={lookup.isFetching}
            className="sm:mt-6"
          >
            {T.find}
          </Button>
        </form>
        {unavailable ? (
          <div
            role="alert"
            className="flex flex-wrap items-center gap-3 text-sm text-status-danger"
          >
            <span>{errorMessage(lookupError)}</span>
            <Button variant="secondary" size="sm" onClick={() => void lookup.refetch()}>
              {T.retry}
            </Button>
          </div>
        ) : null}
      </Card>
      {record ? (
        <Card>
          <div className="flex flex-wrap items-center gap-2">
            <CardTitle>{T.found}</CardTitle>
            <Badge variant="brand">{COMPANY.fromRegistry}</Badge>
            <DemoBadge />
          </div>
          <RegistryFacts record={record} />
          <NotActiveWarning status={record.registry_status} />
          {rest ? (
            <p role="alert" className="m-0 text-sm text-status-danger">
              {rest}
            </p>
          ) : null}
          <div className="flex flex-wrap gap-3">
            <Button
              loading={create.isPending}
              onClick={() => {
                setRest(null);
                create.mutate(record.inn, {
                  onSuccess: () => {
                    toast.success(T.done);
                    navigate(routes.home, { replace: true });
                  },
                  onError: (error) => setRest(errorMessage(error)),
                });
              }}
            >
              {T.confirm}
            </Button>
            <Button variant="secondary" onClick={startOver}>
              {T.other}
            </Button>
          </div>
        </Card>
      ) : null}
    </div>
  );
}
