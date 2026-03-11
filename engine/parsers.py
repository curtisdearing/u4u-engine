"""
engine/parsers.py
=================
Variant file parsers. Supports VCF, 23andMe raw data, plain rsID lists,
and generic CSV files. No web framework dependencies.

Public interface
----------------
    parse_file(file_bytes: bytes, filename: str) -> list[dict]

Each returned dict has keys
---------------------------
    chrom        : str | None   — chromosome, no "chr" prefix (e.g. "1", "X")
    pos          : int | None   — 1-based genomic position
    ref          : str | None   — reference allele (uppercase)
    alt          : str | None   — alternate allele (uppercase)
    rsid         : str | None   — dbSNP rsID (e.g. "rs429358")
    variant_type : str          — "coordinate" | "rsid_only"
    genotype     : str | None   — raw genotype string from 23andMe (e.g. "TC")
    zygosity     : str | None   — "heterozygous" | "homozygous_alt" |
                                   "homozygous_ref" | "unknown"
    gq           : int | None   — genotype quality (VCF only)
    dp           : int | None   — read depth (VCF only)

Notes
-----
- Variants where zygosity == "homozygous_ref" are flagged and will be
  dropped by the quality filter — they are the wildtype, not variants.
- 23andMe files have no ref/alt; those are resolved later via Ensembl.
- VCF files with multi-sample genotypes use the first sample column (index 0).
"""

import csv
import io

try:
    import pysam
    _PYSAM_AVAILABLE = True
except ImportError:
    _PYSAM_AVAILABLE = False


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def parse_file(file_bytes: bytes, filename: str) -> list[dict]:
    """
    Auto-detect file format and return a list of raw variant dicts.

    Parameters
    ----------
    file_bytes : bytes    Raw file content (from disk, S3, or upload).
    filename   : str      Original filename, used only for extension detection.

    Returns
    -------
    list[dict]  Each dict has the canonical keys described in the module docstring.

    Raises
    ------
    ValueError  If the file format is unsupported or the file is unreadable.
    """
    name = filename.lower()
    if name.endswith(".vcf") or name.endswith(".vcf.gz"):
        return _parse_vcf_bytes(file_bytes, filename)
    elif name.endswith(".txt"):
        text = file_bytes.decode("utf-8", errors="replace")
        if _is_23andme_text(text):
            return _parse_23andme_text(text)
        return _parse_rsid_text(text)
    elif name.endswith(".csv"):
        return _parse_csv_bytes(file_bytes)
    else:
        raise ValueError(
            f"Unsupported file format: {filename!r}. "
            "Accepted formats: .vcf, .vcf.gz, .txt, .csv"
        )


# ---------------------------------------------------------------------------
# Canonical variant dict builder
# ---------------------------------------------------------------------------

def _make_variant(
    chrom=None, pos=None, ref=None, alt=None,
    rsid=None, variant_type="coordinate",
    genotype=None, zygosity=None, gq=None, dp=None,
) -> dict:
    """Return a canonical variant dict with all expected keys."""
    # Normalize chromosome — strip "chr" prefix so the entire engine
    # always works with bare chromosome names ("1" not "chr1").
    if chrom:
        chrom = str(chrom).replace("chr", "").replace("CHR", "").strip()
    return {
        "chrom":        chrom,
        "pos":          int(pos) if pos is not None else None,
        "ref":          ref.upper() if ref else None,
        "alt":          alt.upper() if alt else None,
        "rsid":         rsid,
        "variant_type": variant_type,
        "genotype":     genotype,
        "zygosity":     zygosity,
        "gq":           gq,
        "dp":           dp,
    }


# ---------------------------------------------------------------------------
# VCF parser
# ---------------------------------------------------------------------------

def _parse_vcf_bytes(file_bytes: bytes, filename: str) -> list[dict]:
    """Parse a VCF file using pysam. Extracts zygosity, GQ, and DP."""
    if not _PYSAM_AVAILABLE:
        raise ImportError(
            "pysam is required to parse VCF files. "
            "Install it with: pip install pysam  (Linux/Mac only)"
        )
    import tempfile, os
    suffix = ".vcf.gz" if filename.lower().endswith(".gz") else ".vcf"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name
    try:
        vcf = pysam.VariantFile(tmp_path)
        variants = []
        for record in vcf.fetch():
            for alt in (record.alts or []):
                zygosity, gq, dp = _extract_vcf_sample_fields(record)
                variants.append(_make_variant(
                    chrom=record.chrom,
                    pos=record.pos,
                    ref=record.ref,
                    alt=alt,
                    rsid=record.id if record.id and record.id != "." else None,
                    variant_type="coordinate",
                    gq=gq,
                    dp=dp,
                    zygosity=zygosity,
                ))
        return variants
    finally:
        os.unlink(tmp_path)


