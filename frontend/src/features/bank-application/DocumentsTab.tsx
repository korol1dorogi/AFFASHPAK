import { Download, FileText } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import type { Schemas } from "@/api/client";
import { EmptyState } from "@/components/States";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { downloadDocument } from "@/features/bank-application/api";
import { errorMessage } from "@/lib/errors";
import { formatDate } from "@/lib/format";
import { BANK_CARD, BANK_TAB, DOCUMENT_KIND } from "@/texts";

const T = BANK_CARD.documents;

function sizeLabel(bytes: number): string {
  return bytes >= 1024 * 1024
    ? `${(bytes / 1024 / 1024).toFixed(1).replace(".", ",")} МБ`
    : `${Math.ceil(bytes / 1024)} КБ`;
}

export function DocumentsTab({
  applicationId,
  documents,
}: {
  applicationId: number;
  documents: Schemas["Document"][];
}) {
  const [pending, setPending] = useState<number | null>(null);

  if (documents.length === 0) return <EmptyState title={T.empty} text={T.emptyText} />;

  const download = async (document: Schemas["Document"]) => {
    setPending(document.id);
    try {
      await downloadDocument(applicationId, document);
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setPending(null);
    }
  };

  return (
    <Card>
      <CardTitle>{BANK_TAB.documents}</CardTitle>
      <ul aria-label={BANK_TAB.documents} className="m-0 flex list-none flex-col gap-3 p-0">
        {documents.map((document) => (
          <li key={document.id} className="flex flex-wrap items-center gap-3">
            <span className="grid size-9 place-items-center rounded-md bg-sunken text-ink-muted">
              <FileText className="size-5" aria-hidden="true" />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block font-medium">
                {DOCUMENT_KIND[document.kind]}: {document.filename}
              </span>
              <span className="block text-xs text-ink-muted">
                {sizeLabel(document.size)} · {formatDate(document.uploaded_at)}
              </span>
            </span>
            <Button
              variant="secondary"
              loading={pending === document.id}
              aria-label={T.download(document.filename)}
              onClick={() => void download(document)}
            >
              <Download aria-hidden="true" />
              {T.downloadShort}
            </Button>
          </li>
        ))}
      </ul>
    </Card>
  );
}
