import { Printer, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { createPortal, flushSync } from "react-dom";

import { Button } from "@/components/ui/button";
import type { BankApplicationDetail } from "@/features/bank-application/api";
import { CreditConclusion } from "@/features/bank-application/CreditConclusion";
import { cn } from "@/lib/utils";
import { BANK_CARD } from "@/texts";

const T = BANK_CARD.conclusion;

/**
 * The conclusion is a direct child of <body> (a portal), so in print everything else — the app
 * with its menu, header, tabs and action panel, dialogs, toasts — is hidden by one rule, without
 * touching the layout. A4 margins come from @page.
 */
export const PRINT_CSS = `
@media print {
  @page { size: A4; margin: 12mm 12mm 14mm; }
  html, body { background: #fff !important; }
  body > :not([data-credit-conclusion]) { display: none !important; }
  [data-credit-conclusion] { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
}
`;

/** A modal keeps Tab inside: past the last control back to the first, and the other way round. */
function keepFocusInside(event: KeyboardEvent, root: HTMLElement | null) {
  if (!root) return;
  const items = [
    ...root.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])',
    ),
  ];
  const first = items[0];
  const last = items.at(-1);
  if (!first || !last) return;
  const active = document.activeElement;
  if (!root.contains(active)) {
    event.preventDefault();
    first.focus();
  } else if (event.shiftKey && active === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && active === last) {
    event.preventDefault();
    first.focus();
  }
}

/**
 * XP3: full-screen preview of the credit conclusion with «Сохранить в PDF» (the browser's print,
 * «Сохранить как PDF»). Ctrl+P on the card prints the conclusion too: it is mounted for printing.
 */
export function ConclusionPrint({
  card,
  product,
  open,
  onClose,
}: {
  card: BankApplicationDetail;
  product: string;
  open: boolean;
  onClose: () => void;
}) {
  const [generatedAt, setGeneratedAt] = useState(() => new Date());
  const [printing, setPrinting] = useState(false);
  const printButton = useRef<HTMLButtonElement>(null);
  const dialog = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // The print snapshot is taken right after beforeprint: render synchronously.
    const before = () =>
      flushSync(() => {
        setGeneratedAt(new Date());
        setPrinting(true);
      });
    const after = () => setPrinting(false);
    window.addEventListener("beforeprint", before);
    window.addEventListener("afterprint", after);
    return () => {
      window.removeEventListener("beforeprint", before);
      window.removeEventListener("afterprint", after);
    };
  }, []);

  useEffect(() => {
    if (!open) return;
    // The button that opened the preview gets focus back when it closes.
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setGeneratedAt(new Date());
    printButton.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
      if (event.key === "Tab") keepFocusInside(event, dialog.current);
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      if (opener?.isConnected) opener.focus();
    };
  }, [open, onClose]);

  if (!open && !printing) return null;
  const sheet = (
    <div
      className={cn(
        open && "mx-auto my-6 max-w-[210mm] bg-surface p-[12mm] shadow-md",
        "print:m-0 print:max-w-none print:p-0 print:shadow-none",
      )}
    >
      <CreditConclusion card={card} product={product} generatedAt={generatedAt} />
    </div>
  );
  const print = "print:static print:block print:overflow-visible print:bg-white";
  return createPortal(
    open ? (
      <div
        ref={dialog}
        data-credit-conclusion
        role="dialog"
        aria-modal="true"
        aria-label={T.previewLabel}
        className={cn("fixed inset-0 z-50 overflow-auto bg-sunken", print)}
      >
        <style>{PRINT_CSS}</style>
        <div className="sticky top-0 z-10 flex flex-wrap items-center gap-3 border-b border-line bg-surface px-4 py-3 print:hidden">
          <Button ref={printButton} onClick={() => window.print()}>
            <Printer aria-hidden="true" />
            {T.print}
          </Button>
          <Button variant="secondary" onClick={onClose}>
            <X aria-hidden="true" />
            {T.close}
          </Button>
          <span className="text-sm text-ink-muted">{T.previewHint}</span>
        </div>
        {sheet}
      </div>
    ) : (
      <div data-credit-conclusion className={cn("hidden", print)}>
        <style>{PRINT_CSS}</style>
        {sheet}
      </div>
    ),
    document.body,
  );
}
