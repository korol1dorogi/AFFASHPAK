import { createContext, type ReactNode, useCallback, useContext, useMemo, useState } from "react";

/** A question a context button (AI6) hands to the panel. */
export interface AssistantQuestion {
  text: string;
  /** Changes on every ask, so the same question asked twice is sent twice. */
  key: number;
}

interface AssistantState {
  open: boolean;
  setOpen: (open: boolean) => void;
  /** The application a context button chose; kept while the panel stays open. */
  focusApplication: number | null;
  question: AssistantQuestion | null;
  /** Open the panel about this application and send this question. */
  ask: (text: string, applicationId: number | null) => void;
  /** The panel sent the question: it is not sent again on the next render. */
  consume: () => void;
}

const AssistantContext = createContext<AssistantState | null>(null);

export function AssistantProvider({ children }: { children: ReactNode }) {
  const [open, setOpenState] = useState(false);
  const [focusApplication, setFocus] = useState<number | null>(null);
  const [question, setQuestion] = useState<AssistantQuestion | null>(null);
  const setOpen = useCallback((value: boolean) => {
    setOpenState(value);
    if (!value) setFocus(null); // closed: next time the panel follows the page again
  }, []);
  const ask = useCallback((text: string, applicationId: number | null) => {
    setFocus(applicationId);
    setQuestion({ text, key: Date.now() });
    setOpenState(true);
  }, []);
  const consume = useCallback(() => setQuestion(null), []);
  const value = useMemo(
    () => ({ open, setOpen, focusApplication, question, ask, consume }),
    [open, setOpen, focusApplication, question, ask, consume],
  );
  return <AssistantContext.Provider value={value}>{children}</AssistantContext.Provider>;
}

/** The panel's state; outside a provider (bank pages, tests) the buttons simply do nothing. */
export function useAssistant(): AssistantState {
  return (
    useContext(AssistantContext) ?? {
      open: false,
      setOpen: () => {},
      focusApplication: null,
      question: null,
      ask: () => {},
      consume: () => {},
    }
  );
}
