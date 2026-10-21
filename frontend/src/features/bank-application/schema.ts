import { z } from "zod";

import { BANK_CARD } from "@/texts";

/** CommentCreate (docs/openapi.yaml): message 1–2000 characters. */
export const commentSchema = z.object({
  message: z
    .string()
    .trim()
    .min(1, BANK_CARD.journal.commentRequired)
    .max(2000, BANK_CARD.journal.commentTooLong),
});

export type CommentValues = z.infer<typeof commentSchema>;
