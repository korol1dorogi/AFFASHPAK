import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router";

import type { Schemas } from "@/api/client";
import { routes, WIZARD_STEPS } from "@/app/routes";
import { PageHeader } from "@/components/States";
import { Stepper } from "@/components/Stepper";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  emptyParams,
  PARAM_FIELDS,
  ParamsFields,
  paramsToBody,
  useParamsForm,
} from "@/features/application-wizard/ParamsForm";
import { STEP_LABEL } from "@/features/application-wizard/steps";
import { useCreateApplication } from "@/features/applications/api";
import { applyFieldErrors } from "@/lib/errors";

const NEEDS = new Set(["cash_gap", "receivable_delay", "working_capital", "capex"]);

/** Step «Параметры» before the application exists; «Далее» creates the draft. */
export function NewApplicationPage() {
  const [search] = useSearchParams();
  const need = search.get("need");
  const navigate = useNavigate();
  const create = useCreateApplication();
  const form = useParamsForm(
    emptyParams(need && NEEDS.has(need) ? (need as Schemas["NeedType"]) : undefined),
  );
  const [rest, setRest] = useState<string | null>(null);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Новая заявка"
        subtitle="Черновик сохраняется автоматически после первого шага."
      />
      <Stepper
        steps={WIZARD_STEPS.map((key) => ({ key, label: STEP_LABEL[key] }))}
        current="params"
        label="Шаги заявки"
      />
      <Card>
        <form
          noValidate
          className="flex flex-col gap-6"
          onSubmit={form.handleSubmit((values) => {
            setRest(null);
            const body = paramsToBody(values);
            create.mutate(
              {
                ...body,
                product_code: body.product_code ?? undefined,
                invoice_amount: body.invoice_amount ?? undefined,
                collateral_description: body.collateral_description ?? undefined,
                prefill_source: "manual",
              },
              {
                onSuccess: (application) =>
                  navigate(routes.applicationEdit(application.id, "business"), { replace: true }),
                onError: (error) => setRest(applyFieldErrors(error, form.setError, PARAM_FIELDS)),
              },
            );
          })}
        >
          <ParamsFields form={form} />
          {rest ? (
            <p role="alert" className="m-0 text-sm text-status-danger">
              {rest}
            </p>
          ) : null}
          <Button type="submit" size="lg" className="self-start" loading={create.isPending}>
            Далее
          </Button>
        </form>
      </Card>
    </div>
  );
}
