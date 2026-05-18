"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { getJobStatus } from "../../lib/api";
import type { JobStatus } from "../../lib/types";

const POLL_INTERVAL_MS = 2000;

export default function JobStatusPage() {
  const router = useRouter();
  const params = useParams();
  const jobId = params.id as string;

  const [status, setStatus] = useState<JobStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    async function poll() {
      try {
        const data = await getJobStatus(jobId);
        setStatus(data);

        if (data.status === "done") {
          clearInterval(intervalRef.current!);
          router.push(`/jobs/${jobId}/results`);
        } else if (data.status === "failed") {
          clearInterval(intervalRef.current!);
          setError(data.error_message ?? "The analysis job failed. Please try again.");
        }
      } catch (err: unknown) {
        clearInterval(intervalRef.current!);
        setError(err instanceof Error ? err.message : "Failed to fetch job status.");
      }
    }

    poll();
    intervalRef.current = setInterval(poll, POLL_INTERVAL_MS);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [jobId, router]);

  const progress = status?.progress_pct ?? 0;
  const currentStep = status?.progress_step ?? "";

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-8">
      <div className="text-center space-y-2">
        <h1 className="text-2xl font-bold text-zinc-900">Analyzing Variants</h1>
        <p className="text-zinc-500 text-sm">
          Job ID:{" "}
          <code className="font-mono bg-zinc-100 px-1.5 py-0.5 rounded text-xs">
            {jobId}
          </code>
        </p>
      </div>

      {error ? (
        <div className="w-full max-w-md rounded-lg bg-red-50 border border-red-200 p-6 text-center space-y-4">
          <p className="text-red-700 font-medium">Analysis Failed</p>
          <p className="text-sm text-red-600">{error}</p>
          <button
            onClick={() => router.push("/")}
            className="rounded-lg bg-red-600 text-white px-5 py-2 text-sm font-medium hover:bg-red-700 transition-colors"
          >
            Try again
          </button>
        </div>
      ) : (
        <div className="w-full max-w-md space-y-4">
          <div className="bg-white rounded-xl border border-zinc-200 shadow-sm p-6 space-y-4">
            {/* Progress bar */}
            <div>
              <div className="flex justify-between text-xs text-zinc-500 mb-1.5">
                <span>
                  {status?.status === "pending"
                    ? "Queued…"
                    : currentStep || "Processing…"}
                </span>
                <span>{progress}%</span>
              </div>
              <div className="h-2.5 rounded-full bg-zinc-100 overflow-hidden">
                <div
                  className="h-full rounded-full bg-blue-600 transition-all duration-500"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>

            {/* Steps legend */}
            <div className="space-y-2">
              <Step
                label="Parsing variants"
                done={progress >= 25}
                active={status?.status === "running" && progress < 25}
              />
              <Step
                label="Resolving rsIDs"
                done={progress >= 50}
                active={progress >= 25 && progress < 50}
              />
              <Step
                label="Annotating (VEP / ClinVar / gnomAD)"
                done={progress >= 85}
                active={progress >= 50 && progress < 85}
              />
              <Step
                label="Scoring &amp; tiering"
                done={progress >= 100}
                active={progress >= 85 && progress < 100}
              />
            </div>
          </div>

          <p className="text-center text-xs text-zinc-400">
            This page updates automatically. Do not close this tab.
          </p>
        </div>
      )}
    </div>
  );
}

function Step({
  label,
  done,
  active,
}: {
  label: string;
  done: boolean;
  active: boolean;
}) {
  return (
    <div className="flex items-center gap-2 text-sm">
      {done ? (
        <span className="text-green-500">✓</span>
      ) : active ? (
        <span className="inline-block h-3 w-3 rounded-full border-2 border-blue-500 border-t-transparent animate-spin" />
      ) : (
        <span className="inline-block h-3 w-3 rounded-full border border-zinc-300" />
      )}
      <span
        className={
          done
            ? "text-zinc-700 line-through decoration-zinc-300"
            : active
              ? "text-zinc-900 font-medium"
              : "text-zinc-400"
        }
        dangerouslySetInnerHTML={{ __html: label }}
      />
    </div>
  );
}
