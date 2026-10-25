import type { Schemas } from "@/api/client";
import { EmptyState } from "@/components/States";
import { Card, CardTitle } from "@/components/ui/card";
import { ScoreBreakdown } from "@/components/ScoreBreakdown";
import { BANK_CARD } from "@/texts";

const T = BANK_CARD.scoring;

export function ScoringTab({ score }: { score: Schemas["Score"] | null }) {
  if (!score) return <EmptyState title={T.empty} text={T.emptyText} />;
  return (
    <Card>
      <CardTitle>{T.title}</CardTitle>
      <ScoreBreakdown score={score} />
    </Card>
  );
}
