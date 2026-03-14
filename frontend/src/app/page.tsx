"use client";

import { useCallback, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "./lib/auth";
import { FILTER_OPTIONS, type FilterKey } from "./lib/types";
import { presignUpload, uploadToS3, createJob } from "./lib/api";

const ACCEPTED = ".vcf,.txt,.csv";
const MAX_SIZE_MB = 100;

export default function UploadPage() {
  const router = useRouter();
  const { token } = useAuth();

  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [filters, setFilters] = useState<Set<FilterKey>>(
    new Set(["acmg81_rsids.txt"])
  );
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [step, setStep] = useState<string>("");
  const inputRef = useRef<HTMLInputElement>(null);

  /* ---- file selection helpers ---- */

  function validateFile(f: File): string | null {
    const ext = f.name.split(".").pop()?.toLowerCase() ?? "";
    if (!["vcf", "txt", "csv"].includes(ext))
      return "Only .vcf, .txt, and .csv files are accepted.";
    if (f.size > MAX_SIZE_MB * 1024 * 1024)
      return `File must be ≤ ${MAX_SIZE_MB} MB.`;
    return null;
  }

  function handleFileChange(f: File) {
    const err = validateFile(f);
    if (err) {
      setError(err);
      setFile(null);
    } else {
      setError(null);
      setFile(f);
    }
  }

  const onInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) handleFileChange(f);
  };

  const onDrop = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFileChange(f);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* ---- filter toggle ---- */

  function toggleFilter(key: FilterKey) {
    setFilters((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  /* ---- submission ---- */

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;

    if (!token) {
      router.push("/auth");
      return;
    }

    setError(null);
    setSubmitting(true);

    try {
      setStep("Requesting upload URL…");
      const presign = await presignUpload(file.name, file.type || "application/octet-stream", token);

      setStep("Uploading file…");
      await uploadToS3(presign, file);

      setStep("Creating analysis job…");
      const { job_id } = await createJob(
        {
          s3_key: presign.s3_key,
          filename: file.name,
          filters: Array.from(filters),
        },
        token
      );

      router.push(`/jobs/${job_id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "An unexpected error occurred.");
      setSubmitting(false);
      setStep("");
    }
  }

  return (
    <div className="space-y-8">
      {/* Hero */}
      <div className="text-center space-y-2">
        <h1 className="text-3xl font-bold text-zinc-900">
          Genome Variant Analysis
        </h1>
        <p className="text-zinc-500 max-w-lg mx-auto">
          Upload a genome file and receive a clinically prioritized variant
          report annotated with ClinVar, gnomAD, and VEP data.
        </p>
      </div>

      <form
        onSubmit={handleSubmit}
        className="bg-white rounded-xl border border-zinc-200 shadow-sm p-6 space-y-6"
      >
        {/* Drop zone */}
        <div>
          <label className="block text-sm font-medium text-zinc-700 mb-2">
            Genome file
          </label>
          <div
            role="button"
            tabIndex={0}
            aria-label="File drop zone"
            className={`flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-10 cursor-pointer transition-colors ${
              dragging
                ? "border-blue-500 bg-blue-50"
                : file
                  ? "border-green-400 bg-green-50"
                  : "border-zinc-300 hover:border-blue-400 hover:bg-blue-50"
            }`}
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            onClick={() => inputRef.current?.click()}
            onKeyDown={(e) => e.key === "Enter" && inputRef.current?.click()}
          >
            <input
              ref={inputRef}
              type="file"
              accept={ACCEPTED}
              className="sr-only"
              onChange={onInputChange}
            />
            {file ? (
              <>
                <span className="text-3xl mb-2">✅</span>
                <p className="font-medium text-green-700">{file.name}</p>
                <p className="text-xs text-zinc-400 mt-1">
                  {(file.size / 1024 / 1024).toFixed(2)} MB — click to change
                </p>
              </>
            ) : (
              <>
                <span className="text-3xl mb-2">📂</span>
                <p className="font-medium text-zinc-700">
                  Drag &amp; drop or click to choose
                </p>
                <p className="text-xs text-zinc-400 mt-1">
                  Accepts .vcf, .txt, .csv — max 100 MB
                </p>
              </>
            )}
          </div>
        </div>

        {/* Filters */}
        <div>
          <p className="text-sm font-medium text-zinc-700 mb-3">
            Variant filters{" "}
            <span className="text-zinc-400 font-normal">
              (leave all unchecked to analyze everything)
            </span>
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {FILTER_OPTIONS.map((opt) => (
              <label
                key={opt.key}
                className={`flex items-start gap-3 rounded-lg border p-3 cursor-pointer transition-colors ${
                  filters.has(opt.key)
                    ? "border-blue-400 bg-blue-50"
                    : "border-zinc-200 hover:border-zinc-300"
                }`}
              >
                <input
                  type="checkbox"
                  className="mt-0.5 h-4 w-4 rounded text-blue-600"
                  checked={filters.has(opt.key)}
                  onChange={() => toggleFilter(opt.key)}
                />
                <div>
                  <p className="text-sm font-medium text-zinc-800">
                    {opt.label}
                  </p>
                  <p className="text-xs text-zinc-500">{opt.description}</p>
                </div>
              </label>
            ))}
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {/* Submit */}
        <button
          type="submit"
          disabled={!file || submitting}
          className="w-full rounded-lg bg-blue-700 text-white py-3 font-medium text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-blue-800 transition-colors"
        >
          {submitting ? step || "Submitting…" : "Analyze Variants"}
        </button>

        {!token && (
          <p className="text-center text-xs text-zinc-400">
            You will be prompted to sign in before your file is uploaded.
          </p>
        )}
      </form>

      {/* Privacy notice */}
      <p className="text-center text-xs text-zinc-400">
        Genome files are encrypted in transit and at rest and are automatically
        deleted within 24 hours of job completion.
      </p>
    </div>
  );
}
