import { Building2 } from "lucide-react";
import { type FormEvent, useState } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";

import { routes } from "@/app/routes";
import { Facts } from "@/components/Facts";
import { Field } from "@/components/Field";
import { DemoBadge, PageHeader } from "@/components/States";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useCreateCompany, useLookup } from "@/features/company/api";
import { errorMessage } from "@/lib/errors";
import { formatDate } from "@/lib/format";
import { COMPANY as T } from "@/texts";

const INN = /^\d{10}(\d{2})?$/;

/** C3: INN → the registry fills the rest → the user confirms. No re-typing (F12). */
export function CompanyNewPage() {
  const navigate = useNavigate();
  const [inn, setInn] = useState("");
  const [asked, setAsked] = useState<string | null>(null);
  const lookup = useLookup(asked);
  const create = useCreateCompany();
  const valid = INN.test(inn);

  const find = (event: FormEvent) => {
    event.preventDefault();
    if (valid) setAsked(inn);
  };
  const connect = () => {
    if (!asked) return;
    create.mutate(asked, {
      onSuccess: () => {
        toast.success(T.connected);
        navigate(routes.home, { replace: true });
      },
      onError: (error) => toast.error(errorMessage(error)),
    });
  };
  const record = lookup.data;

  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <PageHeader title={T.newTitle} subtitle={T.newSubtitle} />
      <Card>
        <form onSubmit={find} className="flex flex-wrap items-end gap-3">
          <Field
            label={T.inn}
            hint={T.innHint}
            error={inn && !valid ? T.innError : undefined}
            className="min-w-60 flex-1"
          >
            <Input
              inputMode="numeric"
              autoComplete="off"
              value={inn}
              maxLength={12}
              onChange={(event) => setInn(event.target.value.replace(/\D/g, ""))}
            />
          </Field>
          <Button type="submit" disabled={!valid} loading={lookup.isFetching}>
            {T.find}
          </Button>
        </form>
      </Card>

      {asked && !lookup.isFetching && record === null ? (
        <Card>
          <p className="m-0">{T.notFound}</p>
        </Card>
      ) : null}
      {lookup.isError ? (
        <Card>
          <p className="m-0 text-status-danger">{errorMessage(lookup.error)}</p>
        </Card>
      ) : null}

      {record ? (
        <Card>
          <div className="flex flex-wrap items-center gap-2">
            <Building2 className="size-5 text-primary-ink" aria-hidden="true" />
            <CardTitle className="m-0">{record.name}</CardTitle>
            <DemoBadge />
          </div>
          <p className="m-0 text-sm text-ink-muted">{T.fromRegistry}</p>
          <Facts
            items={[
              { label: T.inn, value: record.inn },
              { label: T.ogrn, value: record.ogrn },
              { label: T.okved, value: `${record.okved} ${record.okved_name}` },
              { label: T.registeredAt, value: formatDate(record.registered_at) },
              { label: T.director, value: record.director_name },
              { label: T.address, value: record.address },
              { label: T.status, value: T.registryStatus[record.registry_status] },
            ]}
          />
          <div className="flex flex-wrap items-center gap-3">
            <Button size="lg" onClick={connect} loading={create.isPending}>
              {T.connect}
            </Button>
            <span className="text-sm text-ink-muted">{T.youWillBeSignatory}</span>
          </div>
        </Card>
      ) : null}
    </div>
  );
}
