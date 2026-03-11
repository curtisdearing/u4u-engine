"""
engine/annotators/clinvar.py
============================
Fetches clinical significance, disease name, and a stable condition
lookup key from NCBI ClinVar using the eUtils esearch + esummary
two-step API.

Set NCBI_API_KEY environment variable to increase rate limits from
3 requests/sec (unauthenticated) to 10 requests/sec.

Public interface
----------------
    fetch_clinvar(rsid: str) -> dict | None

Returns
-------
    {
        "clinical_significance": str | None,
        "disease_name":          str | None,
        "condition_key":         str | None,
    }
    None if no ClinVar record exists for this rsID.

condition_key format
--------------------
    "OMIM:<id>"       — preferred; MIM number from trait cross-references
    "MedGen:<id>"     — NCBI MedGen concept ID (fallback)
    "ClinVar:<uid>"   — ClinVar Variation UID (last resort when no xref exists)
    None              — no record or lookup failed
"""

import os
import time
import requests
from tenacity import (
    retry, stop_after_attempt, wait_exponential, retry_if_exception_type,
)
from ..validators import validate_rsid


_NCBI_API_KEY = os.environ.get("NCBI_API_KEY", "")
_EUTILS_BASE  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
_TIMEOUT      = 10
# Respect NCBI rate limits: 3 req/s without key, 10 req/s with key
_SLEEP = 0.1 if _NCBI_API_KEY else 0.35


def fetch_clinvar(rsid: str) -> dict | None:
    """
    Look up clinical significance, associated disease, and stable
    condition lookup key for an rsID.

    Parameters
    ----------
    rsid : str   A valid dbSNP rsID (must start with "rs").

    Returns
    -------
    dict | None
        {
            "clinical_significance": str | None,
            "disease_name":          str | None,
            "condition_key":         str | None,
        }
        Returns None if no ClinVar record is found or rsID is invalid.
    """
    try:
        validate_rsid(rsid)
    except ValueError:
        return None

    uid = _search_clinvar_uid(rsid)
    if not uid:
        return None
    return _fetch_clinvar_summary(uid)


# ---------------------------------------------------------------------------
# Internal helpers — each wrapped with tenacity retry
# ---------------------------------------------------------------------------

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((requests.Timeout, requests.ConnectionError)),
    reraise=False,
)
def _search_clinvar_uid(rsid: str) -> str | None:
    """Search ClinVar for the UID associated with an rsID."""
    time.sleep(_SLEEP)
    params: dict = {"db": "clinvar", "term": f"{rsid}[rs]", "retmode": "json"}
    if _NCBI_API_KEY:
        params["api_key"] = _NCBI_API_KEY
    try:
        resp = requests.get(f"{_EUTILS_BASE}/esearch.fcgi", params=params, timeout=_TIMEOUT)
        uids = resp.json().get("esearchresult", {}).get("idlist", [])
        return uids[0] if uids else None
    except Exception:
        return None


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((requests.Timeout, requests.ConnectionError)),
    reraise=False,
)
def _fetch_clinvar_summary(uid: str) -> dict | None:
    """Fetch the ClinVar esummary for a known UID."""
    time.sleep(_SLEEP)
    params: dict = {"db": "clinvar", "id": uid, "retmode": "json"}
    if _NCBI_API_KEY:
        params["api_key"] = _NCBI_API_KEY
    try:
        resp = requests.get(f"{_EUTILS_BASE}/esummary.fcgi", params=params, timeout=_TIMEOUT)
        doc  = resp.json().get("result", {}).get(uid, {})

        # ClinVar has changed its schema several times.
        # Try all known field paths for clinical significance.
        sig = (
            doc.get("clinical_significance", {}).get("description")
            or doc.get("germline_classification", {}).get("description")
            or doc.get("clinical_impact_classification", {}).get("description")
            or ""
        )

        # Disease name — first entry in trait_set
        disease = None
        for trait in doc.get("trait_set", []):
            if trait.get("trait_name"):
                disease = trait["trait_name"]
                break

        # condition_key — stable lookup key for the associated condition.
        # Priority: OMIM MIM number → NCBI MedGen concept ID → ClinVar UID.
        # Extracted from trait_set[].trait_xrefs cross-reference list; the
        # same trait that has a name is preferred but any trait with an OMIM
        # xref wins over a MedGen xref from a different trait.
        condition_key = None
        _medgen_fallback = None
        for trait in doc.get("trait_set", []):
            for xref in trait.get("trait_xrefs", []):
                db      = xref.get("db", "").upper()
                xref_id = str(xref.get("id", "")).strip()
                if not xref_id:
                    continue
                if db == "OMIM":
                    condition_key = f"OMIM:{xref_id}"
                    break          # OMIM is the preferred key; stop searching
                if db in ("MEDGEN", "MEDGEN_CONCEPT") and not _medgen_fallback:
                    _medgen_fallback = f"MedGen:{xref_id}"
            if condition_key:
                break              # found OMIM — no need to look at other traits

        if not condition_key:
            condition_key = _medgen_fallback or (f"ClinVar:{uid}" if uid else None)

        return {
            "clinical_significance": sig.lower() if sig else None,
            "disease_name":          disease,
            "condition_key":         condition_key,
        }
    except Exception:
        return None
