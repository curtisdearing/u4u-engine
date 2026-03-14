"use client";

import { useState } from "react";
import type { VariantResult } from "../lib/types";
import { TierBadge } from "./TierBadge";

interface VariantCardProps {
  variant: VariantResult;
}

export function VariantCard({ variant }: VariantCardProps) {
  const [open, setOpen] = useState(false);

  return (
    <div className="rounded-lg border border-zinc-200 bg-white shadow-sm overflow-hidden">
      {/* Header */}
      <div className="px-5 py-4 flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <TierBadge tier={variant.tier} emoji={variant.emoji} />
            {variant.genes.length > 0 && (
              <span className="text-xs font-mono text-zinc-500">
                {variant.genes.join(", ")}
              </span>
            )}
          </div>
          <p className="font-semibold text-zinc-900 leading-snug">
            {variant.headline}
          </p>
        </div>
        <span className="text-sm font-mono text-zinc-400 shrink-0">
          {variant.location}
        </span>
      </div>

      {/* Plain-English details */}
      <div className="px-5 pb-4 space-y-2 text-sm text-zinc-600">
        <p>{variant.consequence_plain}</p>
        <p>{variant.rarity_plain}</p>
        {variant.clinvar_plain && <p>{variant.clinvar_plain}</p>}
      </div>

      {/* Action hint */}
      <div className="mx-5 mb-4 rounded-md bg-blue-50 border border-blue-100 px-4 py-2 text-sm text-blue-800">
        <span className="font-medium">Next step: </span>
        {variant.action_hint}
      </div>

      {/* Collapsible technical details */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-5 py-2 bg-zinc-50 border-t border-zinc-100 text-xs text-zinc-500 hover:bg-zinc-100 transition-colors"
        aria-expanded={open}
      >
        <span>Technical details</span>
        <span className="text-zinc-400">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="px-5 py-4 border-t border-zinc-100 grid grid-cols-2 gap-x-6 gap-y-2 text-xs text-zinc-600">
          <Detail label="Variant ID" value={variant.variant_id} />
          <Detail label="rsID" value={variant.rsid ?? "—"} />
          <Detail label="Location" value={variant.location} />
          <Detail label="Consequence" value={variant.consequence} />
          <Detail label="Genes" value={variant.genes.join(", ") || "—"} />
          <Detail label="ClinVar" value={variant.clinvar ?? "—"} />
          <Detail
            label="gnomAD AF"
            value={
              variant.gnomad_af != null
                ? variant.gnomad_af.toExponential(2)
                : "—"
            }
          />
          <Detail label="Score" value={String(variant.score)} />
          {variant.disease_name && (
            <Detail
              label="Disease"
              value={variant.disease_name}
              fullWidth
            />
          )}
          {variant.reasons.length > 0 && (
            <div className="col-span-2">
              <dt className="font-medium text-zinc-400 mb-1">
                Scoring factors
              </dt>
              <ul className="list-disc list-inside space-y-0.5">
                {variant.reasons.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Detail({
  label,
  value,
  fullWidth,
}: {
  label: string;
  value: string;
  fullWidth?: boolean;
}) {
  return (
    <div className={fullWidth ? "col-span-2" : ""}>
      <dt className="font-medium text-zinc-400">{label}</dt>
      <dd className="font-mono truncate">{value}</dd>
    </div>
  );
}
