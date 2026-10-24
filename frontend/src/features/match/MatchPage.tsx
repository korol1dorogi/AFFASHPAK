import { useMutation } from "@tanstack/react-query";
import { CircleCheck, Clock, Package, Truck, Wrench } from "lucide-react";
import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router";

import { api, type Schemas } from "@/api/client";
import { routes } from "@/app/routes";
import { SourceTag } from "@/components/AmountSource";
import { Field } from "@/components/Field";
import { MoneyText, RateText } from "@/components/Money";
import { MoneyInput } from "@/components/MoneyInput";
import { ReasonList } from "@/components/ReasonList";
import { ErrorState, PageHeader } from "@/components/States";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useCreateApplication } from "@/features/applications/api";
import { errorMessage, unwrap } from "@/lib/errors";
import { cn } from "@/lib/utils";
import { NEED } from "@/texts";

type Need = Schemas["NeedType"];
type Offer = Schemas["RecommendedOffer"];

const NEED_ORDER: { need: Need; Icon: typeof Clock }[] = [
  { need: "cash_gap", Icon: Clock },
  { need: "receivable_delay", Icon: Truck },
  { need: "working_capital", Icon: Package },
  { need: "capex", Icon: Wrench },
];

function NeedPicker({ value, onChange }: { value: Need | null; onChange: (need: Need) => void }) {
  return (
    <fieldset className="m-0 flex flex-col gap-4 border-0 p-0">
      <legend className="mb-4 p-0 font-display text-[22px] leading-7 font-bold">
        Что случилось?
      </legend>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-4">
        {NEED_ORDER.map(({ need, Icon }) => {
          const selected = value === need;
          return (
            <label
              key={need}
              className={cn(
                "flex cursor-pointer flex-col gap-2 rounded-lg p-5 focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-focus",
                selected
                  ? "border-2 border-primary bg-primary-soft"
                  : "border border-line bg-surface hover:border-line-strong",
              )}
            >
              <input
                type="radio"
                name="need"
                value={need}
                checked={selected}
                onChange={() => onChange(need)}
                className="sr-only"
              />
              <span
                className={cn(
                  "flex items-center justify-between",
                  selected ? "text-primary-ink" : "text-ink-muted",
                )}
              >
                <Icon className="size-5" aria-hidden="true" />
                {selected ? <CircleCheck className="size-5" aria-hidden="true" /> : null}
              </span>
              <span className="font-semibold">{NEED[need].title}</span>
              <span className="text-sm text-ink-muted">{NEED[need].hint}</span>
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}

function OfferResult({
  offer,
  recommended,
  onApply,
  pending,
}: {
  offer: Offer;
  recommended: boolean;
  onApply: () => void;
  pending: boolean;
}) {
  return (
    <article
      aria-label={offer.product.name}
      className={cn(
        "overflow-hidden rounded-lg bg-surface",
        recommended ? "border-2 border-primary" : "border border-line",
      )}
    >
      <div className="flex flex-wrap items-start gap-6 p-6">
        <div className="flex min-w-0 flex-[1_1_360px] flex-col gap-2">
          <div className="flex flex-wrap gap-2">
            {recommended ? <Badge variant="brand">Рекомендуем</Badge> : null}
            {offer.fits ? (
              <Badge variant="success">
                <CircleCheck aria-hidden="true" />
                Подходит
              </Badge>
            ) : (
              <Badge variant="action">Есть ограничения</Badge>
            )}
          </div>
          <h3 className="m-0 text-xl leading-[26px] font-semibold">{offer.product.name}</h3>
          {offer.product.description ? (
            <p className="m-0 max-w-[56ch]">{offer.product.description}</p>
          ) : null}
        </div>
        <div
          className={cn(
            "flex flex-[0_1_280px] flex-col gap-1 rounded-lg px-5 py-4",
            recommended ? "bg-brass-soft" : "bg-sunken",
          )}
        >
          <span className="text-xs font-medium tracking-[0.02em] text-ink-muted">
            {offer.product.is_revolving ? "ЛИМИТ" : "СУММА"}
          </span>
          <p className="m-0">
            <MoneyText
              value={offer.amount}
              size={recommended ? "lg" : "md"}
              className={recommended ? "text-brass" : undefined}
            />
            <SourceTag source="calc" />
          </p>
          <span className="text-sm text-ink-muted">
            <RateText value={offer.rate} /> · {offer.term_months} мес ·{" "}
            {offer.monthly_payment === null ? (
              "платёж зависит от того, сколько возьмёте"
            ) : (
              <>
                платёж <MoneyText value={offer.monthly_payment} />
                <SourceTag source="calc" />
              </>
            )}
          </span>
        </div>
      </div>
      <div className="px-6 pb-6">
        <ReasonList reasons={offer.reasons} label="Почему этот вариант" />
      </div>
      <div className="flex flex-wrap items-center gap-3 border-t border-line px-6 py-4">
        <Button
          size={recommended ? "lg" : "default"}
          variant={recommended ? "default" : "secondary"}
          loading={pending}
          onClick={onApply}
        >
          Оформить заявку
        </Button>
        <span className="text-sm text-ink-muted">
          Заявка заполнится сама, останется проверить и отправить
        </span>
      </div>
    </article>
  );
}

export function MatchPage() {
  const [search, setSearch] = useSearchParams();
  const navigate = useNavigate();
  const initial = search.get("need");
  const [need, setNeed] = useState<Need | null>(
    NEED_ORDER.some((item) => item.need === initial) ? (initial as Need) : null,
  );
  const [amount, setAmount] = useState("");
  const [term, setTerm] = useState("");
  const [invoice, setInvoice] = useState("");
  const create = useCreateApplication();
  const [applying, setApplying] = useState<string | null>(null);

  const recommend = useMutation({
    mutationFn: async (body: Schemas["RecommendationRequest"]) =>
      unwrap(await api.POST("/api/recommendations", { body })),
  });

  const pick = (value: Need) => {
    setNeed(value);
    setSearch({ need: value }, { replace: true });
    recommend.reset();
  };

  const termNumber = Number(term);
  const termValid =
    term === "" || (Number.isInteger(termNumber) && termNumber >= 1 && termNumber <= 360);

  const run = () => {
    if (!need || !termValid) return;
    recommend.mutate({
      need_type: need,
      ...(amount ? { amount } : {}),
      ...(term ? { term_months: termNumber } : {}),
      ...(need === "receivable_delay" && invoice ? { invoice_amount: invoice } : {}),
    });
  };

  const apply = (offer: Offer) => {
    if (!need) return;
    setApplying(offer.product.code);
    create.mutate(
      {
        need_type: need,
        purpose: NEED[need].title,
        requested_amount: offer.amount,
        term_months: offer.term_months,
        product_code: offer.product.code,
        prefill_source: "recommendation",
        ...(need === "receivable_delay" && invoice ? { invoice_amount: invoice } : {}),
      },
      {
        onSuccess: (application) => navigate(routes.applicationEdit(application.id, "business")),
        onSettled: () => setApplying(null),
      },
    );
  };

  const result = recommend.data;
  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        title="Что вам нужно?"
        subtitle="Подберём подходящий вариант и сумму по данным вашего счёта. Это предварительная оценка, а не решение банка: окончательные условия банк назовёт после проверки заявки."
      />
      <NeedPicker value={need} onChange={pick} />

      {need ? (
        <section aria-labelledby="params-title" className="flex flex-col gap-4">
          <h2 id="params-title" className="m-0 font-display text-[22px] leading-7 font-bold">
            Параметры{" "}
            <span className="font-sans text-sm font-normal text-ink-muted">— необязательно</span>
          </h2>
          <form
            className="flex flex-wrap items-end gap-4"
            onSubmit={(event) => {
              event.preventDefault();
              run();
            }}
          >
            <Field label="Сколько нужно" className="w-56">
              <MoneyInput value={amount} onValueChange={(value) => setAmount(value ?? "")} />
            </Field>
            <Field
              label="На сколько месяцев"
              error={termValid ? undefined : "От 1 до 360 месяцев"}
              className="w-48"
            >
              <Input
                inputMode="numeric"
                value={term}
                onChange={(event) => setTerm(event.target.value.replace(/\D/g, ""))}
              />
            </Field>
            {need === "receivable_delay" ? (
              <Field label="Сумма отгрузки по УПД" className="w-56">
                <MoneyInput value={invoice} onValueChange={(value) => setInvoice(value ?? "")} />
              </Field>
            ) : null}
            <Button type="submit" size="lg" disabled={!termValid} loading={recommend.isPending}>
              {result ? "Пересчитать" : "Показать варианты"}
            </Button>
          </form>
        </section>
      ) : null}

      {recommend.isError ? (
        <ErrorState title="Не получилось подобрать" error={recommend.error} onRetry={run} />
      ) : null}
      {create.isError ? (
        <p role="alert" className="m-0 text-status-danger">
          {errorMessage(create.error)}
        </p>
      ) : null}

      {result ? (
        <section aria-labelledby="results-title" className="flex flex-col gap-4">
          <h2 id="results-title" className="m-0 font-display text-[22px] leading-7 font-bold">
            {result.offers.length
              ? `Варианты по данным вашего счёта: ${result.offers.length}`
              : "Подходящих вариантов нет"}
          </h2>
          {result.stop_factors.length ? (
            <Card className="border-status-danger">
              <p className="m-0 font-semibold">Почему сейчас не получится</p>
              <ReasonList reasons={result.stop_factors} label="Что мешает" />
            </Card>
          ) : null}
          {[...result.offers]
            .sort((a, b) => a.rank - b.rank)
            .map((offer, index) => (
              <OfferResult
                key={offer.product.code}
                offer={offer}
                recommended={index === 0 && offer.fits}
                pending={applying === offer.product.code}
                onApply={() => apply(offer)}
              />
            ))}
        </section>
      ) : null}
    </div>
  );
}
