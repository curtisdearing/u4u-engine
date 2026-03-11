"""
engine/filters.py
=================
Loads rsID whitelists (ACMG81, pharmacogenomics, carrier, traits) from
the data/ directory and applies them to reduce a variant list to a
clinically relevant subset before annotation.

No Streamlit dependencies. Results are cached in memory per process so
repeated calls within a worker don't re-read the file from disk.

Public interface
----------------
    load_filter_set(filename: str, data_dir: str = "data") -> frozenset[str]
    filter_variants(variants, selected_filters, data_dir="data") -> list[dict]

Available filter files
----------------------
    acmg81_rsids.txt        — ACMG SF v3.2 actionable genes (pathogenic)
    pharma_rsids.txt        — Pharmacogenomics genes (CYP2C19, CYP2D6, etc.)
    carrier_rsids.txt       — Carrier screening genes
    health_traits_rsids.txt — Health trait associations
    all_clinvar_rsids.txt.gz — All ClinVar rsIDs (large — use sparingly)
"""

import gzip
import os
from functools import lru_cache


@lru_cache(maxsize=16)
def load_filter_set(filename: str, data_dir: str = "data") -> frozenset:
    """
    Load a set of rsIDs from a plain-text or gzipped file.

    Results are LRU-cached in memory so repeated calls within the same
    process do not re-read the file from disk.

    Parameters
    ----------
    filename : str   Filename within data_dir (e.g. "acmg81_rsids.txt").
    data_dir : str   Path to the directory containing filter files.

    Returns
    -------
    frozenset[str]
        Set of rsIDs. Returns an empty frozenset if the file does not exist.
    """
    filepath = os.path.join(data_dir, filename)
    if not os.path.exists(filepath):
        return frozenset()

    rsids: set[str] = set()
    open_fn = gzip.open if filename.endswith(".gz") else open

    try:
        with open_fn(filepath, "rt", encoding="utf-8") as f:
            for line in f:
                rsid = line.strip()
                if rsid:
                    rsids.add(rsid)
    except Exception as e:
        print(f"[filters] Warning: could not load {filename}: {e}")

    return frozenset(rsids)


def filter_variants(
    variants: list[dict],
    selected_filters: list[str],
    data_dir: str = "data",
) -> list[dict]:
    """
    Keep only variants whose rsID appears in at least one selected filter set.

    If no filters are selected, all variants are returned unchanged.

    Parameters
    ----------
    variants         : list[dict]   Parsed variants from parse_file().
    selected_filters : list[str]    Filter filenames to apply (empty = no filter).
    data_dir         : str          Directory containing filter files.

    Returns
    -------
    list[dict]   Filtered variant list (order preserved).
    """
    if not selected_filters:
        return variants

    allowed: set[str] = set()
    for fname in selected_filters:
        allowed.update(load_filter_set(fname, data_dir))

    return [v for v in variants if v.get("rsid") in allowed]
