import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useId, useState } from "react";

import { api, type Schemas } from "@/api/client";
import { ErrorState, PageHeader, PageSkeleton } from "@/components/States";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { errorMessage, unwrap } from "@/lib/errors";
import { formatDecimal, formatRate } from "@/lib/format";
import { cn } from "@/lib/utils";
import { METRIC, metricTitle, BANK_POLICY as T } from "@/texts";

type Overview = Schemas["PolicyOverview"];
type Factor = Overview["factors"][number];
type Zone = keyof Schemas["PolicyZones"];
const EDITABLE = ["A", "B", "C", "D"] as const;
type Boundaries = Record<(typeof EDITABLE)[number], number>;
const ZONE_OF: Record<string, Zone> = {
  A: "auto",
  B: "auto",
  C: "manual",
  D: "manual",
  E: "decline",
  stop: "decline",
};

/** XP7: the policy in force and «what if a grade boundary moves» on the synthetic population. */
export function BankPolicyPage() {
  const policy = useQuery({
    queryKey: ["bank", "policy"],
    queryFn: async () => unwrap(await api.GET("/api/bank/policy")),
  });
  if (policy.isPending) return <PageSkeleton />;
  if (policy.isError) return <ErrorState error={policy.error} onRetry={() => policy.refetch()} />;
  const data = policy.data;
  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={T.title} subtitle={T.subtitle(data.policy_version, data.model_version)} />
      <div className="grid gap-6 lg:grid-cols-2">
        <Grades data={data} />
        <Stops stops={data.stop_factors} />
      </div>
      <Factors factors={data.factors} />
      <WhatIf data={data} />
    </div>
  );
}

function current(data: Overview): Boundaries {
  const found = Object.fromEntries(data.grades.map((row) => [row.grade, row.min_total]));
  return { A: found.A ?? 90, B: found.B ?? 75, C: found.C ?? 60, D: found.D ?? 50 };
}

function Grades({ data }: { data: Overview }) {
  const lowestBelow = data.grades.at(-1)?.min_total ?? 0;
  return (
    <Card className="flex flex-col gap-3">
      <CardTitle>{T.grades}</CardTitle>
      <table className="w-full text-sm">
        <thead className="text-left text-ink-muted">
          <tr>
            <th className="py-1 pr-4 font-normal">{T.gradeCol}</th>
            <th className="py-1 pr-4 font-normal">{T.minCol}</th>
            <th className="py-1 pr-4 font-normal">{T.meaningCol}</th>
          </tr>
        </thead>
        <tbody>
          {data.grades.map((row) => (
            <tr key={row.grade} className="border-t border-line">
              <td className="py-2 pr-4 font-semibold">{row.grade}</td>
              <td className="tabular py-2 pr-4">{row.min_total}</td>
              <td className="py-2 pr-4">{T.meaning[ZONE_OF[row.grade] ?? "manual"]}</td>
            </tr>
          ))}
          <tr className="border-t border-line">
            <td className="py-2 pr-4 font-semibold">{data.lowest_grade}</td>
            <td className="tabular py-2 pr-4">{T.below(lowestBelow)}</td>
            <td className="py-2 pr-4">{T.meaning.decline}</td>
          </tr>
        </tbody>
      </table>
    </Card>
  );
}

function Stops({ stops }: { stops: Overview["stop_factors"] }) {
  return (
    <Card className="flex flex-col gap-3">
      <CardTitle>{T.stops}</CardTitle>
      <ul className="m-0 flex list-disc flex-col gap-2 pl-5 text-sm">
        <li>{T.stopRegistry}</li>
        <li>{T.stopOverdue(stops.current_overdue_days)}</li>
        <li>{T.stopAge(stops.min_business_age_months)}</li>
        <li>{T.stopMissing(stops.max_missing_key_metrics)}</li>
      </ul>
    </Card>
  );
}

function threshold(name: string, value: string): string {
  const format = METRIC[name]?.format;
  if (format === "percent") return formatRate(value);
  if (format === "months") return `${formatDecimal(value)} мес`;
  return formatDecimal(value);
}

function scale(factor: Factor): string {
  if (factor.name === "bki_history") return T.bki;
  if (factor.name === "transparent_business") return T.fns;
  const sign = factor.higher_is_better ? T.atLeast : T.atMost;
  const steps = factor.steps.map(
    (step) => `${sign} ${threshold(factor.name, step.threshold)} — ${T.points(step.points)}`,
  );
  return [...steps, T.floor(factor.floor_points)].join("; ");
}

