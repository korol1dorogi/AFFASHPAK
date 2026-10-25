import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import type { Schemas } from "@/api/client";
import { Field } from "@/components/Field";
import { StatusTimeline } from "@/components/StatusTimeline";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/input";
import { useComment } from "@/features/bank-application/api";
import { type CommentValues, commentSchema } from "@/features/bank-application/schema";
import { applyFieldErrors } from "@/lib/errors";
import { ASSISTANT, BANK_CARD } from "@/texts";

const T = BANK_CARD.journal;

export interface CommentDraft {
  text: string;
  key: number;
}

function CommentForm({
  applicationId,
  draft,
}: {
  applicationId: number;
  draft: CommentDraft | null;
}) {
  const comment = useComment(applicationId);
  const [rest, setRest] = useState<string | null>(null);
  const form = useForm<CommentValues>({
    resolver: zodResolver(commentSchema),
    defaultValues: { message: "" },
  });
  const { setValue, setFocus } = form;
  // The assistant's draft (AI9) lands in the field; saving stays the officer's own action.
  useEffect(() => {
    if (!draft) return;
    setValue("message", draft.text, { shouldDirty: true });
    setFocus("message");
  }, [draft, setValue, setFocus]);

  const submit = form.handleSubmit(({ message }) => {
    setRest(null);
    comment.mutate(message, {
      onSuccess: () => {
        form.reset({ message: "" });
        toast.success(T.sent);
      },
      onError: (error) => setRest(applyFieldErrors(error, form.setError, ["message"])),
    });
  });

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-3">
      <Field
        label={T.commentLabel}
        hint={T.commentHint}
        error={form.formState.errors.message?.message}
      >
        <Textarea {...form.register("message")} maxLength={2000} />
      </Field>
      {draft ? <p className="m-0 text-sm text-ink-muted">{ASSISTANT.bank.inserted}</p> : null}
      {rest ? (
        <p role="alert" className="m-0 text-sm text-status-danger">
          {rest}
        </p>
      ) : null}
      <div>
        <Button type="submit" loading={comment.isPending}>
          {T.send}
        </Button>
      </div>
    </form>
  );
}

/** Full journal including internal events, plus an internal comment the client never sees. */
export function JournalTab({
  applicationId,
  events,
  draft = null,
}: {
  applicationId: number;
  events: Schemas["ApplicationEvent"][];
  draft?: CommentDraft | null;
}) {
  return (
    <Card>
      <CardTitle>{T.title}</CardTitle>
      <StatusTimeline events={events} showInternal />
      <CommentForm applicationId={applicationId} draft={draft} />
    </Card>
  );
}
