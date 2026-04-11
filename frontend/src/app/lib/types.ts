export type Tier = "critical" | "high" | "medium" | "low";

export interface VariantResult {
  // Core identity
  variant_id: string;
  rsid: string | null;
  location: string;
  chrom: string;
  pos: number;
  ref: string;
  alt: string;
  zygosity: string;

  // Annotation
  consequence: string;
  genes: string[];
  clinvar: string | null;
  clinvar_raw: string | null;
  disease_name: string | null;
  condition_key: string | null;
  gnomad_af: number | null;
  gnomad_popmax: number | null;
  gnomad_homozygote_count: number | null;

  // Scoring
  score: number;
  tier: Tier;
  reasons: string[];
  frequency_derived_label: string | null;
  carrier_note: string | null;

  // Consumer summary
  emoji: string;
  headline: string;
  consequence_plain: string;
  rarity_plain: string;
  clinvar_plain: string;
  action_hint: string;
  zygosity_plain: string | null;
}

export interface JobStatus {
  job_id: string;
  status: "pending" | "running" | "done" | "failed";
  /** Nested progress object as returned by the API. */
  progress?: { step: string; pct: number };
  count?: number | null;
  results?: VariantResult[] | null;
  error?: string | null;
  filename?: string;
  file_size?: number;
  created_at?: string;
  started_at?: string | null;
  finished_at?: string | null;
}
