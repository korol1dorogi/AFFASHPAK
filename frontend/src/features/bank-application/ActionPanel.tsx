import { useState } from "react";
import { toast } from "sonner";

import type { Schemas } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import {
  ApproveDialog,
  CounterofferDialog,
  DeclineDialog,
  RequestInfoDialog,
} from "@/features/bank-application/ActionDialogs";
import { type BankApplicationDetail, useAssign } from "@/features/bank-application/api";
import { BANK_ACTIONS } from "@/features/bank-application/texts";
import { errorMessage } from "@/lib/errors";
import { ACTION, BANK_CARD } from "@/texts";

type Opened = "approve" | "counteroffer" | "product" | "request_info" | "decline";

/** Dialog buttons; «Другой продукт» is a counteroffer with product_code (docs/openapi.yaml). */
const BUTTONS: {
  opens: Opened;
  action: Schemas["ApplicationAction"];
  label: string;
  variant: "default" | "secondary" | "danger";
}[] = [
  { opens: "approve", action: "approve", label: ACTION.approve, variant: "default" },
  {
    opens: "counteroffer",
    action: "counteroffer",
    label: ACTION.counteroffer,
    variant: "secondary",
  },
  {
    opens: "product",
    action: "counteroffer",
    label: BANK_ACTIONS.productChange,
    variant: "secondary",
  },
  {
    opens: "request_info",
    action: "request_info",
    label: ACTION.request_info,
    variant: "secondary",
  },
  { opens: "decline", action: "decline", label: ACTION.decline, variant: "danger" },
];

/**
 * Employee actions — only those in available_actions. Each one but «Взять в работу» asks in a
 * dialog. An open dialog stays while the card is re-read after a 409, even if its action is gone.
 */
export function ActionPanel({ card }: { card: BankApplicationDetail }) {
  const { application } = card;
  const can = (action: Schemas["ApplicationAction"]) =>
    application.available_actions.includes(action);
  const [opened, setOpened] = useState<Opened | null>(null);
  const assign = useAssign(application.id);
  const close = () => setOpened(null);
  const buttons = BUTTONS.filter((button) => can(button.action));

  return (
    <aside aria-label={BANK_CARD.actionsLabel}>
      <Card className="gap-3">
        <CardTitle>{BANK_CARD.actionsLabel}</CardTitle>
        {buttons.length === 0 && !can("assign") ? (
          <p className="m-0 text-sm text-ink-muted">{BANK_ACTIONS.none}</p>
        ) : (
          <div className="flex flex-wrap gap-3">
            {can("assign") ? (
              <Button
                variant="secondary"
                loading={assign.isPending}
                onClick={() =>
                  assign.mutate(
                    { version: application.version },
                    {
                      onSuccess: () => toast.success(BANK_ACTIONS.assigned),
                      onError: (error) => toast.error(errorMessage(error)),
                    },
                  )
                }
              >
                {ACTION.assign}
              </Button>
            ) : null}
            {buttons.map((button) => (
              <Button
                key={button.opens}
                variant={button.variant}
                onClick={() => setOpened(button.opens)}
              >
                {button.label}
              </Button>
            ))}
          </div>
        )}
      </Card>
      {opened === "approve" ? <ApproveDialog card={card} onClose={close} /> : null}
      {opened === "counteroffer" || opened === "product" ? (
        <CounterofferDialog card={card} onClose={close} changeProduct={opened === "product"} />
      ) : null}
      {opened === "request_info" ? <RequestInfoDialog card={card} onClose={close} /> : null}
      {opened === "decline" ? <DeclineDialog card={card} onClose={close} /> : null}
    </aside>
  );
}
