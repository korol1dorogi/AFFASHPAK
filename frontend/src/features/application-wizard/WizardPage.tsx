import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router";
import { toast } from "sonner";

import { api, type Schemas } from "@/api/client";
import { routes, WIZARD_STEPS, type WizardStep } from "@/app/routes";
import { useCompany } from "@/app/session";
import { MoneyText } from "@/components/Money";
import { ReasonList } from "@/components/ReasonList";
import { DemoBadge, ErrorState, PageHeader, PageSkeleton } from "@/components/States";
import { Stepper } from "@/components/Stepper";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import {
  PARAM_FIELDS,
  ParamsFields,
  paramsFromApplication,
  paramsToBody,
  useParamsForm,
} from "@/features/application-wizard/ParamsForm";
import { STEP_LABEL } from "@/features/application-wizard/steps";
import {
  type ApplicationDetail,
  useApplication,
  useDocuments,
  useProducts,
  useSubmit,
  useUpdateApplication,
} from "@/features/applications/api";
import { DocumentList, DocumentUpload, RequiredDocuments } from "@/features/applications/Documents";
import { applyFieldErrors, errorMessage, fieldMessages, isConflict } from "@/lib/errors";
import { formatDateTime } from "@/lib/format";
import { useIdempotencyKey } from "@/lib/idempotency";
import { ACTION, BKI_CONSENT, DOCUMENT_KIND, NEED } from "@/texts";

const AUTOSAVE_MS = 800;
const ALL_KINDS = Object.keys(DOCUMENT_KIND) as Schemas["DocumentKind"][];

function useProduct(code: string | null) {
  const products = useProducts();
  return code ? (products.data?.find((product) => product.code === code) ?? null) : null;
}

/** Step «Параметры»: changes are saved by themselves with the current version (409 → banner). */
function ParamsStep({ application }: { application: ApplicationDetail }) {
  const update = useUpdateApplication(application.id);
  const form = useParamsForm(paramsFromApplication(application));
  const version = useRef(application.version);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [conflict, setConflict] = useState(false);
  const [rest, setRest] = useState<string | null>(null);
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => {
    version.current = application.version;
  }, [application.version]);

  // The latest save function lives in a ref: the effect below must not re-run on every render,
  // or each keystroke would reset the debounce timer and nothing would ever be saved.
  const save = useRef<() => void>(() => undefined);
  save.current = () => {
    void form.handleSubmit((values) => {
      update.mutate(
        { version: version.current, ...paramsToBody(values) },
        {
          onSuccess: (detail) => {
            version.current = detail.version;
            setSavedAt(new Date().toISOString());
            setRest(null);
          },
          onError: (error) => {
            if (isConflict(error)) setConflict(true);
            else setRest(applyFieldErrors(error, form.setError, PARAM_FIELDS));
          },
        },
      );
    })();
  };

  useEffect(() => {
    const subscription = form.watch((_values, { type }) => {
      if (type !== "change") return;
      window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => {
        timer.current = undefined;
        save.current();
      }, AUTOSAVE_MS);
    });
    return () => {
      subscription.unsubscribe();
      // Leaving the step before the debounce fired: save right away instead of losing the edit.
      if (timer.current !== undefined) {
        window.clearTimeout(timer.current);
        save.current();
      }
    };
  }, [form]);

  return (
    <Card>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <CardTitle>Параметры</CardTitle>
        <span className="text-sm text-ink-muted" aria-live="polite">
          {update.isPending
            ? "Сохраняем…"
            : savedAt
              ? `Сохранено · ${formatDateTime(savedAt).split(", ")[1]}`
              : "Черновик сохраняется сам"}
        </span>
      </div>
      {conflict ? (
        <div
          role="alert"
          className="flex flex-wrap items-center gap-3 rounded-md bg-status-action-soft p-4"
        >
          <span className="flex-1">Заявку изменили в другой вкладке или с другого устройства.</span>
          <Button
            variant="secondary"
            onClick={() => {
              form.reset(paramsFromApplication(application));
              version.current = application.version;
              setConflict(false);
            }}
          >
            Загрузить актуальную
          </Button>
        </div>
      ) : null}
      <ParamsFields form={form} />
      {rest ? <p className="m-0 text-sm text-status-danger">{rest}</p> : null}
    </Card>
  );
}

