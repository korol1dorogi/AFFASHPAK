import {
  ArrowRight,
  Bot,
  Calculator,
  ChartColumn,
  ExternalLink,
  FileSearch,
  ListChecks,
  MessageCircleQuestion,
  PenLine,
  PhoneOff,
  ScanSearch,
  UserCheck,
} from "lucide-react";
import { useId } from "react";
import { Link } from "react-router";

import type { Schemas } from "@/api/client";
import { routes } from "@/app/routes";
import { MoneyText } from "@/components/Money";
import { ReasonList } from "@/components/ReasonList";
import { DemoBadge } from "@/components/States";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useDemoLogin, useDemoPersonas } from "@/features/auth/api";
import { errorMessage } from "@/lib/errors";
import { PERSONA_STORY, LANDING as T } from "@/texts";

const PERSONAS_ID = "demo-personas";
const CLIENT_ICONS = [MessageCircleQuestion, Calculator, PenLine] as const;
const BANK_ICONS = [ListChecks, ScanSearch, UserCheck, ChartColumn] as const;
const WHY_ICONS = [FileSearch, Bot, PhoneOff] as const;

/** Coffee shop (scenario 1): the reasons /app/match really returns for it (POST /api/recommendations),
 * drawn with the same components as the cabinet. */
const EXAMPLE_REASONS: Schemas["Reason"][] = [
  {
    metric: "overdraft_limit",
    value: "900000.00",
    threshold: null,
    passed: true,
    message: "Лимит — 30% от средних поступлений на счёт за месяц: 900 000 ₽",
  },
  {
    metric: "score_total",
    value: "92",
    threshold: "75",
    passed: true,
    message:
      "92 балла из 100, это предварительная оценка A: кредитную историю и данные ФНС ещё не проверяли",
  },
  {
    metric: "product_requirements",
    value: null,
    threshold: null,
    passed: true,
    message: "Правовая форма и возраст бизнеса подходят",
  },
];

function Hero() {
  return (
    <section className="grid grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)] items-center gap-10 py-8">
      <div className="flex flex-col gap-5">
        <p className="m-0 text-sm font-semibold tracking-wide text-primary-ink uppercase">
          {T.eyebrow}
        </p>
        <h1 className="m-0 font-display text-[44px] leading-[48px] font-extrabold tracking-[-0.02em]">
          {T.title}
        </h1>
        <p className="m-0 max-w-[58ch] text-lg leading-7 text-ink-muted">{T.lead}</p>
        <div className="flex flex-wrap gap-3">
          <Button asChild size="lg">
            <a href={`#${PERSONAS_ID}`}>
              {T.tryPersona}
              <ArrowRight className="size-4" aria-hidden="true" />
            </a>
          </Button>
          <Button asChild size="lg" variant="secondary">
            <Link to={routes.login}>{T.signIn}</Link>
          </Button>
        </div>
        <p className="m-0 text-sm text-ink-muted">
          {T.ownCompany}{" "}
          <Link to={routes.register} className="link font-medium">
            {T.register}
          </Link>
        </p>
      </div>
      <Card className="gap-4 shadow-lg" aria-label={T.example.title}>
        <div className="flex items-center justify-between gap-2">
          <p className="m-0 font-semibold">{T.example.title}</p>
          <DemoBadge />
        </div>
        <div className="flex flex-col gap-1 rounded-md bg-brass-soft p-4">
          <span className="text-sm text-ink-muted">{T.example.product}</span>
          <MoneyText value={T.example.amount} size="lg" className="text-brass" />
          <span className="text-sm text-ink-muted">{T.example.caption}</span>
        </div>
        <ReasonList reasons={EXAMPLE_REASONS} label={T.example.caption} />
        <p className="m-0 text-xs text-ink-muted">{T.example.note}</p>
      </Card>
    </section>
  );
}

