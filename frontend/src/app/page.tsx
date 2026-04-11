"use client";

import { useCallback, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { analyzeFile } from "./lib/api";

const ACCEPTED = ".vcf,.txt,.csv";
const MAX_SIZE_MB = 100;

export default function UploadPage() {
  const router = useRouter();

  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

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

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setError(null);
    setSubmitting(true);
    try {
      const { job_id } = await analyzeFile(file);
      router.push(`/jobs/${job_id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "An unexpected error occurred.");
      setSubmitting(false);
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
          {submitting ? "Uploading…" : "Analyze Variants"}
        </button>
      </form>

      {/* Privacy notice */}
      <p className="text-center text-xs text-zinc-400">
        Genome files are encrypted in transit and held in memory only during
        processing. They are never written to disk and are discarded as soon as
        your job completes.
      </p>
    </div>
  );
}
