import { CircleAlert, CircleCheck, Send } from "lucide-react";
import { type FormEvent, type ReactNode, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";

import { routes } from "@/app/routes";
import { MoneyText, RateText } from "@/components/Money";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { useCreateApplication } from "@/features/applications/api";
import type { AssistantMessage, AssistantToolCall } from "@/features/assistant/api";
import { ApiError, errorMessage } from "@/lib/errors";
import { cn } from "@/lib/utils";
import { NEED, ASSISTANT as T } from "@/texts";

type Json = Record<string, unknown>;

/** 429 is «wait a minute», anything else is the API's own words. */
export function chatError(error: unknown): string {
  if (error instanceof ApiError && error.status === 429) return T.throttled;
  return errorMessage(error);
}

/** The dialogue: plain text only (React escapes it), tool cards and «what the assistant did». */
export function MessageList({
  messages,
  pendingText,
  thinking,
  empty,
  allowApply = false,
}: {
  messages: AssistantMessage[];
  pendingText: string | null;
  thinking: boolean;
  empty: ReactNode;
  allowApply?: boolean;
}) {
  const end = useRef<HTMLDivElement>(null);
  const count = messages.length + (pendingText ? 1 : 0) + (thinking ? 1 : 0);
  useEffect(() => {
    if (count > 0) end.current?.scrollIntoView?.({ block: "end" });
  }, [count]);
  if (messages.length === 0 && !pendingText) {
    return <div className="text-sm text-ink-muted">{empty}</div>;
  }
  return (
    <ol aria-label={T.title} className="m-0 flex list-none flex-col gap-3 p-0">
      {messages.map((message) => (
        <li key={message.id}>
          <Bubble author={message.role}>
            <p className="m-0 whitespace-pre-line">{message.content}</p>
            {message.role === "assistant" && message.tool_calls.length > 0 ? (
              <>
                <ToolCards calls={message.tool_calls} allowApply={allowApply} />
                <ToolLog calls={message.tool_calls} />
              </>
            ) : null}
          </Bubble>
        </li>
      ))}
      {pendingText ? (
        <li>
          <Bubble author="user">
            <p className="m-0 whitespace-pre-line">{pendingText}</p>
          </Bubble>
        </li>
      ) : null}
      {thinking ? (
        <li aria-live="polite" className="text-sm text-ink-muted">
          {T.sending}
        </li>
      ) : null}
      <div ref={end} />
    </ol>
  );
}

function Bubble({ author, children }: { author: string; children: ReactNode }) {
  const mine = author === "user";
  return (
    <div className={cn("flex flex-col gap-1", mine ? "items-end" : "items-start")}>
      <span className="text-xs text-ink-muted">{mine ? T.you : T.assistant}</span>
      <div
        className={cn(
          "flex max-w-full flex-col gap-2 rounded-lg px-3 py-2 text-sm",
          mine ? "bg-primary-soft text-ink" : "bg-sunken text-ink",
        )}
      >
        {children}
      </div>
    </div>
  );
}

/** «Что сделал ассистент»: every tool call of the answer, collapsed (frontend.md, B8). */
function ToolLog({ calls }: { calls: AssistantToolCall[] }) {
  return (
    <details className="text-xs text-ink-muted">
      <summary className="cursor-pointer">{T.toolsTitle}</summary>
      <ul className="m-0 mt-1 flex list-none flex-col gap-1 p-0">
        {calls.map((call, index) => {
          const failed = Boolean((call.result as Json | null)?.error);
          const Icon = failed ? CircleAlert : CircleCheck;
          return (
            // biome-ignore lint/suspicious/noArrayIndexKey: a stored answer's calls never reorder
            <li key={`${call.name}-${index}`} className="flex items-center gap-1">
              <Icon className="size-3.5 shrink-0" aria-hidden="true" />
              <span>
                {T.tools[call.name] ?? call.name}
                {failed ? ` — ${T.toolError}` : ""}
              </span>
            </li>
          );
        })}
      </ul>
    </details>
  );
}

interface OfferResult {
  product: { code: string; name: string; is_revolving?: boolean };
  amount: string;
  term_months: number;
  rate: string;
  monthly_payment: string | null;
  fits: boolean;
}

/** Results worth a card: offers with «Оформить», a payment, a «what if». Everything else is
 * told in the answer's text and listed in «Что сделал ассистент». */
function ToolCards({ calls, allowApply }: { calls: AssistantToolCall[]; allowApply: boolean }) {
  return (
    <>
      {calls.map((call, index) => {
        const result = call.result as Json | null;
        if (!result || result.error) return null;
        const key = `${call.name}-${index}`;
        if (call.name === "recommend_products") {
          const offers = ((result.offers as OfferResult[]) ?? []).slice(0, 3);
          const need = (call.arguments as Json).need_type as keyof typeof NEED;
          return offers.length ? (
            <div key={key} className="flex flex-col gap-2">
              {offers.map((offer) => (
                <OfferCardMini
                  key={offer.product.code}
                  offer={offer}
                  need={need}
                  allowApply={allowApply}
                />
              ))}
              <p className="m-0 text-xs text-ink-muted">{T.preliminary}</p>
            </div>
          ) : null;
        }
        if (call.name === "calc_payment") {
          return (
            <dl key={key} className="m-0 grid grid-cols-2 gap-1 rounded-md bg-surface p-2">
              <dt className="text-xs text-ink-muted">{T.payment}</dt>
              <dd className="m-0 text-right font-semibold">
                <MoneyText value={result.payment as string} />
              </dd>
              <dt className="text-xs text-ink-muted">{T.totalPaid}</dt>
              <dd className="m-0 text-right">
                <MoneyText value={result.total_paid as string} />
              </dd>
              <dt className="text-xs text-ink-muted">{T.overpayment}</dt>
              <dd className="m-0 text-right">
                <MoneyText value={result.overpayment as string} />
              </dd>
            </dl>
          );
        }
        if (call.name === "what_if") {
          return (
            <dl key={key} className="m-0 grid grid-cols-2 gap-1 rounded-md bg-surface p-2">
              <dt className="text-xs text-ink-muted">{T.payment}</dt>
              <dd className="m-0 text-right font-semibold">
                <MoneyText value={result.monthly_payment as string} />
              </dd>
              <dt className="col-span-2 text-xs text-ink-muted">
                {result.fits ? T.fits : T.notFits} · {T.preliminary}
              </dt>
            </dl>
          );
        }
        return null;
      })}
    </>
  );
}

function OfferCardMini({
  offer,
  need,
  allowApply,
}: {
  offer: OfferResult;
  need: keyof typeof NEED | undefined;
  allowApply: boolean;
}) {
  const navigate = useNavigate();
  const create = useCreateApplication();
  const apply = () => {
    if (!need) return;
    create.mutate(
      {
        need_type: need,
        purpose: NEED[need].title,
        requested_amount: offer.amount,
        term_months: offer.term_months,
        product_code: offer.product.code,
        prefill_source: "assistant",
      },
      { onSuccess: (created) => navigate(routes.applicationEdit(created.id, "business")) },
    );
  };
  return (
    <div className="flex flex-col gap-1 rounded-md bg-surface p-2">
      <div className="flex items-baseline justify-between gap-2">
        <span className="font-semibold">{offer.product.name}</span>
        <MoneyText value={offer.amount} className="font-semibold" />
      </div>
      <span className="text-xs text-ink-muted">
        {offer.term_months} мес · <RateText value={offer.rate} /> ·{" "}
        {offer.monthly_payment ? (
          <>
            {T.payment.toLowerCase()} <MoneyText value={offer.monthly_payment} />
          </>
        ) : (
          T.revolving
        )}
      </span>
      {allowApply && need ? (
        <Button
          size="sm"
          variant="secondary"
          className="self-start"
          loading={create.isPending}
          onClick={apply}
        >
          {create.isPending ? T.applying : T.apply}
        </Button>
      ) : null}
      {create.isError ? (
        <span role="alert" className="text-xs text-status-danger">
          {errorMessage(create.error)}
        </span>
      ) : null}
    </div>
  );
}

/** The input: Enter sends, Shift+Enter is a new line; disabled while the answer is coming. */
export function ChatInput({
  onSend,
  busy,
  placeholder,
}: {
  onSend: (text: string) => void;
  busy: boolean;
  placeholder: string;
}) {
  const [text, setText] = useState("");
  const submit = (event?: FormEvent) => {
    event?.preventDefault();
    const value = text.trim();
    if (!value || busy) return;
    onSend(value);
    setText("");
  };
  return (
    <form onSubmit={submit} className="flex items-end gap-2">
      <Textarea
        aria-label={T.placeholder}
        placeholder={placeholder}
        value={text}
        maxLength={2000}
        rows={2}
        className="min-h-12 flex-1"
        onChange={(event) => setText(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            submit();
          }
        }}
      />
      <Button type="submit" size="icon" aria-label={T.send} loading={busy} disabled={!text.trim()}>
        <Send aria-hidden="true" />
      </Button>
    </form>
  );
}
