"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { listJobs } from "../lib/api";
import type { JobListItem } from "../lib/types";

const STATUS_STYLES: Record<string, string> = {
    done: "bg-green-100 text-green-800",
    failed: "bg-red-100 text-red-700",
    running: "bg-blue-100 text-blue-700",
    pending: "bg-zinc-100 text-zinc-600",
};

const STATUS_ICONS: Record<string, string> = {
    done: "✓",
    failed: "✗",
    running: "⟳",
    pending: "⏳",
};

function timeAgo(iso: string): string {
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    return `${days}d ago`;
}

function formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}

export default function JobsListPage() {
    const router = useRouter();
    const [jobs, setJobs] = useState<JobListItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        listJobs(50)
            .then((data) => {
                setJobs(data.jobs);
                setLoading(false);
            })
            .catch((err: unknown) => {
                setError(err instanceof Error ? err.message : "Failed to load jobs.");
                setLoading(false);
            });
    }, []);

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-[60vh]">
                <div className="flex items-center gap-2 text-zinc-500">
                    <span className="inline-block h-5 w-5 rounded-full border-2 border-blue-500 border-t-transparent animate-spin" />
                    Loading jobs…
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-4">
                <div className="rounded-lg bg-red-50 border border-red-200 p-6 text-center max-w-md space-y-4">
                    <p className="text-red-700 font-medium">Failed to load jobs</p>
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

    const completed = jobs.filter((j) => j.status === "done");
    const inProgress = jobs.filter((j) => j.status === "running" || j.status === "pending");
    const failed = jobs.filter((j) => j.status === "failed");

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-zinc-900">Analysis History</h1>
                    <p className="text-sm text-zinc-500 mt-0.5">
                        {jobs.length} job{jobs.length !== 1 ? "s" : ""} total
                    </p>
                </div>
                <button
                    onClick={() => router.push("/")}
                    className="rounded-lg bg-blue-700 text-white px-4 py-2 text-sm font-medium hover:bg-blue-800 transition-colors"
                >
                    + New Analysis
                </button>
            </div>

            {jobs.length === 0 ? (
                <div className="text-center py-20 space-y-3">
                    <span className="text-4xl">📂</span>
                    <p className="text-zinc-500">No jobs yet.</p>
                    <button
                        onClick={() => router.push("/")}
                        className="text-blue-700 text-sm font-medium hover:underline"
                    >
                        Upload a genome file to get started →
                    </button>
                </div>
            ) : (
                <div className="space-y-4">
                    {/* In-progress jobs */}
                    {inProgress.length > 0 && (
                        <Section title="In Progress" count={inProgress.length}>
                            {inProgress.map((job) => (
                                <JobRow
                                    key={job.job_id}
                                    job={job}
                                    onClick={() => router.push(`/jobs/${job.job_id}`)}
                                />
                            ))}
                        </Section>
                    )}

                    {/* Completed jobs */}
                    {completed.length > 0 && (
                        <Section title="Completed" count={completed.length}>
                            {completed.map((job) => (
                                <JobRow
                                    key={job.job_id}
                                    job={job}
                                    onClick={() => router.push(`/jobs/${job.job_id}/results`)}
                                />
                            ))}
                        </Section>
                    )}

                    {/* Failed jobs */}
                    {failed.length > 0 && (
                        <Section title="Failed" count={failed.length}>
                            {failed.map((job) => (
                                <JobRow
                                    key={job.job_id}
                                    job={job}
                                    onClick={() => router.push(`/jobs/${job.job_id}`)}
                                />
                            ))}
                        </Section>
                    )}
                </div>
            )}
        </div>
    );
}


function Section({
    title,
    count,
    children,
}: {
    title: string;
    count: number;
    children: React.ReactNode;
}) {
    return (
        <div>
            <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wide mb-2">
                {title} ({count})
            </h2>
            <div className="space-y-2">{children}</div>
        </div>
    );
}


function JobRow({ job, onClick }: { job: JobListItem; onClick: () => void }) {
    return (
        <button
            onClick={onClick}
            className="w-full flex items-center justify-between bg-white rounded-lg border border-zinc-200 shadow-sm px-4 py-3 hover:border-blue-300 hover:shadow-md transition-all text-left group"
        >
            <div className="flex items-center gap-3 min-w-0">
                {/* Status badge */}
                <span
                    className={`flex-shrink-0 inline-flex items-center justify-center w-7 h-7 rounded-full text-xs font-bold ${STATUS_STYLES[job.status] ?? STATUS_STYLES.pending
                        }`}
                >
                    {STATUS_ICONS[job.status] ?? "?"}
                </span>

                <div className="min-w-0">
                    <p className="text-sm font-medium text-zinc-900 truncate group-hover:text-blue-700 transition-colors">
                        {job.filename}
                    </p>
                    <p className="text-xs text-zinc-400 mt-0.5">
                        {formatSize(job.file_size)}
                        {job.count != null && ` · ${job.count} variants`}
                        {job.created_at && ` · ${timeAgo(job.created_at)}`}
                    </p>
                </div>
            </div>

            {/* Right side */}
            <div className="flex items-center gap-3 flex-shrink-0 ml-4">
                {job.status === "running" && (
                    <div className="w-20">
                        <div className="h-1.5 rounded-full bg-zinc-100 overflow-hidden">
                            <div
                                className="h-full rounded-full bg-blue-500 transition-all"
                                style={{ width: `${job.progress?.pct ?? 0}%` }}
                            />
                        </div>
                    </div>
                )}
                <span className="text-zinc-300 group-hover:text-blue-500 transition-colors">→</span>
            </div>
        </button>
    );
}
