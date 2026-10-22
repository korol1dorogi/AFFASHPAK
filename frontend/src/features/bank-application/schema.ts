import { z } from "zod";
import type { Schemas } from "@/api/client";
import { percentToFraction } from "@/lib/format";
import { BANK_ACTIONS, BANK_CARD, DOCUMENT_KIND } from "@/texts";

/** CommentCreate (docs/openapi.yaml): message 1–2000 characters. */
export const commentSchema = z.object({
  message: z
    .string()
    .trim()
    .min(1, BANK_CARD.journal.commentRequired)
    .max(2000, BANK_CARD.journal.commentTooLong),
});

export type CommentValues = z.infer<typeof commentSchema>;

const E = BANK_ACTIONS.errors;

// Money as MoneyInput hands it over ("6500000.00"); zero and "invalid" fail. Same idea for a rate.
const POSITIVE_MONEY = /^(?!0+(?:\.0+)?$)\d+(?:\.\d{1,2})?$/;
const POSITIVE_RATE = /^(?!0+(?:\.0+)?$)\d+(?:\.\d+)?$/;

const text = (max: number) => z.string().trim().max(max, E.tooLong(max));

/** VersionedAction (approve): the comment to the client is optional. */
export const approveSchema = z.object({ comment: text(2000) });

export type ApproveValues = z.infer<typeof approveSchema>;

/**
 * CounterofferAction: other terms, or another product when `changeProduct` («Другой продукт»).
 * The rate is typed in percent and leaves as the API's annual fraction ("21,5" → "0.215").
 */
export function counterofferSchema(changeProduct: boolean) {
  return z.object({
    product_code: changeProduct ? z.string().min(1, E.product) : z.string(),
    amount: z.string().regex(POSITIVE_MONEY, E.amount),
    term_months: z.coerce.number<string | number>().int(E.term).min(1, E.term).max(360, E.term),
    rate: z.string().transform((value, ctx) => {
      const fraction = percentToFraction(value);
      if (fraction === null || !POSITIVE_RATE.test(fraction)) {
        ctx.addIssue({ code: "custom", message: E.rate });
        return z.NEVER;
      }
      return fraction;
    }),
    comment: text(2000).min(1, E.comment),
  });
}

export type CounterofferValues = z.input<ReturnType<typeof counterofferSchema>>;
export type CounterofferOutput = z.output<ReturnType<typeof counterofferSchema>>;

const DOCUMENT_KINDS = Object.keys(DOCUMENT_KIND) as [
  Schemas["DocumentKind"],
  ...Schemas["DocumentKind"][],
];

/** RequestInfoAction: what the client has to answer, and which documents to upload (if any). */
export const requestInfoSchema = z.object({
  message: text(2000).min(1, E.message),
  document_kinds: z.array(z.enum(DOCUMENT_KINDS)),
});

export type RequestInfoValues = z.infer<typeof requestInfoSchema>;

/** DeclineAction: reasons in plain words and at least one «что улучшить» (each up to 500). */
export const declineSchema = z.object({
  reasons_text: text(2000).min(1, E.reasons),
  improvements: z.array(z.object({ text: text(500).min(1, E.improvement) })).min(1, E.improvement),
});

export type DeclineValues = z.infer<typeof declineSchema>;
