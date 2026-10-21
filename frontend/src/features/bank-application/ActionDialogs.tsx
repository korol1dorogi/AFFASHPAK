import { zodResolver } from "@hookform/resolvers/zod";
import { X } from "lucide-react";
import { type FormEvent, type ReactNode, useMemo, useState } from "react";
import {
  Controller,
  type FieldValues,
  type Path,
  type UseFormSetError,
  useFieldArray,
  useForm,
  useWatch,
} from "react-hook-form";
import { toast } from "sonner";

import type { Schemas } from "@/api/client";
import { Field } from "@/components/Field";
import { MoneyInput } from "@/components/MoneyInput";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input, NativeSelect, Textarea } from "@/components/ui/input";
import {
  type BankApplicationDetail,
  useApprove,
  useCounteroffer,
  useDecline,
  useProducts,
  useRequestInfo,
} from "@/features/bank-application/api";
import {
  type ApproveValues,
  approveSchema,
  type CounterofferOutput,
  type CounterofferValues,
  counterofferSchema,
  type DeclineValues,
  declineSchema,
  type RequestInfoValues,
  requestInfoSchema,
} from "@/features/bank-application/schema";
import { BANK_ACTIONS } from "@/features/bank-application/texts";
import { applyFieldErrors, errorMessage, isConflict } from "@/lib/errors";
import { formatMoney, formatRate } from "@/lib/format";

const T = BANK_ACTIONS;

interface DialogProps {
  card: BankApplicationDetail;
  onClose: () => void;
}

/** The last failed send: a 409 (the card is being re-read) or text that matched no form field. */
interface Problem {
  conflict: boolean;
  text: string;
}

function problemOf<V extends FieldValues>(
  error: unknown,
  setError: UseFormSetError<V>,
  fields: readonly Path<V>[],
): Problem | null {
  if (isConflict(error)) return { conflict: true, text: errorMessage(error) };
  const rest = applyFieldErrors(error, setError, fields);
  return rest ? { conflict: false, text: rest } : null;
}

/**
 * Frame of every action: form, 409 banner, «Отмена» and the confirm button. Same primitives as
 * ConfirmDialog, plus the confirm is disabled once the action has left available_actions.
 * The form keeps what was typed, so a 409 never loses it.
 */
