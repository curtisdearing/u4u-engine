"""
engine/deduplicator.py
======================
Removes duplicate variants before annotation.

Why this step exists
--------------------
After rsID resolution, the same genomic position can appear more than once:
  1. A 23andMe file contains rsid + coordinates; Ensembl resolution returns
     those same coordinates again → two entries for one position.
  2. The same rsID appears in multiple filter sets and is resolved twice.
  3. A VCF multi-allelic site can be split into multiple alt alleles that
     share the same position and ref.

Without deduplication the same variant gets annotated, scored, and displayed
twice. This was the most visible quality problem in the Streamlit prototype.

Public interface
----------------
    deduplicate(variants: list[dict]) -> list[dict]
"""


def deduplicate(variants: list[dict]) -> list[dict]:
    """
    Remove variants that share the same genomic position and alleles.

    Deduplication key: (chrom, pos, ref, alt) — all normalized.

    Tie-breaking: when two variants share a key, the entry with an rsID is
    preferred over the one without. If both have rsIDs, the first is kept.

    Parameters
    ----------
    variants : list[dict]   Coordinate variants (chrom/pos/ref/alt all present).

    Returns
    -------
    list[dict]   Unique variants. Input order is preserved for kept entries.
    """
    seen: dict[tuple, dict] = {}

    for v in variants:
        chrom = str(v.get("chrom") or "").replace("chr", "").replace("CHR", "").upper()
        pos   = v.get("pos")
        ref   = str(v.get("ref") or "").upper()
        alt   = str(v.get("alt") or "").upper()

        # Can't key variants missing any coordinate field
        if not (pos and ref and alt):
            continue

        key = (chrom, pos, ref, alt)

        if key not in seen:
            seen[key] = v
        elif v.get("rsid") and not seen[key].get("rsid"):
            # Upgrade to the entry that has an rsID (richer for ClinVar lookup)
            seen[key] = v

    return list(seen.values())