function Steps({
  title,
  steps,
  icons,
  numbered,
}: {
  title: string;
  steps: readonly { title: string; text: string }[];
  icons: readonly (typeof ArrowRight)[];
  numbered?: boolean;
}) {
  const titleId = useId();
  return (
    <section aria-labelledby={titleId} className="flex flex-col gap-4">
      <h2 id={titleId} className="m-0 font-display text-2xl font-bold">
        {title}
      </h2>
      <ol
        className="m-0 grid list-none gap-4 p-0"
        style={{ gridTemplateColumns: `repeat(${steps.length}, minmax(0, 1fr))` }}
      >
        {steps.map((step, index) => {
          const Icon = icons[index] ?? ArrowRight;
          return (
            <li key={step.title}>
              <Card className="h-full gap-3">
                <div className="flex items-center gap-3">
                  <span className="grid size-10 place-items-center rounded-full bg-primary-soft text-primary-ink">
                    <Icon className="size-5" aria-hidden="true" />
                  </span>
                  {numbered ? (
                    <span className="font-display text-sm font-bold text-ink-muted">
                      {index + 1} / {steps.length}
                    </span>
                  ) : null}
                </div>
                <h3 className="m-0 text-lg font-semibold">{step.title}</h3>
                <p className="m-0 text-sm leading-6 text-ink-muted">{step.text}</p>
              </Card>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

function Why() {
  const titleId = useId();
  return (
    <section aria-labelledby={titleId} className="flex flex-col gap-4">
      <h2 id={titleId} className="m-0 font-display text-2xl font-bold">
        {T.whyTitle}
      </h2>
      <figure className="m-0 flex flex-col gap-2 border-l-4 border-primary bg-surface py-3 pr-4 pl-5">
        <blockquote className="m-0 text-lg leading-7">{T.quote}</blockquote>
        <figcaption className="text-sm text-ink-muted">— {T.quoteSource}</figcaption>
      </figure>
      <ul className="m-0 grid list-none grid-cols-3 gap-4 p-0">
        {T.why.map((item, index) => {
          const Icon = WHY_ICONS[index] ?? FileSearch;
          return (
            <li key={item.title} className="flex gap-3">
              <Icon className="mt-1 size-5 shrink-0 text-primary" aria-hidden="true" />
              <div className="flex flex-col gap-1">
                <h3 className="m-0 text-base font-semibold">{item.title}</h3>
                <p className="m-0 text-sm leading-6 text-ink-muted">{item.text}</p>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function Personas() {
  const personas = useDemoPersonas();
  const demoLogin = useDemoLogin();
  return (
    <section
      id={PERSONAS_ID}
      aria-labelledby={`${PERSONAS_ID}-title`}
      className="flex scroll-mt-20 flex-col gap-4"
    >
      <div className="flex items-center gap-2">
        <h2 id={`${PERSONAS_ID}-title`} className="m-0 font-display text-2xl font-bold">
          {T.personasTitle}
        </h2>
        <DemoBadge />
      </div>
      {personas.data === null ? (
        <p className="m-0 text-ink-muted">{T.personasOff}</p>
      ) : (
        <>
          <p className="m-0 text-ink-muted">{T.personasLead}</p>
          <ul aria-label={T.personasTitle} className="m-0 grid list-none grid-cols-2 gap-3 p-0">
            {(personas.data ?? []).map((persona) => (
              <li
                key={persona.code}
                className="flex items-center gap-3 rounded-md border border-line bg-surface p-3"
              >
                <span className="min-w-0 flex-1">
                  <span className="block text-xs font-semibold text-primary-ink">
                    {persona.kind === "bank" ? T.personaBank : T.personaClient(persona.scenario)}
                  </span>
                  <span className="block font-medium">{persona.title}</span>
                  {PERSONA_STORY[persona.code] ? (
                    <span className="block text-sm text-ink-muted">
                      {PERSONA_STORY[persona.code]}
                    </span>
                  ) : null}
                </span>
                <Button
                  variant="secondary"
                  size="sm"
                  aria-label={`${T.personaSignIn}: ${persona.title}`}
                  loading={demoLogin.isPending && demoLogin.variables === persona.code}
                  onClick={() => demoLogin.mutate(persona.code)}
                >
                  {T.personaSignIn}
                </Button>
              </li>
            ))}
          </ul>
          {demoLogin.isError ? (
            <p role="alert" className="m-0 text-sm text-status-danger">
              {errorMessage(demoLogin.error)}
            </p>
          ) : null}
        </>
      )}
    </section>
  );
}

/** UX1: what it is, the client's and the bank's path, why it is different, demo sign-in. */
export function LandingPage() {
  return (
    <div className="flex flex-col gap-12 pb-8">
      <Hero />
      <Steps title={T.clientTitle} steps={T.clientSteps} icons={CLIENT_ICONS} numbered />
      <Steps title={T.bankTitle} steps={T.bankSteps} icons={BANK_ICONS} />
      <Why />
      <Personas />
      <footer className="flex flex-wrap items-center gap-x-6 gap-y-2 border-t border-line pt-4 text-sm text-ink-muted">
        {/* /api/docs is served by Caddy, not by the SPA router: a plain link. */}
        <a href="/api/docs/" className="link inline-flex items-center gap-1">
          {T.links.swagger}
          <ExternalLink className="size-3.5" aria-hidden="true" />
        </a>
        <Link to={routes.status} className="link">
          {T.links.status}
        </Link>
        <span>{T.disclaimer}</span>
      </footer>
    </div>
  );
}
