"""
engine/annotators/gnomad.py
============================
Fetches population allele frequencies from the gnomAD GraphQL API.
Tries gnomAD r4 first; falls back to r2.1 for variants not yet in r4.

Public interface
----------------
    fetch_gnomad(chrom, pos, ref, alt) -> dict | None

Returns
-------
    {
        "af":               float | None,   — allele frequency (best source)
        "homozygote_count": int | None,
        "popmax_af":        float | None,   — highest AF across ancestry groups
        "source":           str,            — "genome" | "exome"
        "dataset":          str,            — "gnomad_r4" | "gnomad_r2_1"
    }
    None if the variant is absent from gnomAD entirely.
"""

import requests
from tenacity import (
    retry, stop_after_attempt, wait_exponential, retry_if_exception_type,
)
from ..validators import validate_coordinates


_GNOMAD_URL = "https://gnomad.broadinstitute.org/api/"
_TIMEOUT    = 10
_DATASETS   = ["gnomad_r4", "gnomad_r2_1"]  # try in order

_QUERY = """
query($variantId: String!, $datasetId: DatasetId!) {
  variant(variantId: $variantId, dataset: $datasetId) {
    genome {
      af
      ac
      an
      homozygote_count
      popmax { af }
    }
    exome {
      af
      ac
      an
      homozygote_count
      popmax { af }
    }
  }
}
"""


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((requests.Timeout, requests.ConnectionError)),
    reraise=False,
)
def fetch_gnomad(chrom: str, pos: int, ref: str, alt: str) -> dict | None:
    """
    Fetch population frequency data for a variant from gnomAD.

    Parameters
    ----------
    chrom : str   Chromosome (with or without "chr" prefix).
    pos   : int   1-based position.
    ref   : str   Reference allele.
    alt   : str   Alternate allele.

    Returns
    -------
    dict | None
        See module docstring for the returned dict shape.
        Returns None if the variant is not found in gnomAD after all retries.
    """
    try:
        validate_coordinates(chrom, pos, ref, alt)
    except ValueError:
        return None

    clean_chrom = str(chrom).replace("chr", "").replace("CHR", "")
    variant_id  = f"{clean_chrom}-{pos}-{ref}-{alt}"

    for dataset in _DATASETS:
        result = _query_gnomad(variant_id, dataset)
        if result is not None:
            result["dataset"] = dataset
            return result

    return None


def _query_gnomad(variant_id: str, dataset: str) -> dict | None:
    """Make one gnomAD GraphQL query for a specific dataset."""
    try:
        resp = requests.post(
            _GNOMAD_URL,
            json={"query": _QUERY, "variables": {"variantId": variant_id, "datasetId": dataset}},
            headers={"Content-Type": "application/json"},
            timeout=_TIMEOUT,
        )
        if resp.status_code != 200:
            return None

        variant_data = resp.json().get("data", {}).get("variant")
        if not variant_data:
            return None

        genome = variant_data.get("genome")
        exome  = variant_data.get("exome")

        # Prefer genome data when it has observed allele counts; otherwise exome.
        if genome and (genome.get("ac") or 0) > 0:
            src, src_name = genome, "genome"
        elif exome and (exome.get("ac") or 0) > 0:
            src, src_name = exome, "exome"
        elif genome and (genome.get("an") or 0) > 0:
            src, src_name = genome, "genome"
        else:
            return None

        return {
            "af":               src.get("af"),
            "homozygote_count": src.get("homozygote_count"),
            "popmax_af":        (src.get("popmax") or {}).get("af"),
            "source":           src_name,
        }

    except Exception:
        return None
