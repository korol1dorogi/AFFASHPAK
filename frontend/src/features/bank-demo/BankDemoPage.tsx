import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { api, type Schemas } from "@/api/client";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { DemoBadge, ErrorState, PageHeader, PageSkeleton } from "@/components/States";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { useDemoLogin, useDemoPersonas } from "@/features/auth/api";
import { errorMessage, unwrap } from "@/lib/errors";
import { BANK_DEMO as T } from "@/texts";

type Failures = Schemas["DemoFailures"];
type Source = Schemas["DemoSource"];
const SOURCES = ["egrul", "transparent_business", "bki", "bank_account"] as const;
const BREAKER_THRESHOLD = 3; // apps/integrations/breaker.py
const POLL_MS = 2000;

const BREAKER_TONE = { closed: "success", open: "danger", half_open: "action" } as const;

/** Whole seconds from `now` to `iso`, never below zero. */
function secondsUntil(iso: string, now: number): number {
  return Math.max(0, Math.ceil((new Date(iso).getTime() - now) / 1000));
}

/**
 * XP6: the circuit breaker of a source, live — «Breaker открыт · 3 ошибки подряд · повтор
 * через 24 с». State in words and a tone, never a colour alone.
 */
function BreakerStatus({ source, now }: { source: Source; now: number }) {
  const { state, failures, open_until: openUntil } = source.breaker;
  const B = T.breaker;
  const details =
    state === "open"
      ? [B.streak(failures), openUntil ? B.retryIn(secondsUntil(openUntil, now)) : null]
      : state === "half_open"
        ? [B.trial]
        : [failures ? B.of(failures, BREAKER_THRESHOLD) : B.calls];
  if (source.failing_until) {
    details.push(B.offIn(Math.ceil(secondsUntil(source.failing_until, now) / 60)));
  }
  return (
    <span className="flex flex-wrap items-center gap-2 text-sm" data-breaker={state}>
      <Badge variant={BREAKER_TONE[state]}>{B[state]}</Badge>
      <span className="text-ink-muted">{details.filter(Boolean).join(" · ")}</span>
    </span>
  );
}

/** The live state of the sources: polled while the panel is open, a clock for the countdowns. */
function useSources() {
  const sources = useQuery({
    queryKey: ["demo", "sources"],
    queryFn: async () => unwrap(await api.GET("/api/demo/sources")),
    refetchInterval: POLL_MS,
  });
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  return { sources: sources.data, now };
}

/** B7: scenario 7 in two clicks (switch a simulator off), reset between runs, quick sign-in. */
export function BankDemoPage() {
  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={T.title} subtitle={T.subtitle} actions={<DemoBadge />} />
      <Outages />
      <Personas />
      <Reset />
    </div>
  );
}

function Outages() {
  const queryClient = useQueryClient();
  const failures = useQuery({
    queryKey: ["demo", "failures"],
    queryFn: async () => unwrap(await api.GET("/api/demo/failures")),
  });
  // The switch moves at once (local state); after the last save the server's state wins, so a
  // late answer to an earlier click cannot undo a later one, and a failed save puts it back.
  const [local, setLocal] = useState<Failures | null>(null);
  const save = useMutation({
    mutationFn: async (body: Failures) => unwrap(await api.PUT("/api/demo/failures", { body })),
    onError: (error) => toast.error(errorMessage(error)),
    onSettled: async () => {
      await queryClient.invalidateQueries({ queryKey: ["demo", "failures"] });
      void queryClient.invalidateQueries({ queryKey: ["demo", "sources"] });
      if (queryClient.isMutating({ mutationKey: ["demo", "failures"] }) <= 1) setLocal(null);
    },
    mutationKey: ["demo", "failures"],
  });
  const { sources, now } = useSources();
  if (failures.isPending) return <PageSkeleton />;
  if (failures.isError)
    return (
      <ErrorState
        title={T.loadError}
        error={failures.error}
        onRetry={() => void failures.refetch()}
      />
    );
  const flags = local ?? failures.data;
  return (
    <Card>
      <CardTitle className="m-0">{T.outagesTitle}</CardTitle>
      <p className="m-0 text-sm text-ink-muted">{T.outagesHint}</p>
      <p className="m-0 text-sm">{T.twoClicks}</p>
      <ul aria-label={T.outagesTitle} className="m-0 flex list-none flex-col gap-2 p-0">
        {SOURCES.map((source) => {
          const live = sources?.find((item) => item.source === source);
          return (
            <li
              key={source}
              data-source={source}
              className="flex flex-wrap items-center gap-3 rounded-md border border-line p-3"
            >
              <label className="flex flex-1 cursor-pointer items-center gap-3">
                <input
                  type="checkbox"
                  role="switch"
                  aria-checked={flags[source]}
                  checked={flags[source]}
                  onChange={(event) => {
                    const next = { ...flags, [source]: event.target.checked };
                    setLocal(next);
                    save.mutate(next);
                  }}
                  className="size-4"
                />
                <span className="flex-1">{T.sources[source]}</span>
              </label>
              <span
                className={flags[source] ? "font-semibold text-status-danger" : "text-ink-muted"}
              >
                {flags[source] ? T.down : T.up}
              </span>
              {live ? (
                <span className="basis-full pl-7">
                  <BreakerStatus source={live} now={now} />
                </span>
              ) : null}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

function Personas() {
  const personas = useDemoPersonas();
  const login = useDemoLogin();
  if (!personas.data) return null;
  return (
    <Card>
      <CardTitle className="m-0">{T.personasTitle}</CardTitle>
      <p className="m-0 text-sm text-ink-muted">{T.personasHint}</p>
      <ul aria-label={T.personasTitle} className="m-0 flex list-none flex-col gap-2 p-0">
        {personas.data.map((persona) => (
          <li
            key={persona.code}
            className="flex items-center gap-3 rounded-md border border-line p-3"
          >
            <span className="min-w-0 flex-1">
              <span className="block font-medium">{persona.title}</span>
              <span className="text-sm text-ink-muted">
                {persona.kind === "bank" ? T.bankPlace : T.scenario(persona.scenario)}
              </span>
            </span>
            <Button
              size="sm"
              variant="secondary"
              loading={login.isPending && login.variables === persona.code}
              onClick={() => login.mutate(persona.code)}
            >
              {T.signInAs}
            </Button>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function Reset() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const reset = useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/demo/reset")),
    onSuccess: () => {
      toast.success(T.resetDone);
      setOpen(false);
      void queryClient.invalidateQueries();
    },
    onError: (error) => toast.error(errorMessage(error)),
  });
  return (
    <Card>
      <CardTitle className="m-0">{T.resetTitle}</CardTitle>
      <p className="m-0 text-sm text-ink-muted">{T.resetHint}</p>
      <Button variant="danger" className="self-start" onClick={() => setOpen(true)}>
        {T.reset}
      </Button>
      <ConfirmDialog
        open={open}
        onOpenChange={setOpen}
        title={T.resetConfirmTitle}
        text={T.resetConfirmText}
        confirmLabel={T.reset}
        danger
        pending={reset.isPending}
        onConfirm={() => reset.mutate()}
      />
    </Card>
  );
}
