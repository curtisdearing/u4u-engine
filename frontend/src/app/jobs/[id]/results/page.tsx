"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter, useParams } from "next/navigation";
import { getJobStatus } from "../../../lib/api";
import type { VariantResult, Tier, Bpc157Prediction, PeptideMapping, PeptideRecommendation } from "../../../lib/types";
import { VariantCard } from "../../../components/VariantCard";
import { SummaryMetrics } from "../../../components/SummaryMetrics";

const TIER_ORDER: Tier[] = ["critical", "high", "medium", "low"];

const BPC157_TIER_COLORS: Record<string, string> = {
  likely_good: "bg-green-100 text-green-800 border-green-300",
  possible: "bg-yellow-100 text-yellow-800 border-yellow-300",
  uncertain: "bg-zinc-100 text-zinc-600 border-zinc-300",
  low_confidence: "bg-red-50 text-red-600 border-red-200",
};

const BPC157_TIER_LABELS: Record<string, string> = {
  likely_good: "Likely Good Candidate",
  possible: "Possible Candidate",
  uncertain: "Uncertain",
  low_confidence: "Low Confidence",
};

export default function ResultsPage() {
  const router = useRouter();
  const params = useParams();
  const jobId = params.id as string;

  const [results, setResults] = useState<VariantResult[] | null>(null);
  const [bpc157, setBpc157] = useState<Bpc157Prediction | null>(null);
  const [peptides, setPeptides] = useState<PeptideMapping | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tierFilter, setTierFilter] = useState<Tier | "all">("all");

  useEffect(() => {
    getJobStatus(jobId)
      .then((data) => {
        if (data.results) {
          // V3: results is a dict with variants and enrichment data
          const res = data.results;
          if (res.variants) {
            setResults(res.variants);
          } else {
            setError("Results not available. The job may still be running.");
          }
          if (res.bpc157_prediction) {
            setBpc157(res.bpc157_prediction);
          }
          if (res.peptide_recommendations) {
            setPeptides(res.peptide_recommendations);
          }
        } else {
          setError("Results not available. The job may still be running.");
        }
      })
      .catch((err: unknown) =>
        setError(err instanceof Error ? err.message : "Failed to load results.")
      );
  }, [jobId]);

  const downloadCsv = useCallback(() => {
    if (!results) return;

    const headers = [
      "variant_id",
      "rsid",
      "location",
      "genes",
      "consequence",
      "tier",
      "score",
      "clinvar",
      "disease_name",
      "gnomad_af",
      "headline",
    ];

    const rows = results.map((r) =>
      [
        r.variant_id,
        r.rsid ?? "",
        r.location,
        r.genes.join(";"),
        r.consequence,
        r.tier,
        r.score,
        r.clinvar ?? "",
        r.disease_name ?? "",
        r.gnomad_af ?? "",
        `"${r.headline.replace(/"/g, '""')}"`,
      ].join(",")
    );

    const csv = [headers.join(","), ...rows].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `variants-${jobId}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }, [results, jobId]);

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-4">
        <div className="rounded-lg bg-red-50 border border-red-200 p-6 text-center max-w-md space-y-4">
          <p className="text-red-700 font-medium">Failed to load results</p>
          <p className="text-sm text-red-600">{error}</p>
          <button
            onClick={() => router.push("/")}
            className="rounded-lg bg-blue-700 text-white px-5 py-2 text-sm font-medium hover:bg-blue-800 transition-colors"
          >
            Back to upload
          </button>
        </div>
      </div>
    );
  }

  if (!results) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="flex items-center gap-2 text-zinc-500">
          <span className="inline-block h-5 w-5 rounded-full border-2 border-blue-500 border-t-transparent animate-spin" />
          Loading results…
        </div>
      </div>
    );
  }

  const filtered =
    tierFilter === "all"
      ? results
      : results.filter((r) => r.tier === tierFilter);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-zinc-900">Variant Report</h1>
          <p className="text-sm text-zinc-500 font-mono mt-0.5">{jobId}</p>
        </div>
        <button
          onClick={downloadCsv}
          className="rounded-lg border border-zinc-200 bg-white text-zinc-700 px-4 py-2 text-sm font-medium hover:bg-zinc-50 transition-colors"
        >
          ⬇ Download CSV
        </button>
      </div>

      {/* Summary metrics */}
      <SummaryMetrics results={results} />

      {/* BPC-157 Prediction Card */}
      {bpc157 && <Bpc157Card prediction={bpc157} />}

      {/* Peptide Recommendations Card */}
      {peptides && <PeptideCard mapping={peptides} />}

      {/* Tier filter */}
      <div className="flex flex-wrap gap-2">
        {(["all", ...TIER_ORDER] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTierFilter(t)}
            className={`rounded-full px-3 py-1 text-xs font-medium transition-colors capitalize ${tierFilter === t
              ? "bg-blue-700 text-white"
              : "bg-white border border-zinc-200 text-zinc-600 hover:bg-zinc-50"
              }`}
          >
            {t === "all"
              ? `All (${results.length})`
              : `${t} (${results.filter((r) => r.tier === t).length})`}
          </button>
        ))}
      </div>

      {/* Variant cards */}
      {filtered.length === 0 ? (
        <div className="text-center py-16 text-zinc-400">
          No variants match the selected filter.
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((v) => (
            <VariantCard key={v.variant_id} variant={v} />
          ))}
        </div>
      )}

      <p className="text-center text-xs text-zinc-400 pb-8">
        {filtered.length} of {results.length} variants shown ·{" "}
        <button
          onClick={() => router.push("/")}
          className="underline hover:no-underline"
        >
          Run another analysis
        </button>
      </p>
    </div>
  );
}


/* ── BPC-157 Prediction Card ────────────────────────────────────────────── */

function Bpc157Card({ prediction }: { prediction: Bpc157Prediction }) {
  const [expanded, setExpanded] = useState(false);

  const tierColor = BPC157_TIER_COLORS[prediction.responder_tier] ?? BPC157_TIER_COLORS.low_confidence;
  const tierLabel = BPC157_TIER_LABELS[prediction.responder_tier] ?? "Unknown";

  return (
    <div className="bg-white rounded-xl border border-zinc-200 shadow-sm overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-5 text-left hover:bg-zinc-50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className="text-xl">🧬</span>
          <div>
            <h2 className="font-semibold text-zinc-900 text-sm">
              BPC-157 Response Prediction
            </h2>
            <p className="text-xs text-zinc-500 mt-0.5">
              {prediction.primary_use_case_display}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span
            className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${tierColor}`}
          >
            {tierLabel}
          </span>
          <span className="text-zinc-400 text-sm">{expanded ? "▲" : "▼"}</span>
        </div>
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="border-t border-zinc-100 p-5 space-y-5">
          {/* Summary */}
          <p className="text-sm text-zinc-700 leading-relaxed">
            {prediction.summary_text}
          </p>

          {/* Pathways affected */}
          {prediction.pathways_affected.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wide mb-2">
                Pathways Affected
              </h3>
              <div className="space-y-2">
                {prediction.pathways_affected.map((p) => (
                  <div
                    key={p.pathway}
                    className="flex items-start gap-2 text-sm"
                  >
                    <span className="text-blue-500 mt-0.5">●</span>
                    <div>
                      <span className="font-medium text-zinc-800">
                        {p.display_name}
                      </span>
                      <span className="text-zinc-400 ml-1.5">
                        ({p.genes_hit.join(", ")} — {Math.round(p.coverage * 100)}%
                        coverage)
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Candidate factors */}
          {prediction.candidate_factors.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wide mb-2">
                Genetic Modifiers Detected
              </h3>
              <div className="space-y-1.5">
                {prediction.candidate_factors.map((f) => (
                  <div key={f.rsid} className="text-sm text-zinc-700">
                    <span className="font-mono text-xs bg-zinc-100 px-1 py-0.5 rounded">
                      {f.rsid}
                    </span>{" "}
                    <span className="text-zinc-500">({f.gene})</span> —{" "}
                    {f.effect}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Biomarker recommendations */}
          {prediction.biomarker_recommendations.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wide mb-2">
                Recommended Biomarker Panel
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                {prediction.biomarker_recommendations.map((b) => (
                  <div
                    key={b.name}
                    className="flex items-center justify-between text-sm bg-zinc-50 rounded px-3 py-1.5"
                  >
                    <span className="text-zinc-700">{b.name}</span>
                    <span className="text-xs text-zinc-400">
                      {b.expected_change}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Disclaimer */}
          <div className="rounded-md bg-amber-50 border border-amber-200 px-4 py-3">
            <p className="text-xs text-amber-800 leading-relaxed">
              <strong>⚠️ Important:</strong> {prediction.disclaimer}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}


/* ── Peptide Recommendations Card ──────────────────────────────────────── */

const COVERAGE_COLORS: Record<string, string> = {
  full: "bg-green-100 text-green-800 border-green-300",
  partial: "bg-yellow-100 text-yellow-800 border-yellow-300",
  none: "bg-zinc-100 text-zinc-500 border-zinc-200",
};

function PeptideCard({ mapping }: { mapping: PeptideMapping }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="bg-white rounded-xl border border-zinc-200 shadow-sm overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-5 text-left hover:bg-zinc-50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className="text-xl">💊</span>
          <div>
            <h2 className="font-semibold text-zinc-900 text-sm">
              Peptide Therapy Genotyping Coverage
            </h2>
            <p className="text-xs text-zinc-500 mt-0.5">
              {mapping.peptides_with_coverage} of {mapping.recommendations.length} peptides
              have genotyping data
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span
            className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${mapping.peptides_with_coverage > 0
              ? "bg-green-100 text-green-800 border-green-300"
              : "bg-zinc-100 text-zinc-500 border-zinc-200"
              }`}
          >
            {mapping.peptides_with_coverage > 0
              ? `${mapping.peptides_with_coverage} Covered`
              : "No Coverage"}
          </span>
          <span className="text-zinc-400 text-sm">{expanded ? "▲" : "▼"}</span>
        </div>
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="border-t border-zinc-100 p-5 space-y-5">
          {/* Summary */}
          <p className="text-sm text-zinc-700 leading-relaxed">
            {mapping.summary_text}
          </p>

          {/* Peptide list */}
          <div className="space-y-3">
            {mapping.recommendations.map((rec) => {
              const coverageLevel =
                rec.coverage >= 1 ? "full" : rec.coverage > 0 ? "partial" : "none";
              const coverageColor = COVERAGE_COLORS[coverageLevel];

              return (
                <div
                  key={rec.peptide_name}
                  className="rounded-lg border border-zinc-200 p-4 space-y-2"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <span className="font-medium text-zinc-900 text-sm">
                        {rec.peptide_name}
                      </span>
                      <span className="ml-2 text-xs text-zinc-400">
                        {rec.category_display}
                      </span>
                    </div>
                    <span
                      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium whitespace-nowrap ${coverageColor}`}
                    >
                      {Math.round(rec.coverage * 100)}% coverage
                    </span>
                  </div>

                  {/* Gene details */}
                  <div className="flex flex-wrap gap-1.5">
                    {rec.genes_for_genotyping.map((gene) => {
                      const found = rec.genes_found.includes(gene);
                      return (
                        <span
                          key={gene}
                          className={`inline-flex items-center rounded px-1.5 py-0.5 text-xs font-mono ${found
                            ? "bg-green-50 text-green-700 border border-green-200"
                            : "bg-zinc-50 text-zinc-400 border border-zinc-200"
                            }`}
                        >
                          {found ? "✓" : "○"} {gene}
                        </span>
                      );
                    })}
                  </div>

                  {/* Rationale */}
                  <p className="text-xs text-zinc-500 leading-relaxed">
                    {rec.rationale}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
