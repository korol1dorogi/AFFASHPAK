import { z } from "zod";

import { COMPANY } from "@/features/company/texts";

const E = COMPANY.errors;

// Limits mirror Inn, CompanyUpdate and MemberCreate in docs/openapi.yaml. The INN checksum is
// not checked: the contract asks only for the format, and synthetic registry INNs do not pass it.
export const innSchema = z.object({
  inn: z
    .string()
    .trim()
    .regex(/^\d{10}(\d{2})?$/, E.inn),
});

export type InnValues = z.infer<typeof innSchema>;

export const nameSchema = z.object({
  name: z.string().trim().min(1, E.name).max(300, E.tooLong(300)),
});

export type NameValues = z.infer<typeof nameSchema>;

export const memberSchema = z.object({
  username: z.string().trim().min(1, E.username).max(150, E.tooLong(150)),
  position: z.string().trim().min(1, E.position).max(100, E.tooLong(100)),
  role: z.enum(["signatory", "preparer"]),
});

export type MemberValues = z.infer<typeof memberSchema>;
