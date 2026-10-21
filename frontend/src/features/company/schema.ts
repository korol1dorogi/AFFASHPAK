import { z } from "zod";

import { innIsValid } from "@/lib/inn";

import { COMPANY } from "@/texts";

const E = COMPANY.errors;

// Limits mirror Inn, CompanyUpdate and MemberCreate in docs/openapi.yaml; the INN check digits
// follow the ФНС algorithm (the API checks them too, every registry INN passes).
export const innSchema = z.object({
  inn: z
    .string()
    .trim()
    .regex(/^\d{10}(\d{2})?$/, E.inn)
    .refine(innIsValid, E.innChecksum),
});

export type InnValues = z.infer<typeof innSchema>;

/** Empty — show the registry name again (the API stores null). */
export const nameSchema = z.object({
  short_name: z.string().trim().max(300, E.tooLong(300)),
});

export type NameValues = z.infer<typeof nameSchema>;

export const memberSchema = z.object({
  username: z.string().trim().min(1, E.username).max(150, E.tooLong(150)),
  position: z.string().trim().min(1, E.position).max(100, E.tooLong(100)),
  role: z.enum(["signatory", "preparer"]),
});

export type MemberValues = z.infer<typeof memberSchema>;
