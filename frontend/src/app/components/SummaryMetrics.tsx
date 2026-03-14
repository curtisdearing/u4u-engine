"use client";

import type { Tier, VariantResult } from "../lib/types";

interface SummaryMetricsProps {
  results: VariantResult[];
}

const TIER_ORDER: Tier[] = ["critical", "high", "medium", "low"];
const TIER_COLORS: Record<Tier, string> = {
  critical: "text-red-700 bg-red-50 border-red-200",
  high: "text-orange-700 bg-orange-50 border-orange-200",
  medium: "text-yellow-700 bg-yellow-50 border-yellow-200",
  low: "text-green-700 bg-green-50 border-green-200",
};
const TIER_EMOJIS: Record<Tier, string> = {
  critical: "🔴",
  high: "🟠",
  medium: "🟡",
  low: "🟢",
};

export function SummaryMetrics({ results }: SummaryMetricsProps) {
  const counts = TIER_ORDER.reduce(
    (acc, tier) => {
      acc[tier] = results.filter((r) => r.tier === tier).length;
      return acc;
    },
    {} as Record<Tier, number>
  );

  return (
    <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
      <div className="sm:col-span-1 rounded-lg border border-zinc-200 bg-white px-4 py-3 text-center">
        <div className="text-2xl font-bold text-zinc-900">{results.length}</div>
        <div className="text-xs text-zinc-500 mt-0.5">Total Variants</div>
      </div>
      {TIER_ORDER.map((tier) => (
        <div
          key={tier}
          className={`rounded-lg border px-4 py-3 text-center ${TIER_COLORS[tier]}`}
        >
          <div className="text-2xl font-bold">{counts[tier]}</div>
          <div className="text-xs mt-0.5 capitalize">
            {TIER_EMOJIS[tier]} {tier}
          </div>
        </div>
      ))}
    </div>
  );
}
