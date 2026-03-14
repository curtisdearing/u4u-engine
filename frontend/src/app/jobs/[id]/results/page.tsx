"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter, useParams } from "next/navigation";
import { useAuth } from "../../../lib/auth";
import { getJobResults, deleteJob } from "../../../lib/api";
import type { VariantResult, Tier } from "../../../lib/types";
import { VariantCard } from "../../../components/VariantCard";
import { SummaryMetrics } from "../../../components/SummaryMetrics";

const TIER_ORDER: Tier[] = ["critical", "high", "medium", "low"];

export default function ResultsPage() {
  const router = useRouter();
  const params = useParams();
  const jobId = params.id as string;
  const { token } = useAuth();

  const [results, setResults] = useState<VariantResult[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tierFilter, setTierFilter] = useState<Tier | "all">("all");
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (!token) {
      router.push("/auth");
      return;
    }

    getJobResults(jobId, token)
      .then((data) => setResults(data.results))
      .catch((err: unknown) =>
        setError(
          err instanceof Error ? err.message : "Failed to load results."
        )
      );
  }, [jobId, token, router]);

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

  async function handleDelete() {
    if (!token) return;
    if (!confirm("Delete this job and all results? This cannot be undone."))
      return;
    setDeleting(true);
    try {
      await deleteJob(jobId, token);
      router.push("/");
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Delete failed.");
      setDeleting(false);
    }
  }

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
        <div className="flex gap-2">
          <button
            onClick={downloadCsv}
            className="rounded-lg border border-zinc-200 bg-white text-zinc-700 px-4 py-2 text-sm font-medium hover:bg-zinc-50 transition-colors"
          >
            ⬇ Download CSV
          </button>
          <button
            onClick={handleDelete}
            disabled={deleting}
            className="rounded-lg border border-red-200 text-red-600 px-4 py-2 text-sm font-medium hover:bg-red-50 transition-colors disabled:opacity-50"
          >
            {deleting ? "Deleting…" : "Delete job"}
          </button>
        </div>
      </div>

      {/* Summary metrics */}
      <SummaryMetrics results={results} />

      {/* Tier filter */}
      <div className="flex flex-wrap gap-2">
        {(["all", ...TIER_ORDER] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTierFilter(t)}
            className={`rounded-full px-3 py-1 text-xs font-medium transition-colors capitalize ${
              tierFilter === t
                ? "bg-blue-700 text-white"
                : "bg-white border border-zinc-200 text-zinc-600 hover:bg-zinc-50"
            }`}
          >
            {t === "all" ? `All (${results.length})` : `${t} (${results.filter((r) => r.tier === t).length})`}
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
