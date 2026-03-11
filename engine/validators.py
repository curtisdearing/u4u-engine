"""
engine/validators.py
====================
Input validation for all data entering the engine.
All external data — file bytes, rsIDs, coordinates — must pass through
here before any parsing or API call occurs.

Raises ValueError with a user-friendly message on any invalid input.

Public interface
----------------
    validate_file_bytes(data: bytes, filename: str) -> None
    validate_rsid(rsid: str) -> str
    validate_coordinates(chrom, pos, ref, alt) -> None
"""

import re

_RSID_RE  = re.compile(r"^rs\d+$", re.IGNORECASE)
_CHROM_RE = re.compile(r"^(chr)?([1-9]|1[0-9]|2[0-2]|X|Y|MT|M)$", re.IGNORECASE)
_ALLELE_RE = re.compile(r"^[ACGT]+$", re.IGNORECASE)

MAX_FILE_BYTES = 100 * 1024 * 1024  # 100 MB


def validate_file_bytes(data: bytes, filename: str) -> None:
    """
    Validate uploaded file content before any parsing occurs.

    Checks
    ------
    - File is not empty
    - File size ≤ 100 MB
    - VCF files have the required ##fileformat=VCF header
    - Text/CSV files are valid UTF-8

    Raises ValueError with a clear, user-facing message on failure.
    """
    if not data:
        raise ValueError("The uploaded file is empty.")

    if len(data) > MAX_FILE_BYTES:
        mb = len(data) / (1024 * 1024)
        raise ValueError(
            f"File is {mb:.1f} MB. Maximum allowed size is 100 MB. "
            "For whole-genome VCFs please contact support."
        )

    name = filename.lower()

    if name.endswith(".vcf"):
        header = data[:200].decode("utf-8", errors="ignore")
        if not header.startswith("##fileformat=VCF"):
            raise ValueError(
                "File does not appear to be a valid VCF. "
                "VCF files must begin with '##fileformat=VCF'."
            )

    if name.endswith(".txt") or name.endswith(".csv"):
        try:
            data[:4096].decode("utf-8")
        except UnicodeDecodeError:
            raise ValueError(
                "File does not appear to be valid UTF-8 text. "
                "Please save your file as UTF-8 and try again."
            )


def validate_rsid(rsid: str) -> str:
    """
    Validate that a string is a well-formed dbSNP rsID.

    Returns the rsid unchanged if valid.
    Raises ValueError otherwise.
    """
    if not rsid or not _RSID_RE.match(rsid):
        raise ValueError(
            f"Invalid rsID {rsid!r}. "
            "Expected format: 'rs' followed by digits (e.g. 'rs429358')."
        )
    return rsid


def validate_coordinates(chrom, pos, ref, alt) -> None:
    """
    Validate genomic coordinates before passing to external APIs.

    Raises ValueError with a clear message on any invalid field.
    """
    chrom_str = str(chrom or "").strip()
    if not _CHROM_RE.match(chrom_str):
        raise ValueError(
            f"Invalid chromosome {chrom_str!r}. "
            "Expected 1–22, X, Y, MT (with or without 'chr' prefix)."
        )
    if pos is None or not isinstance(pos, int) or pos <= 0:
        raise ValueError(f"Invalid position {pos!r}. Must be a positive integer.")
    if not ref or not _ALLELE_RE.match(str(ref)):
        raise ValueError(f"Invalid reference allele {ref!r}. Must contain only A, C, G, T.")
    if not alt or not _ALLELE_RE.match(str(alt)):
        raise ValueError(f"Invalid alternate allele {alt!r}. Must contain only A, C, G, T.")
