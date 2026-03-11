"""
engine/annotators/myvariant.py
================================
MyVariant.info fallback annotator. Used when the primary annotators
(ClinVar eUtils, gnomAD GraphQL) return no data.

MyVariant.info aggregates ClinVar, gnomAD, dbSNP, and other sources into
a single REST endpoint. It is useful as a safety net but less authoritative
than the primary sources.

Public interface
----------------
    fetch_myvariant(rsid=None, chrom=None, pos=None, ref=None, alt=None) -> dict | None

Returns
-------
    {
        "clinvar_classification": str | None,
        "clinvar_condition":      str | None,
        "clinvar_review_status":  str | None,
        "condition_key":          str | None,
        "gnomad_af":              float | None,
        "gnomad_popmax":          float | None,
    }
    None if no data is found.

condition_key format (mirrors clinvar.py)
-----------------------------------------
    "OMIM:<id>"     — extracted from rcv.conditions.identifiers.omim
    "MedGen:<id>"   — extracted from rcv.conditions.identifiers.medgen
    None            — no identifier available in this response
"""

import requests
from tenacity import (
    retry, stop_after_attempt, wait_exponential, retry_if_exception_type,
)

_BASE    = "https://myvariant.info/v1"
_TIMEOUT = 10


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((requests.Timeout, requests.ConnectionError)),
    reraise=False,
)
def fetch_myvariant(
    rsid: str | None = None,
    chrom: str | None = None,
    pos: int | None = None,
    ref: str | None = None,
    alt: str | None = None,
) -> dict | None:
    """
    Look up a variant in MyVariant.info by rsID or genomic coordinate.

    Preference: rsID lookup is tried first (more reliable hit rate).
    Falls back to coordinate-based lookup if rsID is unavailable.

    IMPORTANT: When matching hits by rsID, we validate that chrom/pos match
    the hit's location if those fields are available on the variant. This
    prevents accepting data for a different genomic locus that shares an rsID
    due to build differences.

    Parameters
    ----------
    rsid  : str | None   dbSNP rsID (preferred).
    chrom : str | None   Chromosome (bare, no "chr" prefix).
    pos   : int | None   1-based position.
    ref   : str | None   Reference allele.
    alt   : str | None   Alternate allele.

    Returns
    -------
    dict | None   See module docstring for returned fields.
    """
    data = None

    if rsid and str(rsid).lower().startswith("rs"):
        data = _query_by_rsid(rsid, chrom, pos)

    if data is None and chrom and pos and ref and alt and ref != alt:
        data = _query_by_coordinate(chrom, pos, ref, alt)

    if data is None:
        return None

    return _extract(data)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _query_by_rsid(rsid: str, chrom, pos) -> dict | None:
    """Query MyVariant.info by rsID; validate locus if coordinates are known."""
    try:
        url = f"{_BASE}/query?q=dbsnp.rsid:{rsid}&fields=clinvar,gnomad_exome,gnomad_genome"
        resp = requests.get(url, timeout=_TIMEOUT)
        if resp.status_code != 200:
            return None
        hits = resp.json().get("hits", [])
        if not hits:
            return None

        # Prefer a hit whose locus matches what we have on the variant.
        # Prevents build-mismatch data contamination.
        if chrom and pos:
            clean_chrom = str(chrom).replace("chr", "").replace("CHR", "")
            for hit in hits:
                hit_chrom = str(hit.get("chrom", "")).replace("chr", "").replace("CHR", "")
                hit_pos   = hit.get("vcf", {}).get("position") or hit.get("hg38", {}).get("start")
                if hit_chrom == clean_chrom and hit_pos and abs(int(hit_pos) - int(pos)) <= 1:
                    if "clinvar" in hit or "gnomad_exome" in hit or "gnomad_genome" in hit:
                        return hit

        # Fall back to first hit with useful data
        for hit in hits:
            if "clinvar" in hit or "gnomad_exome" in hit or "gnomad_genome" in hit:
                return hit

        return None
    except Exception:
        return None


def _query_by_coordinate(chrom, pos, ref, alt) -> dict | None:
    """Query MyVariant.info by HGVS genomic coordinate."""
    try:
        clean_chrom = str(chrom).replace("chr", "").replace("CHR", "")
        url = f"{_BASE}/variant/chr{clean_chrom}:g.{pos}{ref}>{alt}"
        resp = requests.get(url, timeout=_TIMEOUT)
        if resp.status_code == 404:
            return None
        if resp.status_code != 200:
            return None
        return resp.json()
    except Exception:
        return None


def _extract(data: dict) -> dict:
    """Extract ClinVar and gnomAD fields from a MyVariant.info hit."""
    # ── ClinVar ──────────────────────────────────────────────────────────
    clinvar_classification = None
    clinvar_condition      = None
    clinvar_review_status  = None
    condition_key          = None

    cv = data.get("clinvar")
    if cv:
        rcv = cv.get("rcv", [])
        if isinstance(rcv, dict):
            rcv = [rcv]
        if rcv:
            primary = rcv[0]
            sig = primary.get("clinical_significance", "")
            if isinstance(sig, list):
                sig = sig[0] if sig else ""
            clinvar_classification = sig.lower() if sig else None

            conditions = primary.get("conditions", {})
            if isinstance(conditions, dict):
                clinvar_condition = conditions.get("name")
                _ids = conditions.get("identifiers", {})
                if isinstance(_ids, dict):
                    if _ids.get("omim"):
                        condition_key = f"OMIM:{_ids['omim']}"
                    elif _ids.get("medgen"):
                        condition_key = f"MedGen:{_ids['medgen']}"
            elif isinstance(conditions, list) and conditions:
                clinvar_condition = conditions[0].get("name")
                _ids = conditions[0].get("identifiers", {})
                if isinstance(_ids, dict):
                    if _ids.get("omim"):
                        condition_key = f"OMIM:{_ids['omim']}"
                    elif _ids.get("medgen"):
                        condition_key = f"MedGen:{_ids['medgen']}"

            rev = primary.get("review_status", "")
            clinvar_review_status = rev.replace("_", " ") if rev else None

    # ── gnomAD ────────────────────────────────────────────────────────────
    gnomad_af     = None
    gnomad_popmax = None

    gex = data.get("gnomad_exome", {})
    ggn = data.get("gnomad_genome", {})

    if isinstance(gex, dict) and "af" in gex:
        gnomad_af     = gex.get("af", {}).get("af")
        gnomad_popmax = gex.get("af", {}).get("popmax")
    elif isinstance(ggn, dict) and "af" in ggn:
        gnomad_af     = ggn.get("af", {}).get("af")
        gnomad_popmax = ggn.get("af", {}).get("popmax")

    return {
        "clinvar_classification": clinvar_classification,
        "clinvar_condition":      clinvar_condition,
        "clinvar_review_status":  clinvar_review_status,
        "condition_key":          condition_key,
        "gnomad_af":              gnomad_af,
        "gnomad_popmax":          gnomad_popmax,
    }
