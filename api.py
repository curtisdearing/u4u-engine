"""
api.py — U4U Engine FastAPI wrapper
====================================
Wraps run_pipeline() as an async job queue service.

Architecture
------------
  POST /analyze          — upload file, get back a job_id immediately
  GET  /jobs/{job_id}    — poll for status, progress, and results
  GET  /health           — liveness check

The pipeline runs in a thread pool (blocking IO — external API calls).
The client polls /jobs/{job_id} until status is "done" or "failed".

Job storage
-----------
MVP: in-memory dict (_jobs).  Jobs survive within a process but are lost
on restart.  When you add Postgres, replace _jobs with DB reads/writes and
keep the same endpoint signatures — the frontend polling contract does not change.

Environment variables
---------------------
NCBI_API_KEY   — NCBI API key (optional, raises ClinVar rate limit 3→10 req/s)
DATA_DIR       — path to directory containing rsID filter files (default: "data")
FILTERS        — comma-separated filter filenames (default: "acmg81_rsids.txt")
                 set to "" to run all variants without a panel filter
WORKERS        — thread pool size — set to CPU count of host (default: 4)
MAX_UPLOAD_MB  — file size limit in megabytes (default: 100)
JOB_TTL_HOURS  — hours to keep completed jobs in memory (default: 24)
"""

import asyncio
import logging
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from fastapi import BackgroundTasks, FastAPI, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse

from engine import run_pipeline

# ── Configuration ─────────────────────────────────────────────────────────────

DATA_DIR      = os.getenv("DATA_DIR", "data")
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "100"))
WORKERS       = int(os.getenv("WORKERS", "4"))
JOB_TTL_HOURS = int(os.getenv("JOB_TTL_HOURS", "24"))

_raw_filters = os.getenv("FILTERS", "acmg81_rsids.txt").strip()
FILTERS      = [f.strip() for f in _raw_filters.split(",") if f.strip()] if _raw_filters else []

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("u4u.api")

# ── App ───────────────────────────────────────────────────────────────────────

app      = FastAPI(
    title="U4U Engine API",
    version="2.0.0",
    description="Genomic variant annotation and interpretation pipeline.",
)
_executor = ThreadPoolExecutor(max_workers=WORKERS)

# ── In-memory job store ───────────────────────────────────────────────────────
# Schema per job:
#   status     : "pending" | "running" | "done" | "failed"
#   progress   : {"step": str, "pct": int}
#   count      : int | None     — number of variants found
#   results    : list[dict] | None
#   error      : str | None
#   filename   : str
#   file_size  : int
#   created_at : str (ISO-8601)
#   started_at : str | None
#   finished_at: str | None

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Background job runner ─────────────────────────────────────────────────────

def _progress_callback(job_id: str, step: str, pct: int):
    """Called by the pipeline on each step — updates the in-memory job record."""
    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id]["progress"] = {"step": step, "pct": pct}


def _run_pipeline_task(job_id: str, file_bytes: bytes, filename: str):
    """
    Blocking pipeline run — executed in the thread pool.
    Updates the in-memory job record as it runs.
    """
    with _jobs_lock:
        _jobs[job_id]["status"]     = "running"
        _jobs[job_id]["started_at"] = _now_iso()

    log.info("job=%s starting file=%s size=%d bytes", job_id, filename, len(file_bytes))

    try:
        results = run_pipeline(
            file_bytes,
            filename,
            filters=FILTERS,
            data_dir=DATA_DIR,
            progress_callback=lambda step, pct: _progress_callback(job_id, step, pct),
        )
        with _jobs_lock:
            _jobs[job_id].update({
                "status":      "done",
                "count":       len(results),
                "results":     results,
                "progress":    {"step": "Complete", "pct": 100},
                "finished_at": _now_iso(),
            })
        log.info("job=%s done variants=%d", job_id, len(results))

    except ValueError as exc:
        with _jobs_lock:
            _jobs[job_id].update({
                "status":      "failed",
                "error":       str(exc),
                "finished_at": _now_iso(),
            })
        log.warning("job=%s validation error: %s", job_id, exc)

    except Exception as exc:
        with _jobs_lock:
            _jobs[job_id].update({
                "status":      "failed",
                "error":       "Pipeline error. Check server logs.",
                "finished_at": _now_iso(),
            })
        log.exception("job=%s unhandled pipeline error", job_id)


# ── Periodic job cleanup ──────────────────────────────────────────────────────

