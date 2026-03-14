"""
api.py — U4U Engine FastAPI wrapper
====================================
Exposes run_pipeline() as a web service.

Endpoints
---------
POST /analyze   — upload a genome file, get back annotated variants as JSON
GET  /health    — confirm the server is running

Environment variables
---------------------
NCBI_API_KEY   — NCBI API key (optional, raises ClinVar rate limit from 3 to 10 req/s)
DATA_DIR       — path to directory containing rsID filter files (default: "data")
FILTERS        — comma-separated filter filenames to apply (default: "acmg81_rsids.txt")
                 set to "" to run all variants without a panel filter
WORKERS        — number of threads in the pipeline thread pool (default: 4)
MAX_UPLOAD_MB  — file size limit in megabytes (default: 100)
"""

import os
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

from engine import run_pipeline

# ── Configuration ─────────────────────────────────────────────────────────────

DATA_DIR      = os.getenv("DATA_DIR", "data")
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "100"))
WORKERS       = int(os.getenv("WORKERS", "4"))

_raw_filters  = os.getenv("FILTERS", "acmg81_rsids.txt").strip()
FILTERS       = [f.strip() for f in _raw_filters.split(",") if f.strip()] if _raw_filters else []

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("u4u.api")

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="U4U Engine API",
    version="1.0.0",
    description="Genomic variant annotation and interpretation pipeline.",
)

_executor = ThreadPoolExecutor(max_workers=WORKERS)

# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    """Liveness check. Returns 200 when the server is running."""
    return {"status": "ok"}


@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    """
    Upload a genome file and receive annotated variants as JSON.

    Accepted formats: .vcf, .vcf.gz (primary), .txt (23andMe), .csv, rsID list.
    File is read into memory, processed, and discarded — never written to disk.

    Returns
    -------
    {
        "count": int,
        "results": [
            {
                "variant_id": str,
                "tier": "critical" | "high" | "medium" | "low",
                "score": int,
                "headline": str,
                "genes": [str],
                "clinvar": str | null,
                "disease_name": str | null,
                "condition_key": str | null,
                "gnomad_af": float | null,
                "consequence": str,
                "action_hint": str,
                ... (full field list in engine/__init__.py)
            },
            ...
        ]
    }
    """
    filename = file.filename or "upload"

    # Read file bytes
    file_bytes = await file.read()

    # Guard: enforce size limit before hitting the pipeline validator
    max_bytes = MAX_UPLOAD_MB * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {MAX_UPLOAD_MB} MB limit.",
        )

    log.info("analyze request: file=%s size=%d bytes filters=%s", filename, len(file_bytes), FILTERS)

    # Run pipeline in thread pool — it is blocking IO (external API calls)
    try:
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            _executor,
            lambda: run_pipeline(
                file_bytes,
                filename,
                filters=FILTERS,
                data_dir=DATA_DIR,
            ),
        )
    except ValueError as exc:
        # Raised by the pipeline for bad input (empty file, unsupported format, etc.)
        log.warning("pipeline validation error: %s", exc)
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        log.exception("pipeline error for file=%s", filename)
        raise HTTPException(status_code=500, detail="Pipeline error. Check server logs.")

    log.info("analyze complete: file=%s variants=%d", filename, len(results))
    return JSONResponse(content={"count": len(results), "results": results})