function ActionDialog({
  card,
  action,
  title,
  text,
  confirmLabel,
  danger = false,
  pending,
  problem,
  onClose,
  onSubmit,
  children,
}: DialogProps & {
  action: Schemas["ApplicationAction"];
  title: string;
  text: string;
  confirmLabel: string;
  danger?: boolean;
  pending: boolean;
  problem: Problem | null;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  children: ReactNode;
}) {
  const available = card.application.available_actions.includes(action);
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent className="max-h-[calc(100dvh-32px)] w-[min(520px,calc(100%-32px))] overflow-y-auto">
        <DialogTitle>{title}</DialogTitle>
        <DialogDescription>{text}</DialogDescription>
        <form noValidate onSubmit={onSubmit} className="flex flex-col gap-4">
          {children}
          {problem ? (
            <div
              role="alert"
              className="flex flex-col gap-1 rounded-md bg-status-danger-soft px-4 py-3 text-sm text-status-danger"
            >
              <p className="m-0">{problem.text}</p>
              {problem.conflict && available ? <p className="m-0">{T.conflictHint}</p> : null}
            </div>
          ) : null}
          {available ? null : (
            <p role="status" className="m-0 text-sm text-ink-muted">
              {T.unavailable}
            </p>
          )}
          <div className="flex flex-wrap justify-end gap-3">
            <DialogClose asChild>
              <Button type="button" variant="secondary">
                {T.cancel}
              </Button>
            </DialogClose>
            <Button
              type="submit"
              variant={danger ? "danger" : "default"}
              loading={pending}
              disabled={!available}
            >
              {confirmLabel}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function latestDecision(card: BankApplicationDetail) {
  return [...card.decisions].sort((a, b) => b.created_at.localeCompare(a.created_at))[0];
}

/** manual_review → offer on the requested terms; the comment to the client is optional. */
export function ApproveDialog({ card, onClose }: DialogProps) {
  const { application } = card;
  const approve = useApprove(application.id);
  const [problem, setProblem] = useState<Problem | null>(null);
  const form = useForm<ApproveValues>({
    resolver: zodResolver(approveSchema),
    defaultValues: { comment: "" },
  });

  // Re-created on every render, so a retry after 409 sends the version of the re-read card.
  const submit = form.handleSubmit(({ comment }) => {
    setProblem(null);
    approve.mutate(
      { version: application.version, ...(comment ? { comment } : {}) },
      {
        onSuccess: () => {
          toast.success(T.approve.done);
          onClose();
        },
        onError: (error) => setProblem(problemOf(error, form.setError, ["comment"])),
      },
    );
  });

  return (
    <ActionDialog
      card={card}
      onClose={onClose}
      action="approve"
      title={T.approve.title}
      text={T.approve.text(formatMoney(application.requested_amount), application.term_months)}
      confirmLabel={T.approve.confirm}
      pending={approve.isPending}
      problem={problem}
      onSubmit={submit}
    >
      <Field
        label={T.fields.comment}
        hint={T.fields.commentOptional}
        error={form.formState.errors.comment?.message}
      >
        <Textarea maxLength={2000} {...form.register("comment")} />
      </Field>
    </ActionDialog>
  );
}

/**
 * Other terms («Иные условия») or another product («Другой продукт») — both are counteroffer.
 * Hints: the amount the client's cash flow carries (latest decision) and the product's rate range.
 */
export function CounterofferDialog({
  card,
  onClose,
  changeProduct,
}: DialogProps & { changeProduct: boolean }) {
  const { application } = card;
  const counteroffer = useCounteroffer(application.id);
  const products = useProducts();
  const [problem, setProblem] = useState<Problem | null>(null);
  const schema = useMemo(() => counterofferSchema(changeProduct), [changeProduct]);
  const form = useForm<CounterofferValues, unknown, CounterofferOutput>({
    resolver: zodResolver(schema),
    defaultValues: {
      product_code: "",
      amount: application.requested_amount,
      term_months: application.term_months,
      rate: "",
      comment: "",
    },
  });
  const chosen = useWatch({ control: form.control, name: "product_code" });
  const productCode = changeProduct ? chosen : application.product_code;
  const product = products.data?.find((item) => item.code === productCode);
  const others = products.data?.filter((item) => item.code !== application.product_code) ?? [];
  const maxLoan = latestDecision(card)?.reasons.find(
    (reason) => reason.metric === "max_loan_by_dscr" && reason.value !== null,
  )?.value;
  const errors = form.formState.errors;
  const t = changeProduct ? T.product : T.counteroffer;

  const submit = form.handleSubmit(({ product_code, ...terms }) => {
    setProblem(null);
    counteroffer.mutate(
      { version: application.version, ...terms, ...(changeProduct ? { product_code } : {}) },
      {
        onSuccess: () => {
          toast.success(t.done);
          onClose();
        },
        onError: (error) =>
          setProblem(
            problemOf(error, form.setError, [
              "product_code",
              "amount",
              "term_months",
              "rate",
              "comment",
            ]),
          ),
      },
    );
  });

  return (
    <ActionDialog
      card={card}
      onClose={onClose}
      action="counteroffer"
      title={t.title}
      text={t.text}
      confirmLabel={t.confirm}
      pending={counteroffer.isPending}
      problem={problem}
      onSubmit={submit}
    >
      {changeProduct ? (
        <Field label={T.fields.product} error={errors.product_code?.message}>
          <NativeSelect {...form.register("product_code")}>
            <option value="">{T.fields.chooseProduct}</option>
            {others.map((item) => (
              <option key={item.code} value={item.code}>
                {item.name}
              </option>
            ))}
          </NativeSelect>
        </Field>
      ) : null}
      {/* Field gives its direct child the id, so it wraps MoneyInput, not the Controller. */}
      <Controller
        control={form.control}
        name="amount"
        render={({ field }) => (
          <Field
            label={T.fields.amount}
            hint={maxLoan ? T.fields.amountHint(formatMoney(maxLoan)) : undefined}
            error={errors.amount?.message}
          >
            <MoneyInput
              name={field.name}
              value={field.value}
              onBlur={field.onBlur}
              onValueChange={(value) => field.onChange(value ?? "invalid")}
            />
          </Field>
        )}
      />
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={T.fields.term} error={errors.term_months?.message}>
          <Input
            type="number"
            inputMode="numeric"
            min={1}
            max={360}
            {...form.register("term_months")}
          />
        </Field>
        <Field
          label={T.fields.rate}
          hint={
            product
              ? T.fields.rateHint(formatRate(product.rate_min), formatRate(product.rate_max))
              : undefined
          }
          error={errors.rate?.message}
        >
          <Input inputMode="decimal" autoComplete="off" {...form.register("rate")} />
        </Field>
      </div>
      <Field label={T.fields.comment} hint={T.fields.commentHint} error={errors.comment?.message}>
        <Textarea maxLength={2000} {...form.register("comment")} />
      </Field>
    </ActionDialog>
  );
}

/** manual_review → info_requested: the text the client answers (documents are named in it). */
export function RequestInfoDialog({ card, onClose }: DialogProps) {
  const { application } = card;
  const requestInfo = useRequestInfo(application.id);
  const [problem, setProblem] = useState<Problem | null>(null);
  const form = useForm<RequestInfoValues>({
    resolver: zodResolver(requestInfoSchema),
    defaultValues: { message: "" },
  });

  const submit = form.handleSubmit(({ message }) => {
    setProblem(null);
    requestInfo.mutate(
      { version: application.version, message },
      {
        onSuccess: () => {
          toast.success(T.requestInfo.done);
          onClose();
        },
        onError: (error) => setProblem(problemOf(error, form.setError, ["message"])),
      },
    );
  });

  return (
    <ActionDialog
      card={card}
      onClose={onClose}
      action="request_info"
      title={T.requestInfo.title}
      text={T.requestInfo.text}
      confirmLabel={T.requestInfo.confirm}
      pending={requestInfo.isPending}
      problem={problem}
      onSubmit={submit}
    >
      <Field
        label={T.requestInfo.message}
        hint={T.requestInfo.messageHint}
        error={form.formState.errors.message?.message}
      >
        <Textarea maxLength={2000} {...form.register("message")} />
      </Field>
    </ActionDialog>
  );
}

/** manual_review → declined: reasons in plain words and at least one «что улучшить». */
export function DeclineDialog({ card, onClose }: DialogProps) {
  const { application } = card;
  const decline = useDecline(application.id);
  const [problem, setProblem] = useState<Problem | null>(null);
  const form = useForm<DeclineValues>({
    resolver: zodResolver(declineSchema),
    defaultValues: { reasons_text: "", improvements: [{ text: "" }] },
  });
  const improvements = useFieldArray({ control: form.control, name: "improvements" });
  const errors = form.formState.errors;
  const listError = errors.improvements?.message ?? errors.improvements?.root?.message;

  const submit = form.handleSubmit(({ reasons_text, improvements: items }) => {
    setProblem(null);
    decline.mutate(
      {
        version: application.version,
        reasons_text,
        improvements: items.map((item) => item.text),
      },
      {
        onSuccess: () => {
          toast.success(T.decline.done);
          onClose();
        },
        onError: (error) =>
          setProblem(problemOf(error, form.setError, ["reasons_text", "improvements"])),
      },
    );
  });

  return (
    <ActionDialog
      card={card}
      onClose={onClose}
      action="decline"
      title={T.decline.title}
      text={T.decline.text}
      confirmLabel={T.decline.confirm}
      danger
      pending={decline.isPending}
      problem={problem}
      onSubmit={submit}
    >
      <Field label={T.decline.reasons} error={errors.reasons_text?.message}>
        <Textarea maxLength={2000} {...form.register("reasons_text")} />
      </Field>
      {improvements.fields.map((item, index) => (
        <div key={item.id} className="flex items-start gap-2">
          <Field
            label={T.decline.improvement(index + 1)}
            error={errors.improvements?.[index]?.text?.message}
            className="flex-1"
          >
            <Input maxLength={500} {...form.register(`improvements.${index}.text`)} />
          </Field>
          {improvements.fields.length > 1 ? (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="mt-6"
              aria-label={T.decline.removeImprovement(index + 1)}
              onClick={() => improvements.remove(index)}
            >
              <X aria-hidden="true" />
            </Button>
          ) : null}
        </div>
      ))}
      {listError ? (
        <p role="alert" className="m-0 text-sm text-status-danger">
          {listError}
        </p>
      ) : null}
      <div>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          onClick={() => improvements.append({ text: "" })}
        >
          {T.decline.addImprovement}
        </Button>
      </div>
    </ActionDialog>
  );
}