function BusinessStep() {
  const company = useCompany();
  const metrics = useQuery({
    queryKey: ["company", "metrics"],
    queryFn: async () => {
      const result = await api.GET("/api/company/metrics");
      if (result.response.status === 404) return null;
      if (!result.data) throw new Error("metrics");
      return result.data;
    },
  });
  return (
    <Card>
      <div className="flex flex-wrap items-center gap-2">
        <CardTitle>О бизнесе</CardTitle>
        {company.data?.is_demo ? <DemoBadge /> : null}
      </div>
      <CardDescription>
        Эти данные уже есть в профиле компании — вводить заново не нужно. Ошибка в реквизитах?{" "}
        <Link to={routes.company}>Исправить в профиле</Link>
      </CardDescription>
      {company.data ? (
        <dl className="m-0 grid grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-4">
          {[
            ["Компания", company.data.name],
            ["ИНН", company.data.inn],
            ["ОГРН", company.data.ogrn],
            ["Вид деятельности", `${company.data.okved} ${company.data.okved_name}`],
            ["Регион", company.data.region],
            ["Руководитель", company.data.director_name],
          ].map(([term, value]) => (
            <div key={term}>
              <dt className="text-xs text-ink-muted">{term}</dt>
              <dd className="m-0">{value || "—"}</dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className="m-0 text-ink-muted">Профиль компании ещё не заполнен.</p>
      )}
      {metrics.data?.metrics.length ? (
        <>
          <p className="m-0 font-semibold">По данным счёта</p>
          <ReasonList reasons={metrics.data.metrics} label="Показатели бизнеса" />
        </>
      ) : null}
    </Card>
  );
}

function DocumentsStep({ application }: { application: ApplicationDetail }) {
  const product = useProduct(application.product_code);
  const required = product?.required_documents ?? [];
  return (
    <Card>
      <CardTitle>Документы</CardTitle>
      <CardDescription>
        {product
          ? `Для продукта «${product.name}» банку нужны:`
          : "Продукт подберёт банк — загрузите выписку, если она есть."}
      </CardDescription>
      <RequiredDocuments applicationId={application.id} required={required} />
      <DocumentUpload
        applicationId={application.id}
        kinds={required.length ? [...required, "other"] : ALL_KINDS}
      />
      <DocumentList applicationId={application.id} />
    </Card>
  );
}

function ReviewStep({ application }: { application: ApplicationDetail }) {
  const navigate = useNavigate();
  const submit = useSubmit(application.id);
  const idempotency = useIdempotencyKey();
  const product = useProduct(application.product_code);
  const documents = useDocuments(application.id);
  const members = useQuery({
    queryKey: ["company", "members"],
    queryFn: async () => (await api.GET("/api/company/members")).data ?? [],
  });
  const signatory = members.data?.find((member) => member.role === "signatory");
  const missing = (product?.required_documents ?? []).filter(
    (kind) => !documents.data?.some((document) => document.kind === kind),
  );
  const canSubmit = application.available_actions.includes("submit");
  const [consent, setConsent] = useState(false);
  const [consentMissing, setConsentMissing] = useState(false);

  return (
    <Card>
      <CardTitle>Проверка и отправка</CardTitle>
      <dl className="m-0 grid grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-4">
        <div>
          <dt className="text-xs text-ink-muted">Задача</dt>
          <dd className="m-0">{NEED[application.need_type].title}</dd>
        </div>
        <div>
          <dt className="text-xs text-ink-muted">Продукт</dt>
          <dd className="m-0">{product?.name ?? "Не выбран"}</dd>
        </div>
        <div>
          <dt className="text-xs text-ink-muted">Сумма и срок</dt>
          <dd className="m-0">
            <MoneyText value={application.requested_amount} className="font-semibold" /> на{" "}
            {application.term_months} мес
          </dd>
        </div>
        <div className="col-span-full">
          <dt className="text-xs text-ink-muted">На что нужны деньги</dt>
          <dd className="m-0">{application.purpose}</dd>
        </div>
      </dl>
      {missing.length ? (
        <p className="m-0 rounded-md bg-status-action-soft p-3 text-sm">
          Не хватает: {missing.map((kind) => DOCUMENT_KIND[kind]).join(", ")}. Можно отправить и так
          — банк запросит их позже, но проверка займёт дольше.
        </p>
      ) : null}
      {submit.isError ? (
        <div role="alert" className="m-0 text-sm text-status-danger">
          <p className="m-0">{errorMessage(submit.error)}</p>
          {fieldMessages(submit.error).length ? (
            <ul className="m-0 pl-5">
              {fieldMessages(submit.error).map((message) => (
                <li key={message}>{message}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
      {canSubmit ? (
        <>
          <div className="flex flex-col gap-2 rounded-md border border-line p-3">
            <label className="flex cursor-pointer items-start gap-3">
              <input
                type="checkbox"
                checked={consent}
                onChange={(event) => {
                  setConsent(event.target.checked);
                  if (event.target.checked) setConsentMissing(false);
                }}
                aria-describedby="bki-consent-text"
                aria-invalid={consentMissing}
                className="mt-1 size-4 shrink-0"
              />
              <span className="font-semibold">{BKI_CONSENT.label}</span>
            </label>
            <p id="bki-consent-text" className="m-0 pl-7 text-sm text-ink-muted">
              {BKI_CONSENT.text}
            </p>
            {consentMissing ? (
              <p role="alert" className="m-0 pl-7 text-sm text-status-danger">
                {BKI_CONSENT.required}
              </p>
            ) : null}
          </div>
          <Button
            size="lg"
            className="self-start"
            loading={submit.isPending}
            onClick={() => {
              if (!consent) {
                setConsentMissing(true);
                return;
              }
              submit.mutate(
                { key: idempotency.current(), version: application.version },
                {
                  onSuccess: () => {
                    idempotency.renew();
                    toast.success("Заявка отправлена в банк");
                    navigate(routes.application(application.id));
                  },
                },
              );
            }}
          >
            {ACTION.submit}
          </Button>
        </>
      ) : (
        <p className="m-0 rounded-md bg-sunken p-3">
          Отправить заявку может подписант{signatory ? `: ${signatory.user.full_name}` : ""}.
          Черновик сохранён — он увидит его в своём кабинете.
        </p>
      )}
    </Card>
  );
}

export function WizardPage() {
  const params = useParams();
  const id = Number(params.id);
  const step = params.step as WizardStep;
  const application = useApplication(id, { poll: false });

  if (!WIZARD_STEPS.includes(step))
    return <Navigate to={routes.applicationEdit(id, "params")} replace />;
  if (application.isPending) return <PageSkeleton />;
  if (application.isError)
    return <ErrorState error={application.error} onRetry={() => application.refetch()} />;
  const data = application.data;
  if (data.status !== "draft" || !data.available_actions.includes("edit")) {
    return <Navigate to={routes.application(id)} replace />;
  }

  const index = WIZARD_STEPS.indexOf(step);
  const previous = WIZARD_STEPS[index - 1];
  const next = WIZARD_STEPS[index + 1];

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={`Заявка № ${data.id}`} subtitle="Черновик — банк его ещё не видит." />
      <Stepper
        label="Шаги заявки"
        current={step}
        steps={WIZARD_STEPS.map((key) => ({
          key,
          label: STEP_LABEL[key],
          to: routes.applicationEdit(id, key),
        }))}
      />
      {step === "params" ? <ParamsStep application={data} /> : null}
      {step === "business" ? <BusinessStep /> : null}
      {step === "documents" ? <DocumentsStep application={data} /> : null}
      {step === "review" ? <ReviewStep application={data} /> : null}
      <div className="flex flex-wrap gap-3">
        {previous ? (
          <Button asChild variant="secondary">
            <Link to={routes.applicationEdit(id, previous)}>Назад</Link>
          </Button>
        ) : null}
        {next ? (
          <Button asChild variant={step === "review" ? "secondary" : "default"}>
            <Link to={routes.applicationEdit(id, next)}>Далее: {STEP_LABEL[next]}</Link>
          </Button>
        ) : null}
      </div>
    </div>
  );
}
