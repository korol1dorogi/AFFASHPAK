import { MessageCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useAssistant } from "@/features/assistant/context";

/** AI6: a ready question to the assistant about this application, right where it arises. */
export function AskAssistant({
  question,
  applicationId,
}: {
  question: string;
  applicationId: number;
}) {
  const { ask } = useAssistant();
  return (
    <Button
      variant="ghost"
      size="sm"
      className="self-start"
      onClick={() => ask(question, applicationId)}
    >
      <MessageCircle aria-hidden="true" />
      {question}
    </Button>
  );
}
