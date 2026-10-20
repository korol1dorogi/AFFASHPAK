import { Construction } from "lucide-react";

import { EmptyState, PageHeader } from "@/components/States";

/** A route that exists but whose screen is another task (docs/tasks.md). The task replaces it. */
export function Placeholder({ title, task, note }: { title: string; task: string; note?: string }) {
  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={title} />
      <EmptyState
        icon={<Construction className="size-6" aria-hidden="true" />}
        title={`Экран в работе — задача ${task}`}
        text={note ?? "Требования — docs/frontend.md, дизайн — docs/design.md."}
      />
    </div>
  );
}