async def _cleanup_old_jobs():
    """Remove completed/failed jobs older than JOB_TTL_HOURS to prevent memory leak."""
    while True:
        await asyncio.sleep(3600)  # run hourly
        cutoff = datetime.now(timezone.utc) - timedelta(hours=JOB_TTL_HOURS)
        with _jobs_lock:
            expired = [
                jid for jid, j in _jobs.items()
                if j["status"] in ("done", "failed")
                and j.get("finished_at")
                and datetime.fromisoformat(j["finished_at"]) < cutoff
            ]
            for jid in expired:
                del _jobs[jid]
        if expired:
            log.info("cleanup: removed %d expired jobs", len(expired))


@app.on_event("startup")
async def _startup():
    asyncio.create_task(_cleanup_old_jobs())


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    """
    Liveness check. Returns 200 when the server is up.

    Also reports queue depth so ops can detect backlog.
    """
    with _jobs_lock:
        running = sum(1 for j in _jobs.values() if j["status"] == "running")
        pending = sum(1 for j in _jobs.values() if j["status"] == "pending")
    return {"status": "ok", "jobs_running": running, "jobs_pending": pending}


@app.post("/analyze", status_code=202)
async def analyze(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    """
    Upload a genome file and receive a job_id.

    The file is processed asynchronously. Poll GET /jobs/{job_id} for results.

    Accepted formats: .vcf, .vcf.gz (primary), .txt (23andMe), .csv, rsID list.
    File is read into memory, processed, and discarded — never written to disk.

    Returns
    -------
    {
        "job_id": str,
        "status": "pending",
        "poll_url": "/jobs/{job_id}"
    }

    Status codes
    ------------
    202  Job accepted
    413  File exceeds MAX_UPLOAD_MB limit
    422  Unsupported / empty file (caught before background task starts)
    """
    filename   = file.filename or "upload"
    file_bytes = await file.read()

    # ── Size guard (before job is created) ───────────────────────────────────
    max_bytes = MAX_UPLOAD_MB * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {MAX_UPLOAD_MB} MB limit.",
        )

    if len(file_bytes) == 0:
        raise HTTPException(status_code=422, detail="Empty file.")

    # ── Create job record ─────────────────────────────────────────────────────
    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = {
            "status":      "pending",
            "progress":    {"step": "Queued", "pct": 0},
            "count":       None,
            "results":     None,
            "error":       None,
            "filename":    filename,
            "file_size":   len(file_bytes),
            "created_at":  _now_iso(),
            "started_at":  None,
            "finished_at": None,
        }

    # ── Dispatch to thread pool via BackgroundTasks ──────────────────────────
    # BackgroundTasks runs after the response is sent, in the event loop.
    # We submit to _executor to keep the async event loop free.
    loop = asyncio.get_event_loop()
    background_tasks.add_task(
        loop.run_in_executor,
        _executor,
        _run_pipeline_task,
        job_id,
        file_bytes,
        filename,
    )

    log.info("job=%s queued file=%s size=%d bytes", job_id, filename, len(file_bytes))

    return JSONResponse(
        status_code=202,
        content={
            "job_id":   job_id,
            "status":   "pending",
            "poll_url": f"/jobs/{job_id}",
        },
    )


@app.get("/jobs/{job_id}")
def get_job(job_id: str, include_results: bool = True):
    """
    Poll job status and retrieve results when complete.

    Parameters
    ----------
    include_results : bool
        Set to false to get status/progress without the full results list.
        Useful for a progress bar that only fetches results once status=done.

    Returns
    -------
    {
        "job_id":     str,
        "status":     "pending" | "running" | "done" | "failed",
        "progress":   {"step": str, "pct": int},
        "count":      int | null,
        "results":    [...] | null,    # null if pending/running or include_results=false
        "error":      str | null,
        "filename":   str,
        "file_size":  int,
        "created_at": str,             # ISO-8601
        "started_at": str | null,
        "finished_at":str | null
    }

    Polling guidance
    ----------------
    - Poll every 2–5 seconds while status is "pending" or "running".
    - Stop when status is "done" or "failed".
    - Jobs expire after JOB_TTL_HOURS (default 24h) — 404 after that.
    """
    with _jobs_lock:
        job = _jobs.get(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found or expired.")

    response = dict(job)
    response["job_id"] = job_id

    if not include_results:
        response.pop("results", None)

    return response


@app.get("/jobs")
def list_jobs(limit: int = 20):
    """
    List recent jobs (status only — no results payload).
    Useful for ops dashboards. Returns newest first.
    """
    with _jobs_lock:
        snapshot = sorted(
            [{"job_id": jid, **{k: v for k, v in j.items() if k != "results"}}
             for jid, j in _jobs.items()],
            key=lambda x: x.get("created_at", ""),
            reverse=True,
        )
    return {"jobs": snapshot[:limit]}
