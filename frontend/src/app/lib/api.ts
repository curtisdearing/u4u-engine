import type { JobStatus, VariantResult } from "./types";

const API_BASE =
  (process.env.NEXT_PUBLIC_API_BASE ?? "https://flmanbiosci.net/api/v1").replace(/\/$/, "");

async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, options);
  if (!res.ok) {
    let message = `Request failed: ${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) message = body.detail;
    } catch {
      // ignore parse errors
    }
    throw new Error(message);
  }
  return res.json() as Promise<T>;
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export async function login(
  email: string,
  password: string
): Promise<{ access_token: string }> {
  const form = new URLSearchParams({ username: email, password });
  return apiFetch("/auth/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form.toString(),
  });
}

export async function signup(
  email: string,
  password: string
): Promise<{ access_token: string }> {
  return apiFetch("/auth/signup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

// ── Upload ────────────────────────────────────────────────────────────────────

export interface PresignResponse {
  upload_url: string;
  s3_key: string;
}

export async function presignUpload(
  filename: string,
  contentType: string,
  token: string
): Promise<PresignResponse> {
  return apiFetch("/upload/presign", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ filename, content_type: contentType }),
  });
}

export async function uploadToS3(
  presign: PresignResponse,
  file: File
): Promise<void> {
  const res = await fetch(presign.upload_url, {
    method: "PUT",
    headers: { "Content-Type": file.type || "application/octet-stream" },
    body: file,
  });
  if (!res.ok) {
    throw new Error(`S3 upload failed: ${res.status} ${res.statusText}`);
  }
}

// ── Jobs ──────────────────────────────────────────────────────────────────────

export async function createJob(
  payload: { s3_key: string; filename: string; filters: string[] },
  token: string
): Promise<{ job_id: string }> {
  return apiFetch("/jobs", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });
}

export async function getJobStatus(
  jobId: string,
  token: string
): Promise<JobStatus> {
  return apiFetch(`/jobs/${jobId}/status`, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function getJobResults(
  jobId: string,
  token: string
): Promise<{ results: VariantResult[] }> {
  return apiFetch(`/jobs/${jobId}/results`, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function deleteJob(
  jobId: string,
  token: string
): Promise<void> {
  await apiFetch(`/jobs/${jobId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
}
