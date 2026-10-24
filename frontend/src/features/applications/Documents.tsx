import { CircleCheck, FileText, Upload } from "lucide-react";
import { useId, useRef, useState } from "react";
import { toast } from "sonner";

import type { Schemas } from "@/api/client";
import { Button } from "@/components/ui/button";
import { NativeSelect } from "@/components/ui/input";
import { useDocuments, useUploadDocument } from "@/features/applications/api";
import { errorMessage } from "@/lib/errors";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import { DOCUMENT_KIND } from "@/texts";

type Kind = Schemas["DocumentKind"];
const MAX_BYTES = 10 * 1024 * 1024;
const ACCEPT = "application/pdf,image/png,image/jpeg";

function sizeLabel(bytes: number): string {
  return bytes >= 1024 * 1024
    ? `${(bytes / 1024 / 1024).toFixed(1).replace(".", ",")} МБ`
    : `${Math.ceil(bytes / 1024)} КБ`;
}

/** Upload one document: type, file, button. PDF, JPG, PNG up to 10 MB; the server checks again. */
export function DocumentUpload({
  applicationId,
  kinds,
  defaultKind,
}: {
  applicationId: number;
  kinds: Kind[];
  defaultKind?: Kind;
}) {
  const upload = useUploadDocument(applicationId);
  const fileRef = useRef<HTMLInputElement>(null);
  const [kind, setKind] = useState<Kind>(defaultKind ?? kinds[0] ?? "other");
  const [error, setError] = useState<string | null>(null);
  const id = useId();

  const send = (file: File | undefined) => {
    setError(null);
    if (!file) return;
    if (file.size > MAX_BYTES) {
      setError("Файл больше 10 МБ. Сожмите его или загрузите по частям.");
      return;
    }
    upload.mutate(
      { kind, file },
      {
        onSuccess: (document) => toast.success(`Загружено: ${document.filename}`),
        onError: (failure) => setError(errorMessage(failure)),
        onSettled: () => {
          if (fileRef.current) fileRef.current.value = "";
        },
      },
    );
  };

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex min-w-56 flex-col gap-1">
          <label htmlFor={`${id}-kind`} className="text-sm font-medium">
            Тип документа
          </label>
          <NativeSelect
            id={`${id}-kind`}
            value={kind}
            onChange={(event) => setKind(event.target.value as Kind)}
          >
            {kinds.map((value) => (
              <option key={value} value={value}>
                {DOCUMENT_KIND[value]}
              </option>
            ))}
          </NativeSelect>
        </div>
        <input
          ref={fileRef}
          id={`${id}-file`}
          type="file"
          accept={ACCEPT}
          className="sr-only"
          onChange={(event) => send(event.target.files?.[0])}
        />
        <Button
          variant="secondary"
          loading={upload.isPending}
          onClick={() => fileRef.current?.click()}
        >
          <Upload aria-hidden="true" />
          Выбрать файл
        </Button>
      </div>
      <p
        className={cn("m-0 text-sm", error ? "text-status-danger" : "text-ink-muted")}
        role={error ? "alert" : undefined}
      >
        {error ?? "PDF, JPG или PNG, до 10 МБ."}
      </p>
    </div>
  );
}

/** Uploaded documents of the application. */
export function DocumentList({ applicationId }: { applicationId: number }) {
  const documents = useDocuments(applicationId);
  if (!documents.data?.length) {
    return <p className="m-0 text-sm text-ink-muted">Документов пока нет.</p>;
  }
  return (
    <ul className="m-0 flex list-none flex-col gap-3 p-0">
      {documents.data.map((document) => (
        <li key={document.id} className="flex items-center gap-3">
          <span className="grid size-9 place-items-center rounded-md bg-sunken text-ink-muted">
            <FileText className="size-5" aria-hidden="true" />
          </span>
          <span className="min-w-0 flex-1">
            <a href={document.download_url} className="font-medium">
              {DOCUMENT_KIND[document.kind]}: {document.filename}
            </a>
            <span className="block text-xs text-ink-muted">
              {sizeLabel(document.size)} · {formatDate(document.uploaded_at)}
            </span>
          </span>
        </li>
      ))}
    </ul>
  );
}

/** Required documents of the product: uploaded ✓ / still needed. */
export function RequiredDocuments({
  applicationId,
  required,
}: {
  applicationId: number;
  required: Kind[];
}) {
  const documents = useDocuments(applicationId);
  const uploaded = new Set(documents.data?.map((document) => document.kind));
  if (required.length === 0) {
    return (
      <p className="m-0 text-ink-muted">
        Для этого продукта документы не обязательны: банк возьмёт данные из выписки.
      </p>
    );
  }
  return (
    <ul aria-label="Нужные документы" className="m-0 flex list-none flex-col gap-2 p-0">
      {required.map((kind) => {
        const done = uploaded.has(kind);
        return (
          <li
            key={kind}
            className="flex items-center gap-3 rounded-md border border-line bg-surface p-3"
          >
            {done ? (
              <CircleCheck
                className="size-5 text-status-success"
                role="img"
                aria-label="загружен"
              />
            ) : (
              <FileText className="size-5 text-ink-muted" role="img" aria-label="нужно загрузить" />
            )}
            <span className="flex-1">{DOCUMENT_KIND[kind]}</span>
            <span className={cn("text-sm", done ? "text-status-success" : "text-ink-muted")}>
              {done ? "Загружен" : "Нужно загрузить"}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
