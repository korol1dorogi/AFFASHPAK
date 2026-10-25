import { MessageCircle } from "lucide-react";

import { useAssistant } from "@/features/assistant/context";

/**
 * AI6: a ready question to the assistant about this application, right where it arises.
 * It acts on this page (opens the assistant), so it looks like a dashed «псевдоссылка».
 */
export function AskAssistant({
  question,
  applicationId,
}: {
  question: string;
  applicationId: number;
}) {
  const { ask } = useAssistant();
  return (
    <button
      type="button"
      className="link-action inline-flex items-center gap-1.5 self-start text-left text-sm"
      onClick={() => ask(question, applicationId)}
    >
      <MessageCircle className="size-4 shrink-0" aria-hidden="true" />
      {question}
    </button>
  );
}
