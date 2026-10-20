import { useCallback, useRef } from "react";

/**
 * One Idempotency-Key per intent (docs/frontend.md, «Мастер заявки»): the same key is reused
 * when a request is retried after a network error, and a new one is taken after success.
 */
export function useIdempotencyKey() {
  const key = useRef<string>(crypto.randomUUID());
  const renew = useCallback(() => {
    key.current = crypto.randomUUID();
  }, []);
  return { current: () => key.current, renew };
}
