import { useId } from "react";

import { ErrorState } from "@/components/States";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import {
  type AssistantSummary,
  useBankHistory,
  useBankSummary,
  useSendBankMessage,
} from "@/features/assistant/api";
import { ChatInput, chatError, MessageList } from "@/features/assistant/Chat";
import { ASSISTANT } from "@/texts";

const T = ASSISTANT.bank;
const SUMMARY_PREFIX = "[СВОДКА]"; // interface И2а, backend apps/assistant/summary.py

/**
 * AI9: the officer's assistant inside the card. «Сводка для решения» — risks, what to verify and a
 * comment draft, each line from the tools' facts; «Вставить в комментарий» puts the draft into the
 * journal's comment field — the officer edits and saves it. The assistant changes nothing itself.
 */
export function AssistantTab({
  applicationId,
  onInsertComment,
}: {
  applicationId: number;
  onInsertComment: (text: string) => void;
}) {
  const summary = useBankSummary(applicationId);
  return (
    <div className="flex flex-col gap-6">
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-col gap-1">
            <CardTitle>{T.title}</CardTitle>
            <CardDescription>{T.subtitle}</CardDescription>
          </div>
          <Button loading={summary.isPending} onClick={() => summary.mutate()}>
            {summary.isPending ? T.summaryLoading : T.summary}
          </Button>
        </div>
        {summary.isError ? (
          <p role="alert" className="m-0 text-sm text-status-danger">
            {T.error}: {chatError(summary.error)}
          </p>
        ) : null}
        {summary.data ? (
          <SummaryView summary={summary.data} onInsertComment={onInsertComment} />
        ) : null}
      </Card>
      <Dialogue applicationId={applicationId} />
    </div>
  );
}

function SummaryView({
  summary,
  onInsertComment,
}: {
  summary: AssistantSummary;
  onInsertComment: (text: string) => void;
}) {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Block title={T.risks} items={summary.risks} empty={T.noRisks} />
      <Block title={T.toVerify} items={summary.to_verify} empty={T.nothingToVerify} />
      <section className="flex flex-col gap-2 md:col-span-2" aria-label={T.draft}>
        <h3 className="m-0 text-base font-semibold">{T.draft}</h3>
        <p className="m-0 rounded-md bg-sunken p-3 whitespace-pre-line">{summary.draft_comment}</p>
        <Button
          variant="secondary"
          size="sm"
          className="self-start"
          onClick={() => onInsertComment(summary.draft_comment)}
        >
          {T.insert}
        </Button>
      </section>
      {summary.sources.length ? (
        <p className="m-0 text-xs text-ink-muted md:col-span-2">
          {T.sources}: {summary.sources.join(" · ")}
        </p>
      ) : null}
    </div>
  );
}

function Block({ title, items, empty }: { title: string; items: string[]; empty: string }) {
  const id = useId();
  return (
    <section aria-labelledby={id} className="flex flex-col gap-2">
      <h3 id={id} className="m-0 text-base font-semibold">
        {title}
      </h3>
      {items.length ? (
        <ul className="m-0 flex flex-col gap-1 pl-5">
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className="m-0 text-sm text-ink-muted">{empty}</p>
      )}
    </section>
  );
}

function Dialogue({ applicationId }: { applicationId: number }) {
  const history = useBankHistory(applicationId);
  const send = useSendBankMessage(applicationId);
  return (
    <Card>
      <CardTitle>{ASSISTANT.title}</CardTitle>
      {history.isError ? (
        <ErrorState
          title={ASSISTANT.loadError}
          error={history.error}
          onRetry={() => void history.refetch()}
        />
      ) : (
        <MessageList
          // The decision summaries are shown above, not as «[СВОДКА]» → JSON in the dialogue.
          messages={(history.data ?? []).filter(
            (m) => !m.content.startsWith(SUMMARY_PREFIX) && !m.content.startsWith("{"),
          )}
          pendingText={send.isPending ? (send.variables ?? null) : null}
          thinking={send.isPending}
          empty={T.empty}
        />
      )}
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
    </Card>
  );
}
