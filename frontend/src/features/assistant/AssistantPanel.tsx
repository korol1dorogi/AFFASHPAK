import * as DialogPrimitive from "@radix-ui/react-dialog";
import { MessageCircle, X } from "lucide-react";

import { Button } from "@/components/ui/button";

/**
 * Assistant side panel (task B8 replaces the body). The trigger lives in the client header so the
 * panel is reachable from every /app page (docs/frontend.md, «Ассистент»).
 */
export function AssistantPanel() {
  return (
    <DialogPrimitive.Root>
      <DialogPrimitive.Trigger asChild>
        <Button variant="ghost" size="sm">
          <MessageCircle aria-hidden="true" />
          Ассистент
        </Button>
      </DialogPrimitive.Trigger>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Content className="fixed top-0 right-0 bottom-0 z-50 flex w-[min(420px,100%)] flex-col gap-4 bg-surface p-6 text-ink shadow-pop">
          <div className="flex items-center justify-between">
            <DialogPrimitive.Title className="m-0 text-lg font-semibold">
              Ассистент
            </DialogPrimitive.Title>
            <DialogPrimitive.Close
              className="rounded-sm p-1 text-ink-muted hover:bg-sunken"
              aria-label="Закрыть"
            >
              <X className="size-4" aria-hidden="true" />
            </DialogPrimitive.Close>
          </div>
          <DialogPrimitive.Description className="m-0 text-ink-muted">
            Здесь будет ассистент: подберёт продукт, посчитает платёж и поможет заполнить заявку.
            Задача B8.
          </DialogPrimitive.Description>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
