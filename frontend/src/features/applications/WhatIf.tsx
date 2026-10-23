import { useEffect, useId, useState } from "react";

import type { Schemas } from "@/api/client";
import { SourceTag } from "@/components/AmountSource";
import { Field } from "@/components/Field";
import { MoneyText } from "@/components/Money";
import { MoneyInput } from "@/components/MoneyInput";
import { ReasonList } from "@/components/ReasonList";
import { Badge } from "@/components/ui/badge";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { type ApplicationDetail, useWhatIf } from "@/features/applications/api";
import { errorMessage } from "@/lib/errors";
import { formatDecimal, formatMoney } from "@/lib/format";
import { cn } from "@/lib/utils";
import { WHAT_IF as T } from "@/texts";

type Offer = Schemas["Offer"];

const DEBOUNCE_MS = 300;
const AMOUNT_STEP = 10_000; // ₽ per slider step; the exact amount goes into the field below
const SLIDER =
  "h-11 w-full cursor-pointer accent-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus";

/** An active offer with a fixed payment whose amount or product the bank changed (XP1). */
export function showsWhatIf(application: ApplicationDetail): boolean {
  const offer = application.offer;
  return (
    application.status === "offer" &&
    offer !== null &&
    offer.status === "active" &&
    !offer.product.is_revolving &&
    (offer.is_counteroffer || offer.product_changed)
  );
}

/** Slider positions are whole rubles: the integer part of the API string, no float arithmetic. */
function wholeRubles(money: string): number {
  return Number.parseInt(money, 10);
}

function useDebounced<T>(value: T, ms: number): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), ms);
    return () => clearTimeout(timer);
  }, [value, ms]);
  return settled;
}

/**
 * «Что если» under the offer: amount and term sliders; the backend counts the payment, the DSCR
 * with it and the amount allowed for the term (credit_math). The offer itself does not change.
 */
export function WhatIf({ application, offer }: { application: ApplicationDetail; offer: Offer }) {
  const titleId = useId();
  const product = offer.product;
  const [amount, setAmount] = useState(offer.amount);
  const [term, setTerm] = useState(offer.term_months);
  const settledAmount = useDebounced(amount, DEBOUNCE_MS);
  const settledTerm = useDebounced(term, DEBOUNCE_MS);
  const whatIf = useWhatIf(application.id, settledAmount, settledTerm, {
    enabled: settledAmount !== "",
  });
  const result = whatIf.data;
  // The answer on screen is for other terms while the slider settles or the request runs.
  const stale =
    whatIf.isFetching ||
    (result !== undefined && (result.amount !== amount || result.term_months !== term));

  const low = wholeRubles(product.amount_min);
  // Up to what the client asked for (capped by the product), never below the offer itself.
  const high = Math.max(
    wholeRubles(offer.amount),
    Math.min(wholeRubles(product.amount_max), wholeRubles(application.requested_amount)),
  );

  return (
    <Card role="region" aria-labelledby={titleId}>
      <div className="flex flex-col gap-1">
        <CardTitle id={titleId}>{T.title}</CardTitle>
        <CardDescription>{T.subtitle}</CardDescription>
      </div>
      <div className="grid gap-6 sm:grid-cols-2">
        <div className="flex flex-col gap-2">
          <Field label={T.amount}>
            <input
              type="range"
              className={SLIDER}
              min={low}
              max={high}
              step={AMOUNT_STEP}
              value={amount === "" ? low : wholeRubles(amount)}
              aria-valuetext={amount === "" ? undefined : formatMoney(amount)}
              onChange={(event) => setAmount(`${event.target.value}.00`)}
            />
          </Field>
          <MoneyInput
            aria-label={T.amountExact}
            value={amount}
            // null — the text is not an amount yet: keep the last valid one
            onValueChange={(value) => {
              if (value !== null) setAmount(value);
            }}
          />
        </div>
        <div className="flex flex-col gap-2">
          <Field label={T.term}>
            <input
              type="range"
              className={SLIDER}
              min={product.term_min_months}
              max={product.term_max_months}
              step={1}
              value={term}
              aria-valuetext={T.months(term)}
              onChange={(event) => setTerm(Number(event.target.value))}
            />
          </Field>
          <p className="m-0 font-display text-xl leading-[26px] font-bold">{T.months(term)}</p>
        </div>
      </div>

      <div
        aria-live="polite"
        aria-busy={stale || undefined}
        className={cn(
          "flex flex-col gap-4 border-t border-line pt-4 transition-opacity",
          stale && "opacity-60",
        )}
      >
        {whatIf.isError ? (
          <p role="alert" className="m-0 text-sm text-status-danger">
            {errorMessage(whatIf.error)}
          </p>
        ) : result ? (
          <>
            <dl className="m-0 grid grid-cols-[repeat(auto-fit,minmax(160px,1fr))] gap-4">
              <div>
                <dt className="text-xs text-ink-muted">{T.payment}</dt>
                <dd className="m-0">
                  <MoneyText value={result.monthly_payment} size="md" />
                  <SourceTag source="calc" />
                </dd>
              </div>
              <div>
                <dt className="text-xs text-ink-muted">{T.maxAmount(result.term_months)}</dt>
                <dd className="m-0">
                  {result.max_amount === null ? (
                    <span className="text-sm">{T.noMaxAmount}</span>
                  ) : (
                    <>
                      <MoneyText value={result.max_amount} size="md" />
                      <SourceTag source="calc" />
                    </>
                  )}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-ink-muted">{T.coverage}</dt>
                <dd className="m-0 text-sm">
                  {result.dscr_after === null
                    ? T.noMaxAmount
                    : T.coverageValue(
                        formatDecimal(result.dscr_after),
                        formatDecimal(result.min_dscr),
                      )}
                </dd>
              </div>
            </dl>
            <Badge variant={result.fits ? "success" : "danger"} size="md">
              {result.fits ? T.fits : T.notFits}
            </Badge>
            {result.fits ? null : (
              <ReasonList
                reasons={result.reasons.filter((reason) => !reason.passed)}
                label={T.why}
              />
            )}
          </>
        ) : (
          <p className="m-0 text-sm text-ink-muted">{T.counting}</p>
        )}
      </div>
      <p className="m-0 text-xs text-ink-muted">{T.note}</p>
    </Card>
  );
}
