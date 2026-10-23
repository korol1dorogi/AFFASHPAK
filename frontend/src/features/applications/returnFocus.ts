import { useCallback, useEffect, useRef } from "react";

/**
 * A dialog opened from state (no DialogTrigger) gives focus back to <body> when it closes.
 * remember() keeps the element that opened it; once `open` is false again, focus goes back there.
 * Lead's list (UX2): the proper fix is in ConfirmDialog / ui/dialog, then this hook goes away.
 */
export function useReturnFocus(open: boolean) {
  const opener = useRef<HTMLElement | null>(null);

  const remember = useCallback(() => {
    opener.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  }, []);

  useEffect(() => {
    if (open || !opener.current) return;
    const target = opener.current;
    opener.current = null;
    // After Radix has finished its own close-focus (it puts focus on <body>).
    const frame = requestAnimationFrame(() => {
      if (target.isConnected) target.focus();
    });
    return () => cancelAnimationFrame(frame);
  }, [open]);

  return remember;
}
