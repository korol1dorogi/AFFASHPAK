import * as Tabs from "@radix-ui/react-tabs";
import type { ReactNode } from "react";
import { useSearchParams } from "react-router";

import { BANK_TABS, type BankTab } from "@/app/routes";
import { cn } from "@/lib/utils";
import { BANK_CARD, BANK_TAB } from "@/texts";

function isTab(value: string | null): value is BankTab {
  return (BANK_TABS as readonly string[]).includes(value ?? "");
}

/**
 * Card tabs kept in ?tab= (docs/frontend.md §1.5). Radix gives the tablist roles and arrow keys.
 * Candidate for B1 as components/ui/tabs.
 */
export function CardTabs({ panels }: { panels: Record<BankTab, ReactNode> }) {
  const [params, setParams] = useSearchParams();
  const raw = params.get("tab");
  const current: BankTab = isTab(raw) ? raw : "application";

  const select = (value: string) => {
    if (!isTab(value)) return;
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.set("tab", value);
        return next;
      },
      { replace: true },
    );
  };

  return (
    <Tabs.Root value={current} onValueChange={select} className="flex flex-col gap-6">
      <Tabs.List
        aria-label={BANK_CARD.tabsLabel}
        className="flex flex-wrap gap-1 border-b border-line"
      >
        {BANK_TABS.map((tab) => (
          <Tabs.Trigger
            key={tab}
            value={tab}
            className={cn(
              "-mb-px cursor-pointer border-b-2 border-transparent px-4 py-2.5 text-sm font-medium text-ink-muted",
              "hover:text-ink focus-visible:rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              "data-[state=active]:border-primary data-[state=active]:text-ink",
            )}
          >
            {BANK_TAB[tab]}
          </Tabs.Trigger>
        ))}
      </Tabs.List>
      {BANK_TABS.map((tab) => (
        <Tabs.Content
          key={tab}
          value={tab}
          className="flex flex-col gap-6 focus-visible:outline-none"
        >
          {panels[tab]}
        </Tabs.Content>
      ))}
    </Tabs.Root>
  );
}
