import type { Schemas } from "@/api/client";
import { type AmountSource, SourceTag } from "@/components/AmountSource";
import { MoneyText, RateText } from "@/components/Money";
import { ReasonList } from "@/components/ReasonList";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatDate, formatMoney } from "@/lib/format";
import { ACTION, PRODUCT_KIND } from "@/texts";

type Offer = Schemas["Offer"];

/**
 * The bank's offer: the main amount, terms, why (for a counteroffer or another product) and the
 * two client actions. Buttons appear only when available_actions allows them. Every amount says
 * where it comes from (SRC7): `amountSource` — «расчёт» or «решение банка» (offerAmountSource).
 */
export function OfferCard({
  offer,
  actions,
  amountSource = "calc",
  onAccept,
  onDecline,
  pending,
}: {
  offer: Offer;
  actions: Schemas["ApplicationAction"][];
  amountSource?: AmountSource;
  onAccept?: () => void;
  onDecline?: () => void;
  pending?: "accept" | "decline" | null;
}) {
  const canAccept = actions.includes("accept_offer");
  const canDecline = actions.includes("decline_offer");
  const why = offer.reasons.length > 0 && (offer.is_counteroffer || offer.product_changed);
  return (
    <article
      aria-label="Предложение банка"
      className="overflow-hidden rounded-lg border border-line bg-surface"
    >
      <div className="flex flex-col gap-1 bg-brass-soft p-6">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-medium tracking-[0.02em] text-ink-muted">
            {PRODUCT_KIND[offer.product.kind].toUpperCase()}
          </span>
          {offer.is_counteroffer ? <Badge variant="action">Иные условия</Badge> : null}
          {offer.product_changed ? <Badge variant="action">Другой продукт</Badge> : null}
          {offer.status === "accepted" ? <Badge variant="success">Принято</Badge> : null}
        </div>
        <p className="m-0">
          <MoneyText value={offer.amount} size="lg" className="text-brass" />
          <SourceTag source={amountSource} />
        </p>
        {offer.is_counteroffer ? (
          <span className="text-sm text-ink-muted">
            Вы просили {formatMoney(offer.requested_amount)}
            <SourceTag source="you" />
          </span>
        ) : null}
      </div>
      <dl className="m-0 grid grid-cols-[repeat(auto-fit,minmax(140px,1fr))] gap-4 border-b border-line p-6">
        <div>
          <dt className="text-xs text-ink-muted">Ставка</dt>
          <dd className="m-0">
            <RateText value={offer.rate} size="md" />
          </dd>
        </div>
        <div>
          <dt className="text-xs text-ink-muted">Срок</dt>
          <dd className="m-0 font-display text-xl leading-[26px] font-bold">
            {offer.term_months}&nbsp;мес
          </dd>
        </div>
        <div>
          <dt className="text-xs text-ink-muted">Платёж в месяц</dt>
          <dd className="m-0">
            {offer.monthly_payment === null ? (
              <span className="text-sm">Зависит от того, сколько возьмёте</span>
            ) : (
              <>
                <MoneyText value={offer.monthly_payment} size="md" />
                <SourceTag source="calc" />
              </>
            )}
          </dd>
        </div>
      </dl>
      {why ? (
        <div className="flex flex-col gap-3 border-b border-line p-6">
          <p className="m-0 font-semibold">
            {offer.product_changed ? "Почему другой продукт" : "Почему меньше, чем вы просили"}
          </p>
          <ReasonList reasons={offer.reasons} label="Почему такие условия" />
        </div>
      ) : null}
      {canAccept || canDecline ? (
        <div className="flex flex-wrap items-center gap-3 px-6 py-4">
          {canAccept ? (
            <Button size="lg" onClick={onAccept} loading={pending === "accept"}>
              {ACTION.accept_offer}
            </Button>
          ) : null}
          {canDecline ? (
            <Button variant="danger" onClick={onDecline} loading={pending === "decline"}>
              {ACTION.decline_offer}
            </Button>
          ) : null}
          <span className="text-sm text-ink-muted">
            Действует до {formatDate(offer.expires_at)}
          </span>
        </div>
      ) : null}
    </article>
  );
}
