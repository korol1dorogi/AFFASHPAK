import type { Schemas } from "@/api/client";
import { formatDateTime, formatDecimal } from "@/lib/format";
import { BANK_CARD, METRIC, metricTitle } from "@/texts";

const T = BANK_CARD.scoring;

/**
 * Max points of each scorecard factor — from docs/decision-model.md §4.
 * Remove when the contract gets ScoreFactor.max_points.
 */
export const FACTOR_MAX_POINTS: Readonly<Record<string, number>> = {
  business_age_months: 10,
  dscr: 25,
  debt_to_ebitda: 15,
  revenue_trend: 15,
  counterparty_concentration: 10,
  bki_history: 20,
  transparent_business: 5,
};

const NUMBER_RE = /^-?\d+(?:\.\d+)?$/;

export function factorValue(factor: Schemas["ScoreFactor"]): string {
  if (factor.value === null) return BANK_CARD.noValue;
  if (!NUMBER_RE.test(factor.value)) return factor.value;
  const format = METRIC[factor.name]?.format;
  const number = formatDecimal(factor.value);
  if (format === "months") return `${number} мес`;
  if (format === "days") return `${number} дн.`;
  return number;
}

/** Score explained factor by factor (design.md §3): the bank card and the credit conclusion. */
export function ScoreBreakdown({ score }: { score: Schemas["Score"] }) {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end gap-x-8 gap-y-3">
        <div>
          <p className="m-0 text-sm text-ink-muted">{T.grade}</p>
          <p className="m-0 font-display text-[40px] leading-[44px] font-bold">{score.grade}</p>
        </div>
        <div>
          <p className="m-0 text-sm text-ink-muted">{T.total}</p>
          <p className="tabular m-0 font-display text-2xl font-bold">{T.outOf(score.total)}</p>
        </div>
        <div className="text-sm text-ink-muted">
          <p className="m-0">
            {T.model}: <span className="text-ink">{score.model_version}</span>
          </p>
          <p className="m-0">{formatDateTime(score.created_at)}</p>
        </div>
      </div>
      <p className="m-0 text-sm text-ink-muted">{T.note}</p>
      <ul aria-label={T.factors} className="m-0 flex list-none flex-col gap-3 p-0">
        {score.factors.map((factor) => {
          const max = FACTOR_MAX_POINTS[factor.name];
          const value = factorValue(factor);
          return (
            <li
              key={factor.name}
              data-factor={factor.name}
              className="flex flex-col gap-2 rounded-md border border-line p-3"
            >
              <div className="flex flex-wrap items-baseline justify-between gap-x-4">
                <p className="m-0 font-semibold">
                  {metricTitle(factor.name)}
                  <span
                    className={
                      factor.value === null
                        ? "ml-2 font-normal text-ink-muted"
                        : "tabular ml-2 font-normal"
                    }
                  >
                    {value}
                  </span>
                </p>
                <span className="tabular font-semibold">{T.points(factor.points, max)}</span>
              </div>
              {max ? (
                <div className="h-1.5 overflow-hidden rounded-full bg-sunken" aria-hidden="true">
                  <div
                    className="h-full rounded-full bg-primary"
                    style={{ width: `${Math.min(100, (factor.points / max) * 100)}%` }}
                  />
                </div>
              ) : null}
              <p className="m-0 text-sm text-ink-muted">{factor.message}</p>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