def _extract_vcf_sample_fields(record) -> tuple:
    """
    Extract zygosity, GQ, and DP from the first sample column of a VCF record.
    Returns (zygosity, gq, dp) — all may be None if the fields are absent.
    """
    zygosity = "unknown"
    gq = None
    dp = None

    try:
        samples = list(record.samples.values())
        if not samples:
            return zygosity, gq, dp

        sample = samples[0]

        # Genotype
        gt = sample.get("GT")
        if gt is not None:
            # pysam returns GT as a tuple of allele indices, e.g. (0, 1) or (1, 1)
            alleles = [a for a in gt if a is not None]
            if len(alleles) >= 2:
                if all(a == 0 for a in alleles):
                    zygosity = "homozygous_ref"
                elif len(set(alleles)) == 1:
                    zygosity = "homozygous_alt"
                else:
                    zygosity = "heterozygous"
            elif len(alleles) == 1:
                zygosity = "homozygous_alt" if alleles[0] != 0 else "homozygous_ref"

        # Genotype quality
        try:
            gq = int(sample["GQ"])
        except (KeyError, TypeError, ValueError):
            pass

        # Read depth
        try:
            dp = int(sample["DP"])
        except (KeyError, TypeError, ValueError):
            pass

    except Exception:
        pass

    return zygosity, gq, dp


# ---------------------------------------------------------------------------
# 23andMe parser
# ---------------------------------------------------------------------------

def _is_23andme_text(text: str) -> bool:
    """
    Return True if the text looks like a 23andMe raw-data file.

    23andMe format:
        # rsid  chromosome  position  genotype
        rs548049170  1  69869  TT
    """
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.lower().startswith("# rsid"):
            return True
        if stripped.startswith("#"):
            continue
        parts = stripped.split("\t")
        if len(parts) >= 4 and parts[0].lower().startswith("rs"):
            return True
        return False
    return False


def _infer_zygosity_from_genotype(genotype: str, ref: str | None = None) -> str:
    """
    Infer zygosity from a 23andMe genotype string.

    Without a known reference allele:
      "TT" → homozygous_alt (two identical chars)
      "TC" → heterozygous   (two different chars)

    With a known reference allele:
      "TT" where ref="T" → homozygous_ref
      "TT" where ref="C" → homozygous_alt
      "TC" where ref="T" → heterozygous

    Returns "unknown" for any unrecognised pattern.
    """
    if not genotype or len(genotype) < 2:
        return "unknown"
    if len(genotype) == 2:
        a, b = genotype[0], genotype[1]
        if a == b:
            if ref and a == ref.upper():
                return "homozygous_ref"
            return "homozygous_alt"
        return "heterozygous"
    return "unknown"


def _parse_23andme_text(text: str) -> list[dict]:
    """
    Parse a 23andMe raw data text file.

    Returns rsid_only variants — ref/alt are resolved later via Ensembl.
    Includes genotype string and inferred zygosity.
    """
    variants = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split("\t")
        if len(parts) < 4:
            continue
        rsid, chrom, pos_str, genotype = parts[0], parts[1], parts[2], parts[3]
        if not rsid.lower().startswith("rs"):
            continue  # skip internal 23andMe IDs like "i7001348"

        # Quality pre-filter: skip failed calls
        if _is_failed_genotype(genotype):
            continue

        zygosity = _infer_zygosity_from_genotype(genotype)

        variants.append(_make_variant(
            chrom=chrom,
            pos=int(pos_str) if pos_str.isdigit() else None,
            rsid=rsid,
            genotype=genotype,
            zygosity=zygosity,
            variant_type="rsid_only",
        ))
    return variants


def _is_failed_genotype(genotype: str) -> bool:
    """Return True if the genotype string represents a failed or indel call."""
    g = (genotype or "").strip()
    if not g:
        return True
    if g in ("--", "NN", ".", "-", "DI", "II", "DD"):
        return True
    if "I" in g or "D" in g:
        return True
    if len(g) > 2:
        return True
    return False


# ---------------------------------------------------------------------------
# Plain rsID list parser
# ---------------------------------------------------------------------------

def _parse_rsid_text(text: str) -> list[dict]:
    """Parse a plain-text file with one rsID per line."""
    variants = []
    for line in text.splitlines():
        rsid = line.strip()
        if rsid and rsid.lower().startswith("rs"):
            variants.append(_make_variant(rsid=rsid, variant_type="rsid_only"))
    return variants


# ---------------------------------------------------------------------------
# CSV parser
# ---------------------------------------------------------------------------

def _parse_csv_bytes(file_bytes: bytes) -> list[dict]:
    """
    Parse a CSV file with optional columns: chrom, pos, ref, alt, rsid.

    A row is treated as "coordinate" if both chrom and pos are present,
    otherwise as "rsid_only".
    """
    text = file_bytes.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    variants = []
    for row in reader:
        chrom   = row.get("chrom") or row.get("chromosome")
        pos_raw = row.get("pos")   or row.get("position")
        ref     = row.get("ref")   or row.get("reference")
        alt     = row.get("alt")   or row.get("alternate")
        rsid    = row.get("rsid")  or row.get("rs_id")
        variant_type = "coordinate" if (chrom and pos_raw) else "rsid_only"
        variants.append(_make_variant(
            chrom=chrom,
            pos=int(pos_raw) if pos_raw and str(pos_raw).isdigit() else None,
            ref=ref,
            alt=alt,
            rsid=rsid,
            variant_type=variant_type,
        ))
    return variants