function Factors({ factors }: { factors: Factor[] }) {
  return (
    <Card className="flex flex-col gap-3">
      <CardTitle>{T.factors}</CardTitle>
      <table className="w-full text-sm">
        <thead className="text-left text-ink-muted">
          <tr>
            <th className="py-1 pr-4 font-normal">{T.factorCol}</th>
            <th className="py-1 pr-4 font-normal">{T.maxCol}</th>
            <th className="py-1 pr-4 font-normal">{T.scaleCol}</th>
            <th className="py-1 pr-4 font-normal">{T.unknownCol}</th>
          </tr>
        </thead>
        <tbody>
          {factors.map((factor) => (
            <tr key={factor.name} data-factor={factor.name} className="border-t border-line">
              <td className="py-2 pr-4 font-semibold">{metricTitle(factor.name)}</td>
              <td className="tabular py-2 pr-4">{T.points(factor.max_points)}</td>
              <td className="py-2 pr-4">{scale(factor)}</td>
              <td className="tabular py-2 pr-4">{T.points(factor.unknown_points)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

function WhatIf({ data }: { data: Overview }) {
  const baseline = current(data);
  const [grades, setGrades] = useState<Boundaries>(baseline);
  const recount = useMutation({
    mutationFn: async (body: Boundaries) =>
      unwrap(await api.POST("/api/bank/policy/what-if", { body: { grades: body } })),
  });
  const { mutate } = recount;
  // The first answer is the policy in force: the table is there before any change.
  // biome-ignore lint/correctness/useExhaustiveDependencies: once, on the policy in force
  useEffect(() => mutate(baseline), [data.policy_version]);
  const result = recount.data;
  return (
    <Card className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <CardTitle>{T.whatIf}</CardTitle>
        <p className="m-0 text-sm text-ink-muted">{T.whatIfHint}</p>
      </div>
      <form
        className="flex flex-wrap items-end gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          recount.mutate(grades);
        }}
      >
        {EDITABLE.map((grade) => (
          <BoundaryInput
            key={grade}
            grade={grade}
            value={grades[grade]}
            onChange={(value) => setGrades((old) => ({ ...old, [grade]: value }))}
          />
        ))}
        <Button type="submit" loading={recount.isPending}>
          {T.recount}
        </Button>
        <Button
          type="button"
          variant="ghost"
          onClick={() => {
            setGrades(baseline);
            recount.mutate(baseline);
          }}
        >
          {T.reset}
        </Button>
      </form>
      {recount.isError ? (
        <p role="alert" className="m-0 text-sm text-status-danger">
          {errorMessage(recount.error)}
        </p>
      ) : null}
      {result ? <Impact result={result} /> : null}
    </Card>
  );
}

function BoundaryInput({
  grade,
  value,
  onChange,
}: {
  grade: string;
  value: number;
  onChange: (value: number) => void;
}) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-sm text-ink-muted">
        {T.gradeCol} {grade}, {T.minCol.toLowerCase()}
      </label>
      <Input
        id={id}
        type="number"
        min={1}
        max={100}
        className="w-28"
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
      />
    </div>
  );
}

function Impact({ result }: { result: Schemas["PolicyWhatIf"] }) {
  const label = (grade: string) => (grade === "stop" ? T.stop : grade);
  return (
    <div className="flex flex-col gap-4" aria-live="polite">
      <p className="m-0 text-sm text-ink-muted">{T.population(result.companies)}</p>
      <p className="m-0 font-display text-xl font-bold">
        {result.changed > 0 ? T.changed(result.changed, result.companies) : T.nothingChanged}
      </p>
      <div className="grid gap-6 lg:grid-cols-2">
        <table className="w-full text-sm" aria-label={T.gradeCol}>
          <thead className="text-left text-ink-muted">
            <tr>
              <th className="py-1 pr-4 font-normal">{T.gradeCol}</th>
              <th className="py-1 pr-4 font-normal">{T.nowCol}</th>
              <th className="py-1 pr-4 font-normal">{T.thenCol}</th>
              <th className="py-1 pr-4 font-normal">{T.diffCol}</th>
            </tr>
          </thead>
          <tbody>
            {result.before.map((row, index) => {
              const after = result.after[index]?.count ?? 0;
              const diff = after - row.count;
              return (
                <tr key={row.grade} className="border-t border-line">
                  <td className="py-2 pr-4 font-semibold">{label(row.grade)}</td>
                  <td className="tabular py-2 pr-4">{row.count}</td>
                  <td className="tabular py-2 pr-4">{after}</td>
                  <td
                    className={cn(
                      "tabular py-2",
                      diff > 0 && "text-status-success",
                      diff < 0 && "text-status-danger",
                    )}
                  >
                    {diff > 0 ? `+${diff}` : diff}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <div className="flex flex-col gap-3">
          <p className="m-0 font-semibold">{T.zones}</p>
          <ul className="m-0 flex list-none flex-col gap-1 p-0 text-sm">
            {(["auto", "manual", "decline"] as const).map((zone) => (
              <li key={zone} data-zone={zone}>
                {T.meaning[zone]}:{" "}
                <span className="tabular font-semibold">
                  {result.zones_before[zone]} → {result.zones_after[zone]}
                </span>
              </li>
            ))}
          </ul>
          {result.transitions.length ? (
            <>
              <p className="m-0 font-semibold">{T.moves}</p>
              <ul className="m-0 flex list-none flex-col gap-1 p-0 text-sm">
                {result.transitions.map((move) => (
                  <li key={`${move.from_grade}-${move.to_grade}`}>
                    {T.move(label(move.from_grade), label(move.to_grade), move.count)}
                  </li>
                ))}
              </ul>
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}
