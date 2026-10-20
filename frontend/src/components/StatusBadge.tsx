import { CircleAlert, CircleCheck, CircleSlash, CircleX, Clock, PenLine } from "lucide-react";

import type { Schemas } from "@/api/client";
import { Badge } from "@/components/ui/badge";
import { STATUS, type StatusGroup } from "@/texts";

const ICON: Record<StatusGroup, typeof Clock> = {
  action: CircleAlert,
  progress: Clock,
  success: CircleCheck,
  danger: CircleX,
  neutral: CircleSlash,
};

const WRITING = new Set<Schemas["ApplicationStatus"]>(["draft", "signing"]);

export function StatusBadge({
  status,
  size = "sm",
}: {
  status: Schemas["ApplicationStatus"];
  size?: "sm" | "md";
}) {
  const text = STATUS[status];
  const Icon = WRITING.has(status) ? PenLine : ICON[text.group];
  return (
    <Badge variant={text.group} size={size} data-status={status}>
      <Icon aria-hidden="true" />
      {text.label}
    </Badge>
  );
}
