"use client";

import type { Tier } from "../lib/types";

interface TierBadgeProps {
  tier: Tier;
  emoji: string;
}

const TIER_STYLES: Record<Tier, string> = {
  critical: "bg-red-100 text-red-800 border border-red-300",
  high: "bg-orange-100 text-orange-800 border border-orange-300",
  medium: "bg-yellow-100 text-yellow-800 border border-yellow-300",
  low: "bg-green-100 text-green-800 border border-green-300",
};

export function TierBadge({ tier, emoji }: TierBadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold capitalize ${TIER_STYLES[tier]}`}
    >
      {emoji} {tier}
    </span>
  );
}
