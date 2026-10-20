import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { Controller, type UseFormReturn, useForm, useWatch } from "react-hook-form";
import { z } from "zod";

import type { Schemas } from "@/api/client";
import { Field } from "@/components/Field";
import { MoneyInput } from "@/components/MoneyInput";
import { Input, NativeSelect, Textarea } from "@/components/ui/input";
import { useProducts } from "@/features/applications/api";
import { NEED } from "@/texts";

const MONEY = /^\d+(\.\d{1,2})?$/;
const NEED_TYPES = ["cash_gap", "receivable_delay", "working_capital", "capex"] as const;

/** Products that fit each need (docs/knowledge/credit.md, «Подбор»). */
export const KINDS_FOR_NEED: Record<Schemas["NeedType"], Schemas["ProductKind"][]> = {
  cash_gap: ["overdraft"],
  receivable_delay: ["factoring"],
  working_capital: ["working_capital_loan"],
  capex: ["investment_loan", "leasing"],
};

// Limits mirror ApplicationCreate / ApplicationUpdate in docs/openapi.yaml.
export const paramsSchema = z
  .object({
    need_type: z.enum(NEED_TYPES),
    purpose: z.string().trim().min(1, "Напишите, на что нужны деньги").max(1000),
    requested_amount: z.string().regex(MONEY, "Укажите сумму"),
    term_months: z.coerce
      .number<string | number>()
      .int("Целое число месяцев")
      .min(1, "От 1 месяца")
      .max(360, "Не больше 360 месяцев"),
    product_code: z.string(),
    invoice_amount: z.string(),
    collateral_description: z.string().max(1000),
  })
  .superRefine((values, ctx) => {
    if (values.need_type === "receivable_delay" && !MONEY.test(values.invoice_amount)) {
      ctx.addIssue({
        code: "custom",
        path: ["invoice_amount"],
        message: "Укажите сумму из документа отгрузки",
      });
    }
  });

export type ParamsValues = z.input<typeof paramsSchema>;
export type ParamsOutput = z.output<typeof paramsSchema>;
export const PARAM_FIELDS = [
  "need_type",
  "purpose",
  "requested_amount",
  "term_months",
  "product_code",
  "invoice_amount",
  "collateral_description",
] as const;

export function emptyParams(need?: Schemas["NeedType"]): ParamsValues {
  return {
    need_type: need ?? "cash_gap",
    purpose: "",
    requested_amount: "",
    term_months: 12,
    product_code: "",
    invoice_amount: "",
    collateral_description: "",
  };
}

export function paramsFromApplication(application: Schemas["Application"]): ParamsValues {
  return {
    need_type: application.need_type,
    purpose: application.purpose,
    requested_amount: application.requested_amount,
    term_months: application.term_months,
    product_code: application.product_code ?? "",
    invoice_amount: application.invoice_amount ?? "",
    collateral_description: application.collateral_description ?? "",
  };
}

/** Form values → the API body (empty optional fields become null / are left out). */
export function paramsToBody(values: ParamsOutput) {
  return {
    need_type: values.need_type,
    purpose: values.purpose,
    requested_amount: values.requested_amount,
    term_months: values.term_months,
    product_code: values.product_code || null,
    invoice_amount: values.need_type === "receivable_delay" ? values.invoice_amount || null : null,
    collateral_description: values.collateral_description.trim() || null,
  };
}

export function useParamsForm(defaultValues: ParamsValues) {
  return useForm<ParamsValues, unknown, ParamsOutput>({
    resolver: zodResolver(paramsSchema),
    defaultValues,
    mode: "onChange",
  });
}

export function ParamsFields({
  form,
}: {
  form: UseFormReturn<ParamsValues, unknown, ParamsOutput>;
}) {
  const products = useProducts();
  const need = useWatch({ control: form.control, name: "need_type" });
  const { errors } = form.formState;
  const suitable = (products.data ?? []).filter((product) =>
    KINDS_FOR_NEED[need].includes(product.kind),
  );

  // A product that does not fit the new need is cleared.
  const productCode = useWatch({ control: form.control, name: "product_code" });
  useEffect(() => {
    if (productCode && products.data && !suitable.some((product) => product.code === productCode)) {
      form.setValue("product_code", "", { shouldDirty: true });
    }
  }, [productCode, products.data, suitable, form]);

  return (
    <div className="grid grid-cols-[repeat(auto-fit,minmax(260px,1fr))] gap-4">
      <Field label="Что случилось" error={errors.need_type?.message}>
        <NativeSelect {...form.register("need_type")}>
          {NEED_TYPES.map((value) => (
            <option key={value} value={value}>
              {NEED[value].title}
            </option>
          ))}
        </NativeSelect>
      </Field>
      <Field label="Продукт" hint="Можно оставить выбор банку" error={errors.product_code?.message}>
        <NativeSelect {...form.register("product_code")}>
          <option value="">Подберёт банк</option>
          {suitable.map((product) => (
            <option key={product.code} value={product.code}>
              {product.name}
            </option>
          ))}
        </NativeSelect>
      </Field>
      <Field label="Сумма" error={errors.requested_amount?.message}>
        <Controller
          control={form.control}
          name="requested_amount"
          render={({ field }) => (
            <MoneyInput
              name={field.name}
              value={field.value}
              onBlur={field.onBlur}
              onValueChange={(value) => field.onChange(value ?? "invalid")}
            />
          )}
        />
      </Field>
      <Field label="Срок, месяцев" error={errors.term_months?.message}>
        <Input
          type="number"
          inputMode="numeric"
          min={1}
          max={360}
          {...form.register("term_months")}
        />
      </Field>
      {need === "receivable_delay" ? (
        <Field label="Сумма отгрузки по УПД" error={errors.invoice_amount?.message}>
          <Controller
            control={form.control}
            name="invoice_amount"
            render={({ field }) => (
              <MoneyInput
                name={field.name}
                value={field.value}
                onBlur={field.onBlur}
                onValueChange={(value) => field.onChange(value ?? "invalid")}
              />
            )}
          />
        </Field>
      ) : null}
      <Field label="На что нужны деньги" error={errors.purpose?.message} className="col-span-full">
        <Textarea maxLength={1000} {...form.register("purpose")} />
      </Field>
      {need === "capex" ? (
        <Field
          label="Что можете предложить в залог"
          hint="Можно оставить пустым — банк подскажет"
          error={errors.collateral_description?.message}
          className="col-span-full"
        >
          <Textarea maxLength={1000} {...form.register("collateral_description")} />
        </Field>
      ) : null}
    </div>
  );
}
