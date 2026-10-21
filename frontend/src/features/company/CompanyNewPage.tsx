import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Navigate, useNavigate } from "react-router";
import { toast } from "sonner";

import { routes } from "@/app/routes";
import { useMe } from "@/app/session";
import { Field } from "@/components/Field";
import { DemoBadge, PageHeader } from "@/components/States";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useCreateCompany, useLookup } from "@/features/company/api";
import { NotActiveWarning, RegistryFacts } from "@/features/company/RegistryFacts";
import { type InnValues, innSchema } from "@/features/company/schema";
import { COMPANY } from "@/features/company/texts";
import { ApiError, errorMessage } from "@/lib/errors";

const T = COMPANY.create;

/** ИНН → record from ЕГРЮЛ/ЕГРИП → «Это моя компания». Nothing but the INN is typed. */
export function CompanyNewPage() {
  const me = useMe();
  const navigate = useNavigate();
  const [inn, setInn] = useState<string | null>(null);
  const lookup = useLookup(inn);
  const create = useCreateCompany();
  const [rest, setRest] = useState<string | null>(null);
  const form = useForm<InnValues>({ resolver: zodResolver(innSchema), defaultValues: { inn: "" } });

  // Already has a company (and did not just create it here) → the profile.
  if (me.data?.company_id && !create.isSuccess) return <Navigate to={routes.company} replace />;

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
