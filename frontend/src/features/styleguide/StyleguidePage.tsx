import { type ReactNode, useState } from "react";

import { SourceTag } from "@/components/AmountSource";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Facts } from "@/components/Facts";
import { Field } from "@/components/Field";
import { MoneyText, RateText } from "@/components/Money";
import { MoneyInput } from "@/components/MoneyInput";
import { NextStep } from "@/components/NextStep";
import { OfferCard } from "@/components/OfferCard";
import { ImprovementList, ReasonList } from "@/components/ReasonList";
import { ScoreBreakdown } from "@/components/ScoreBreakdown";
import { DemoBadge, EmptyState, ErrorState, PageHeader, Skeleton } from "@/components/States";
import { StatusBadge } from "@/components/StatusBadge";
import { StatusTimeline } from "@/components/StatusTimeline";
import { Stepper } from "@/components/Stepper";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { EVENTS, OFFER, REASONS, SCORE, STATUSES, TOKENS } from "@/features/styleguide/samples";
import { STYLEGUIDE as T } from "@/texts";

/** UX4: every component of src/components on one page, with demo data (dev only, /dev/ui). */
export function StyleguidePage() {
  const [amount, setAmount] = useState("5300000");
  const [dialog, setDialog] = useState(false);
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-10 p-6">
      <PageHeader title={T.title} subtitle={T.subtitle}>
        <DemoBadge />
      </PageHeader>

      <Section title={T.sections.colors}>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
          {TOKENS.map((token) => (
            <div key={token} className="flex flex-col gap-1">
              <div
                className="h-12 rounded-md border border-line"
                style={{ background: `var(--${token})` }}
              />
              <code className="text-xs text-ink-muted">--{token}</code>
            </div>
          ))}
        </div>
      </Section>

      <Section title={T.sections.type}>
        <p className="m-0 font-display text-[28px] leading-[34px] font-bold">{T.type.display}</p>
        <p className="m-0 font-display text-xl font-bold">{T.type.title}</p>
        <p className="m-0">{T.type.body}</p>
        <p className="m-0 text-sm text-ink-muted">{T.type.muted}</p>
      </Section>

      <Section title={T.sections.buttons}>
        <div className="flex flex-wrap items-center gap-3">
          <Button>{T.buttons.primary}</Button>
          <Button variant="secondary">{T.buttons.secondary}</Button>
          <Button variant="ghost">{T.buttons.ghost}</Button>
          <Button variant="danger">{T.buttons.danger}</Button>
          <Button variant="link">{T.buttons.link}</Button>
          <Button loading>{T.buttons.loading}</Button>
          <Button size="sm">{T.buttons.secondary}</Button>
        </div>
      </Section>

      <Section title={T.sections.badges}>
        <div className="flex flex-wrap gap-2">
          {STATUSES.map((status) => (
            <StatusBadge key={status} status={status} />
          ))}
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant="brand">{T.badges.brand}</Badge>
          <Badge>{T.badges.neutral}</Badge>
        </div>
      </Section>

      <Section title={T.sections.money}>
        <div className="flex flex-wrap items-end gap-6">
          <MoneyText value="2009314.00" size="lg" />
          <MoneyText value="189999.92" size="md" />
          <RateText value="0.2400" size="md" />
          <MoneyText value={null} size="md" />
        </div>
        <div className="flex flex-wrap gap-2">
          <SourceTag source="statement" />
          <SourceTag source="client" />
          <SourceTag source="you" />
          <SourceTag source="calc" />
          <SourceTag source="officer" />
        </div>
      </Section>

      <Section title={T.sections.inputs}>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label={T.inputLabel} hint={T.inputHint}>
            <MoneyInput value={amount} onValueChange={(value) => setAmount(value ?? "")} />
          </Field>
          <Field label={T.inputLabel} error={T.inputError}>
            <Input defaultValue="100000" />
          </Field>
          <Field label={T.inputLabel}>
            <Input disabled defaultValue="900000" />
          </Field>
        </div>
      </Section>

      <Section title={T.sections.nextStep}>
        <NextStep status="offer">{T.nextStepExtra}</NextStep>
        <NextStep status="manual_review" />
        <NextStep status="declined" />
      </Section>

      <Section title={T.sections.stepper}>
        <Stepper
          current="docs"
          steps={[
            { key: "params", label: "Параметры" },
            { key: "business", label: "О бизнесе" },
            { key: "docs", label: "Документы" },
            { key: "review", label: "Проверка и отправка" },
          ]}
        />
      </Section>

      <Section title={T.sections.timeline}>
        <StatusTimeline events={EVENTS} />
      </Section>

      <Section title={T.sections.reasons}>
        <ReasonList reasons={REASONS} />
        <ImprovementList items={[...T.improvements]} />
      </Section>

      <Section title={T.sections.offer}>
        <OfferCard offer={OFFER} actions={["accept_offer", "decline_offer"]} />
      </Section>

      <Section title={T.sections.score}>
        <ScoreBreakdown score={SCORE} />
      </Section>

      <Section title={T.sections.facts}>
        <Facts
          items={[
            { label: "ИНН", value: "000100004213" },
            { label: "Возраст бизнеса", value: "3 года" },
            { label: "Очищенный оборот", value: <MoneyText value="1250000.00" /> },
          ]}
        />
      </Section>

      <Section title={T.sections.states}>
        <div className="grid gap-4 sm:grid-cols-3">
          <EmptyState title={T.emptyTitle} text={T.emptyText} />
          <ErrorState error={new Error("demo")} title={T.errorTitle} onRetry={() => {}} />
          <div className="flex flex-col gap-2">
            <Skeleton className="h-6 w-2/3" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-5/6" />
          </div>
        </div>
      </Section>

      <Section title={T.sections.dialog}>
        <div>
          <Button variant="secondary" onClick={() => setDialog(true)}>
            {T.openDialog}
          </Button>
        </div>
        <ConfirmDialog
          open={dialog}
          onOpenChange={setDialog}
          title={T.dialogTitle}
          text={T.dialogText}
          confirmLabel={T.dialogConfirm}
          danger
          onConfirm={() => setDialog(false)}
        />
      </Section>
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Card className="flex flex-col gap-4">
      <CardTitle>{title}</CardTitle>
      {children}
    </Card>
  );
}
