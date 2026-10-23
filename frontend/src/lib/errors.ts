import type { FieldValues, Path, UseFormSetError } from "react-hook-form";

import type { Schemas } from "@/api/client";

type ErrorBody = Schemas["Error"];

/** A non-2xx API answer in the single error format (docs/openapi.yaml, Error). */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown> | undefined;

  constructor(status: number, body: ErrorBody | undefined) {
    super(body?.error.message ?? "Что-то пошло не так. Попробуйте ещё раз.");
    this.name = "ApiError";
    this.status = status;
    this.code = body?.error.code ?? "unknown";
    this.details = body?.error.details;
  }
}

/** openapi-fetch result → data, or throw ApiError (use inside queryFn / mutationFn). */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.response.ok && result.data !== undefined) return result.data;
  if (result.response.ok && result.response.status === 204) return undefined as T;
  throw new ApiError(result.response.status, result.error as ErrorBody | undefined);
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof TypeError) return "Нет связи с сервером. Проверьте интернет и повторите.";
  return "Что-то пошло не так. Попробуйте ещё раз.";
}

/** All messages of a 400 `details` (field → messages), for screens without matching fields. */
export function fieldMessages(error: unknown): string[] {
  if (!(error instanceof ApiError) || !error.details) return [];
  return Object.values(error.details).flatMap((value) =>
    Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [],
  );
}

export const isConflict = (error: unknown) => error instanceof ApiError && error.status === 409;

/** Put API field errors (`details`) onto form fields; returns what did not match a field. */
export function applyFieldErrors<T extends FieldValues>(
  error: unknown,
  setError: UseFormSetError<T>,
  fields: readonly Path<T>[],
): string | null {
  if (!(error instanceof ApiError) || !error.details) return errorMessage(error);
  const rest: string[] = [];
  for (const [key, value] of Object.entries(error.details)) {
    const text = Array.isArray(value) ? value.join(" ") : String(value);
    if ((fields as readonly string[]).includes(key)) {
      setError(key as Path<T>, { type: "server", message: text });
    } else {
      rest.push(text);
    }
  }
  return rest.length ? rest.join(" ") : null;
}
