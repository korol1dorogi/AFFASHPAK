import { CircleCheck } from "lucide-react";
import { useState } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router";
import { toast } from "sonner";

import { routes } from "@/app/routes";
import { offerAmountSource, SourceTag } from "@/components/AmountSource";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Field } from "@/components/Field";
import { MoneyText, RateText } from "@/components/Money";
import { ErrorState, PageHeader, PageSkeleton } from "@/components/States";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  useApplication,
  useCancel,
  useConfirmSignature,
  useStartSignature,
} from "@/features/applications/api";
import { errorMessage } from "@/lib/errors";
import { formatDateTime } from "@/lib/format";
import { ACTION } from "@/texts";

/**
 * Signing with a code shown on screen — instead of SMS, by the case's rules (O5).
 * The code is shown once; a new request gives a new code.
 */
export function SignPage() {
  const id = Number(useParams().id);
  const navigate = useNavigate();
  const application = useApplication(id, { poll: false });
  const start = useStartSignature(id);
  const confirm = useConfirmSignature(id);
  const cancel = useCancel(id);
  const [code, setCode] = useState("");
  const [leaving, setLeaving] = useState(false);

  if (application.isPending) return <PageSkeleton />;
  if (application.isError)
    return <ErrorState error={application.error} onRetry={() => application.refetch()} />;
  const data = application.data;

  if (data.status === "signed" || data.status === "issued") {
    return (
      <Card className="items-start">
        <CircleCheck className="size-8 text-status-success" aria-hidden="true" />
        <p className="m-0 text-lg font-semibold">Договор подписан</p>
        <Button asChild>
          <Link to={routes.application(id)}>К заявке</Link>
        </Button>
      </Card>
    );
  }
  if (!data.available_actions.includes("sign"))
    return <Navigate to={routes.application(id)} replace />;

  const offer = data.offer;
  const challenge = start.data;
  const valid = /^\d{6}$/.test(code);

  return (
    <div className="flex max-w-[640px] flex-col gap-6">
      <Link to={routes.application(id)} className="link w-fit text-sm">
        ← К заявке № {id}
      </Link>
      <PageHeader
        title="Подписание договора"
        subtitle="В прототипе код не приходит по SMS, а показывается прямо на экране."
      />
      {offer ? (
        <Card className="flex-row flex-wrap gap-6">
          <span>
            <span className="block text-xs text-ink-muted">Сумма</span>
            <MoneyText value={offer.amount} size="md" className="text-brass" />
            <SourceTag source={offerAmountSource(data.decision ? [data.decision] : [])} />
          </span>
          <span>
            <span className="block text-xs text-ink-muted">Ставка</span>
            <RateText value={offer.rate} size="md" />
          </span>
          <span>
            <span className="block text-xs text-ink-muted">Срок</span>
            <span className="font-display text-xl font-bold">{offer.term_months}&nbsp;мес</span>
          </span>
        </Card>
      ) : null}

      <Card>
        {challenge ? (
          <>
            <p className="m-0 font-semibold">Ваш код</p>
            <div
              className="flex gap-2"
              role="img"
              aria-label={`Код ${challenge.code.split("").join(" ")}`}
            >
              {challenge.code.split("").map((digit, index) => (
                <span
                  // biome-ignore lint/suspicious/noArrayIndexKey: digits of a fixed code
                  key={index}
                  className="grid h-14 w-11 place-items-center rounded-sm bg-sunken font-display text-[28px] font-bold tabular"
                >
                  {digit}
                </span>
              ))}
            </div>
            <p className="m-0 text-sm text-ink-muted">
              Код действует до {formatDateTime(challenge.expires_at)} · осталось попыток:{" "}
              {challenge.attempts_left}
            </p>
            <form
              className="flex flex-wrap items-end gap-3"
              onSubmit={(event) => {
                event.preventDefault();
                confirm.mutate(code, {
                  onSuccess: () => {
                    toast.success("Договор подписан");
                    navigate(routes.application(id));
                  },
                });
              }}
            >
              <Field
                label="Введите код"
                error={confirm.isError ? errorMessage(confirm.error) : undefined}
              >
                <Input
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  maxLength={6}
                  className="w-40 tabular tracking-[0.3em]"
                  value={code}
                  onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))}
                />
              </Field>
              <Button type="submit" size="lg" disabled={!valid} loading={confirm.isPending}>
                Подписать
              </Button>
            </form>
            <Button
              variant="link"
              className="self-start px-0"
              onClick={() => start.mutate()}
              loading={start.isPending}
            >
              Получить новый код
            </Button>
          </>
        ) : (
          <>
            <p className="m-0">Нажмите, чтобы получить одноразовый код. Он действует 10 минут.</p>
            {start.isError ? (
              <p role="alert" className="m-0 text-sm text-status-danger">
                {errorMessage(start.error)}
              </p>
            ) : null}
            <Button
              size="lg"
              className="self-start"
              loading={start.isPending}
              onClick={() => start.mutate()}
            >
              Показать код
            </Button>
          </>
        )}
      </Card>

      {data.available_actions.includes("cancel") ? (
        // Up to the signature the client may still say no (fix 3.2).
        <Button variant="ghost" className="self-start" onClick={() => setLeaving(true)}>
          Отказаться и отозвать заявку
        </Button>
      ) : null}
      <ConfirmDialog
        open={leaving}
        onOpenChange={setLeaving}
        title="Отказаться от договора?"
        text="Договор не будет подписан, заявка закроется. Это нельзя отменить."
        confirmLabel={ACTION.cancel}
        cancelLabel="Вернуться к подписанию"
        danger
        pending={cancel.isPending}
        onConfirm={() =>
          cancel.mutate(undefined, {
            onSuccess: () => {
              toast.success("Заявка отозвана");
              navigate(routes.application(id));
            },
            onError: (error) => toast.error(errorMessage(error)),
            onSettled: () => setLeaving(false),
          })
        }
      />
    </div>
  );
}
