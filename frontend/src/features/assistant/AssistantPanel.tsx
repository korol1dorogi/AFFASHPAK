import * as DialogPrimitive from "@radix-ui/react-dialog";
import { MessageCircle, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useMatch } from "react-router";

import { routePatterns, routes } from "@/app/routes";
import { ErrorState } from "@/components/States";
import { Button } from "@/components/ui/button";
import {
  type PendingAction,
  useClientHistory,
  useConfirmAction,
  useSendClientMessage,
} from "@/features/assistant/api";
import { ChatInput, chatError, MessageList } from "@/features/assistant/Chat";
import { useAssistant } from "@/features/assistant/context";
import { errorMessage } from "@/lib/errors";
import { ASSISTANT as T } from "@/texts";

/** The application of the page the client is on, or null (the general dialogue). */
function usePageApplication(): number | null {
  const match = useMatch(routePatterns.applicationAny);
  const id = Number(match?.params.id);
  return Number.isInteger(id) && id > 0 ? id : null;
}

/**
 * The client's assistant (AI5): a panel on the right of every /app page. On an application page
 * it talks about that application. Answers are plain text; offers, payments and «what if» come
 * as cards; a proposed draft waits for «Подтвердить» — nothing changes without it.
 */
export function AssistantPanel() {
  const { open, setOpen, focusApplication, question, consume } = useAssistant();
  const pageApplication = usePageApplication();
  const applicationId = focusApplication ?? pageApplication;
  return (
    <DialogPrimitive.Root open={open} onOpenChange={setOpen}>
      <DialogPrimitive.Trigger asChild>
        <Button variant="ghost" size="sm">
          <MessageCircle aria-hidden="true" />
          {T.open}
        </Button>
      </DialogPrimitive.Trigger>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Content className="fixed top-0 right-0 bottom-0 z-50 flex w-[min(420px,100%)] flex-col gap-4 bg-surface p-5 text-ink shadow-pop">
          <div className="flex items-start justify-between gap-2">
            <div className="flex flex-col gap-1">
              <DialogPrimitive.Title className="m-0 text-lg font-semibold">
                {T.title}
              </DialogPrimitive.Title>
              <DialogPrimitive.Description className="m-0 text-xs text-ink-muted">
                {applicationId ? T.aboutApplication(applicationId) : T.subtitle}
              </DialogPrimitive.Description>
            </div>
            <DialogPrimitive.Close
              className="rounded-sm p-1 text-ink-muted hover:bg-sunken"
              aria-label={T.close}
            >
              <X className="size-4" aria-hidden="true" />
            </DialogPrimitive.Close>
          </div>
          {open ? (
            <Conversation
              applicationId={applicationId}
              question={question?.text ?? null}
              questionKey={question?.key ?? null}
              onQuestionTaken={consume}
            />
          ) : null}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

function Conversation({
  applicationId,
  question,
  questionKey,
  onQuestionTaken,
}: {
  applicationId: number | null;
  question: string | null;
  questionKey: number | null;
  onQuestionTaken: () => void;
}) {
  const history = useClientHistory(applicationId, true);
  const send = useSendClientMessage(applicationId);
  const [handled, setHandled] = useState<Record<string, "confirmed" | "cancelled">>({});
  const { mutate } = send;

  // A context button (AI6) asked: send its question once.
  useEffect(() => {
    if (question && questionKey !== null) {
      mutate(question);
      onQuestionTaken();
    }
  }, [question, questionKey, mutate, onQuestionTaken]);

  const messages = history.data ?? [];
  const pending = latestPending(messages, send.data?.pending_action ?? null);
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <div className="min-h-0 flex-1 overflow-y-auto pr-1">
        {history.isError ? (
          <ErrorState
            title={T.loadError}
            error={history.error}
            onRetry={() => void history.refetch()}
          />
        ) : (
          <MessageList
            messages={messages}
            pendingText={send.isPending ? (send.variables ?? null) : null}
            thinking={send.isPending}
            allowApply
            empty={<EmptyHint onPick={(text) => send.mutate(text)} />}
          />
        )}
        {pending && !handled[pending.id] ? (
          <PendingCard
            action={pending}
            onDone={(state) => setHandled((all) => ({ ...all, [pending.id]: state }))}
          />
        ) : null}
        {pending && handled[pending.id] === "cancelled" ? (
          <p className="m-0 mt-2 text-xs text-ink-muted">{T.cancelled}</p>
        ) : null}
      </div>
      {send.isError ? (
        <p role="alert" className="m-0 text-sm text-status-danger">
          {chatError(send.error)}
        </p>
      ) : null}
      <ChatInput
        onSend={(text) => send.mutate(text)}
        busy={send.isPending}
        placeholder={T.placeholder}
      />
    </div>
  );
}

function EmptyHint({ onPick }: { onPick: (text: string) => void }) {
  return (
    <div className="flex flex-col gap-2">
      <p className="m-0">{T.empty}</p>
      <ul className="m-0 flex list-none flex-col gap-1 p-0">
        {T.examples.map((example) => (
          <li key={example}>
            <button
              type="button"
              className="cursor-pointer rounded-md bg-sunken px-2 py-1 text-left text-sm text-ink hover:bg-primary-soft"
              onClick={() => onPick(example)}
            >
              {example}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** The proposal of the last answer: from the reply just received, or from the journal. */
function latestPending(
  messages: { role: string; tool_calls: { name: string; result: unknown }[] }[],
  fromReply: PendingAction | null,
): PendingAction | null {
  if (fromReply) return fromReply;
  const last = [...messages].reverse().find((message) => message.role === "assistant");
  const call = last?.tool_calls.find((item) => item.name === "create_draft");
  const result = call?.result as { pending_action?: PendingAction } | null | undefined;
  return result?.pending_action ?? null;
}

function PendingCard({
  action,
  onDone,
}: {
  action: PendingAction;
  onDone: (state: "confirmed" | "cancelled") => void;
}) {
  const confirm = useConfirmAction();
  if (confirm.isSuccess) {
    return (
      <div className="mt-3 flex flex-col gap-2 rounded-md border border-status-success bg-status-success-soft p-3 text-sm">
        <span className="font-semibold">{T.confirmed}</span>
        <Button asChild size="sm" className="self-start">
          <Link to={routes.applicationEdit(confirm.data.application.id, "params")}>
            {T.openDraft}
          </Link>
        </Button>
      </div>
    );
  }
  return (
    <section
      aria-label={T.pendingTitle}
      className="mt-3 flex flex-col gap-2 rounded-md border border-line-strong bg-surface p-3 text-sm"
    >
      <span className="font-semibold">{T.pendingTitle}</span>
      <p className="m-0">{action.summary}</p>
      <div className="flex gap-2">
        <Button size="sm" loading={confirm.isPending} onClick={() => confirm.mutate(action.id)}>
          {T.confirm}
        </Button>
        <Button size="sm" variant="secondary" onClick={() => onDone("cancelled")}>
          {T.cancel}
        </Button>
      </div>
      {confirm.isError ? (
        <span role="alert" className="text-status-danger">
          {errorMessage(confirm.error)}
        </span>
      ) : null}
    </section>
  );
}
