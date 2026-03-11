"""
engine/rsid_resolver.py
=======================
Resolves rsIDs to genomic coordinates using the Ensembl REST API.

Key improvement over the prior implementation: when a 23andMe genotype
string is available, the resolver uses it to select only the allele the
user actually carries — rather than returning all possible alt alleles
for that rsID. This eliminates phantom variants for alleles the user
does not have.

Public interface
----------------
    resolve_rsid(rsid: str, genotype: str | None = None) -> list[dict]
    resolve_rsids(rsids_and_genotypes: list[tuple], progress_callback=None) -> list[dict]

Each returned dict has the canonical variant shape from parsers.py:
    chrom, pos, ref, alt, rsid, variant_type="coordinate", genotype, zygosity
"""

import time
import requests
from tenacity import (
    retry, stop_after_attempt, wait_exponential, retry_if_exception_type,
)
from .validators import validate_rsid
from .parsers import _infer_zygosity_from_genotype


_ENSEMBL_BASE    = "https://rest.ensembl.org"
_REQUEST_TIMEOUT = 10  # seconds
_RATE_LIMIT_SLEEP = 0.07  # ~14 req/s — within Ensembl's unauthenticated limit


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((requests.Timeout, requests.ConnectionError)),
    reraise=False,
)
def resolve_rsid(rsid: str, genotype: str | None = None) -> list[dict]:
    """
    Convert a single rsID to coordinate variant dicts.

    Parameters
    ----------
    rsid     : str            A valid dbSNP rsID (e.g. "rs429358").
    genotype : str | None     23andMe genotype string (e.g. "TC" or "TT").
                              When provided, only alleles the user actually
                              carries are returned. Without it, all known
                              alt alleles for the rsID are returned.

    Returns
    -------
    list[dict]
        Zero or more coordinate variant dicts. Returns [] on failure.
    """
    try:
        validate_rsid(rsid)
    except ValueError:
        return []

    try:
        resp = requests.get(
            f"{_ENSEMBL_BASE}/variation/human/{rsid}",
            headers={"Content-Type": "application/json"},
            timeout=_REQUEST_TIMEOUT,
        )
        if resp.status_code != 200:
            return []

        data = resp.json()
        mappings = data.get("mappings", [])
        if not mappings:
            return []

        # Use the first (primary assembly) mapping only
        mapping = mappings[0]
        allele_string = mapping.get("allele_string", "")
        alleles = allele_string.split("/")
        if len(alleles) < 2:
            return []

        ref  = alleles[0].upper()
        chrom = str(mapping.get("seq_region_name", "")).replace("chr", "").replace("CHR", "")
        pos   = mapping.get("start")

        if genotype:
            # Genotype-aware: only return the alt alleles the user carries.
            # Find chars in the genotype string that differ from the reference.
            alt_candidates = list(dict.fromkeys(
                a.upper() for a in genotype if a.upper() != ref and a.upper() in "ACGT"
            ))

            if not alt_candidates:
                # All genotype chars match the reference → homozygous ref
                # Return nothing — this position is not a variant for this user.
                return []

            zygosity = _infer_zygosity_from_genotype(genotype, ref)
            return [
                {
                    "chrom":        chrom,
                    "pos":          pos,
                    "ref":          ref,
                    "alt":          alt,
                    "rsid":         rsid,
                    "variant_type": "coordinate",
                    "genotype":     genotype,
                    "zygosity":     zygosity,
                    "gq":           None,
                    "dp":           None,
                }
                for alt in alt_candidates
            ]

        else:
            # No genotype available — return all known alt alleles
            all_alts = [a.upper() for a in alleles[1:] if a.upper() in "ACGT"]
            return [
                {
                    "chrom":        chrom,
                    "pos":          pos,
                    "ref":          ref,
                    "alt":          alt,
                    "rsid":         rsid,
                    "variant_type": "coordinate",
                    "genotype":     None,
                    "zygosity":     "unknown",
                    "gq":           None,
                    "dp":           None,
                }
                for alt in all_alts
            ]

    except Exception:
        return []


def resolve_rsids(
    rsids_and_genotypes: list,
    progress_callback=None,
) -> list[dict]:
    """
    Resolve a list of rsIDs to coordinate variants.

    Parameters
    ----------
    rsids_and_genotypes : list
        Either a list of str rsIDs (no genotype context), or a list of
        (rsid, genotype) tuples for 23andMe-sourced variants.

    progress_callback : callable | None
        Optional function called as progress_callback(current: int, total: int).

    Returns
    -------
    list[dict]   All resolved coordinate variants (flattened, order preserved).
    """
    resolved: list[dict] = []
    total = len(rsids_and_genotypes)

    for i, item in enumerate(rsids_and_genotypes):
        if isinstance(item, tuple):
            rsid, genotype = item[0], item[1] if len(item) > 1 else None
        else:
            rsid, genotype = item, None

        variants = resolve_rsid(rsid, genotype)
        resolved.extend(variants)
        time.sleep(_RATE_LIMIT_SLEEP)

        if progress_callback:
            progress_callback(i + 1, total)

    return resolved
