export type Tier = "critical" | "high" | "medium" | "low";

export interface JobListItem {
  job_id: string;
  status: "pending" | "running" | "done" | "failed";
  filename: string;
  file_size: number;
  count: number | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  progress: { step: string; pct: number };
  error: string | null;
}

export interface VariantResult {
  variant_id: string;
  rsid: string | null;
  location: string;
  consequence: string;
  genes: string[];
  clinvar: string | null;
  disease_name: string | null;
  gnomad_af: number | null;
  score: number;
  tier: Tier;
  reasons: string[];
  emoji: string;
  headline: string;
  consequence_plain: string;
  rarity_plain: string;
  clinvar_plain: string;
  action_hint: string;
}

export interface Bpc157PathwayHit {
  pathway: string;
  display_name: string;
  genes_hit: string[];
  total_genes: number;
  coverage: number;
  relevance: string;
}

export interface Bpc157CandidateFactor {
  rsid: string;
  gene: string;
  pathway: string;
  direction: string;
  effect: string;
}

export interface Bpc157Biomarker {
  name: string;
  expected_change: string;
  category: string;
}

export interface Bpc157Prediction {
  responder_tier: "likely_good" | "possible" | "uncertain" | "low_confidence";
  composite_score: number;
  pathways_affected: Bpc157PathwayHit[];
  primary_use_case: string;
  primary_use_case_display: string;
  primary_use_case_description: string;
  biomarker_recommendations: Bpc157Biomarker[];
  candidate_factors: Bpc157CandidateFactor[];
  summary_text: string;
  disclaimer: string;
}

export interface PeptideRecommendation {
  peptide_name: string;
  genes_for_genotyping: string[];
  genes_found: string[];
  genes_missing: string[];
  coverage: number;
  rationale: string;
  references: string[];
  category: string;
  category_display: string;
}

export interface PeptideMapping {
  recommendations: PeptideRecommendation[];
  summary_text: string;
  genes_found_total: string[];
  peptides_with_coverage: number;
}

export interface JobStatus {
  job_id: string;
  status: "pending" | "running" | "done" | "failed";
  progress_step?: string;
  progress_pct?: number;
  filename?: string;
  created_at?: string;
  error_message?: string;
  // V3: results is now a dict with variants and enrichment data
  results?: {
    variants?: VariantResult[];
    bpc157_prediction?: Bpc157Prediction;
    peptide_recommendations?: PeptideMapping;
    pathway_summary?: unknown;
    receptor_genetics?: unknown;
    prs_profile?: unknown;
    ar_cag_repeat?: unknown;
  };
  variant_count?: number;
}

