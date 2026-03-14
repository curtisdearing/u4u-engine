export type Tier = "critical" | "high" | "medium" | "low";

export interface VariantResult {
  variant_id: string;
  rsid: string | null;
  location: string;
  genes: string[];
  consequence: string;
  tier: Tier;
  score: number;
  clinvar: string | null;
  disease_name: string | null;
  gnomad_af: number | null;
  headline: string;
  emoji: string;
  consequence_plain: string;
  rarity_plain: string;
  clinvar_plain: string | null;
  action_hint: string;
  reasons: string[];
}

export interface JobStatus {
  status: "queued" | "running" | "complete" | "failed";
  progress: number;
  error?: string | null;
}

export interface FilterOption {
  key: string;
  label: string;
  description: string;
}

export type FilterKey = string;

export const FILTER_OPTIONS: FilterOption[] = [
  {
    key: "acmg81_rsids.txt",
    label: "ACMG SF v3.2 (81 genes)",
    description:
      "Screens for variants in the 81 genes recommended for secondary findings by the American College of Medical Genetics.",
  },
];
