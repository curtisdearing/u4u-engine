"""
engine/quality_filter.py
========================
Genotype quality filter. Removes low-confidence and non-variant calls
before any API annotation occurs.

This is a pure-Python, zero-network step that runs immediately after
parsing. It protects downstream API calls from wasted work on noise.

Rules applied (in order)
-------------------------
1.  Skip homozygous_ref variants — the user carries the reference allele;
    there is no variant to annotate.
2.  Skip failed/indel genotype calls: --, NN, ., -, DI, II, DD, any
    genotype containing I or D (23andMe indel markers).
3.  Skip VCF calls with GQ < 20 (genotype quality score below threshold
    for reliable calling).
4.  Skip VCF calls with DP < 5 (fewer than 5 reads — unreliable).
5.  For VCF variants: skip indels (ref or alt longer than 1 base) —
    the engine currently scores SNPs only; indel handling is a future task.
6.  Skip anomalous 23andMe genotypes longer than 2 characters with no
    ref/alt (likely a formatting artifact).

Public interface
----------------
    apply_quality_filter(variants: list[dict]) -> list[dict]
    filter_stats(original: list[dict], filtered: list[dict]) -> dict
"""

_FAILED_GENOTYPE_STRINGS = frozenset(["--", "NN", ".", "-", "DI", "II", "DD"])

GQ_THRESHOLD = 20  # minimum VCF genotype quality score
DP_THRESHOLD = 5   # minimum VCF read depth


def apply_quality_filter(variants: list[dict]) -> list[dict]:
    """
    Remove low-quality and non-variant calls from a parsed variant list.

    Parameters
    ----------
    variants : list[dict]
        Output of parse_file(). Each dict must have the canonical keys
        (chrom, pos, ref, alt, rsid, variant_type, genotype, zygosity, gq, dp).

    Returns
    -------
    list[dict]
        Filtered variant list. Homozygous-reference and failed calls are removed.
        Order is preserved for retained variants.
    """
    clean = []
    for v in variants:
        if _should_drop(v):
            continue
        clean.append(v)
    return clean


def filter_stats(original: list[dict], filtered: list[dict]) -> dict:
    """
    Return a summary dict describing what was removed by the quality filter.
    Useful for logging and debugging.
    """
    removed = len(original) - len(filtered)
    return {
        "original_count": len(original),
        "filtered_count": len(filtered),
        "removed_count": removed,
        "removed_pct": round(removed / max(len(original), 1) * 100, 1),
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _should_drop(v: dict) -> bool:
    """Return True if the variant should be excluded from annotation."""

    # Rule 1: homozygous reference — not a variant
    if v.get("zygosity") == "homozygous_ref":
        return True

    genotype = (v.get("genotype") or "").strip()
    ref = v.get("ref")
    alt = v.get("alt")

    # Rule 2: failed / indel genotype strings
    if genotype:
        if genotype in _FAILED_GENOTYPE_STRINGS:
            return True
        if "I" in genotype or "D" in genotype:
            return True

    # Rule 3: VCF GQ threshold
    gq = v.get("gq")
    if gq is not None and gq < GQ_THRESHOLD:
        return True

    # Rule 4: VCF DP threshold
    dp = v.get("dp")
    if dp is not None and dp < DP_THRESHOLD:
        return True

    # Rule 5: VCF indels (ref or alt longer than 1 base)
    if ref and alt:
        if len(ref) != 1 or len(alt) != 1:
            return True

    # Rule 6: anomalous 23andMe genotype (no ref/alt, genotype > 2 chars)
    if not ref and not alt and genotype and len(genotype) > 2:
        return True

    return False
