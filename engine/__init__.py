"""
u4u-engine
==========
Standalone genomics variant analysis engine for the U4U platform.

Zero web framework dependencies. Wrap it with FastAPI, Celery, Django,
a CLI script, or a Jupyter notebook — it doesn't care.

Quick start
-----------
    from engine import run_pipeline

    with open("my_file.vcf", "rb") as f:
        results = run_pipeline(f.read(), "my_file.vcf")

    for r in results:
        print(r["tier"], r["headline"])

Accepted file formats
---------------------
    .vcf            — standard Variant Call Format (requires pysam)
    .vcf.gz         — gzipped VCF (requires pysam)
    .txt            — 23andMe raw data download, or one rsID per line
    .csv            — columns: chrom, pos, ref, alt, rsid (any subset)

Result dict fields (per variant)
---------------------------------
    Core identity
        variant_id        str       rsid or "chrom:pos"
        rsid              str|None  dbSNP rsID
        location          str       "chrom:pos"
        chrom             str       chromosome (no chr prefix)
        pos               int       1-based position
        ref               str       reference allele
        alt               str       alternate allele
        zygosity          str       "heterozygous"|"homozygous_alt"|"unknown"

    Annotation
        consequence       str       VEP most severe consequence (SO term)
        genes             list[str] affected gene symbol(s)
        clinvar           str|None  clinical significance (lowercased)
        clinvar_raw       str|None  original ClinVar value before heuristics
        disease_name      str|None  associated disease/condition (human-readable)
        condition_key     str|None  stable lookup key for the condition:
                                      "OMIM:<id>"     — OMIM MIM number (preferred)
                                      "MedGen:<id>"   — NCBI MedGen concept ID
                                      "ClinVar:<uid>" — ClinVar Variation UID
                                      None            — no ClinVar record found
        gnomad_af         float|None allele frequency (genome or exome)
        gnomad_popmax     float|None highest AF across ancestry groups
        gnomad_homozygote_count int|None

    Scoring
        score             int       clinical priority score
        tier              str       "critical"|"high"|"medium"|"low"
        reasons           list[str] human-readable scoring factors
        frequency_derived_label str|None  additive frequency context
        carrier_note      str|None  set for heterozygous recessive variants

    Consumer summary (plain English)
        emoji             str       🔴🟠🟡🟢🔵
        headline          str       one-sentence summary
        consequence_plain str       molecular impact in plain English
        rarity_plain      str       population frequency in plain English
        clinvar_plain     str       ClinVar classification in plain English
        action_hint       str       recommended next step
        zygosity_plain    str|None  plain-English zygosity statement

Public API
----------
Import ONLY from this file. Internal module structure may change.
"""

__version__ = "1.0.0"

# ── Primary entry point ──────────────────────────────────────────────────────
from .pipeline import run_pipeline, annotate_variant

# ── Individual pipeline steps ────────────────────────────────────────────────
from .parsers        import parse_file
from .validators     import validate_file_bytes, validate_rsid, validate_coordinates
from .quality_filter import apply_quality_filter, filter_stats
from .filters        import load_filter_set, filter_variants
from .rsid_resolver  import resolve_rsid, resolve_rsids
from .deduplicator   import deduplicate
from .scoring        import score_variant, Tier
from .summary        import generate_summary, ConsumerSummary

# ── Individual annotators ────────────────────────────────────────────────────
from .annotators.vep       import fetch_vep, select_canonical_consequence
from .annotators.clinvar   import fetch_clinvar
from .annotators.gnomad    import fetch_gnomad
from .annotators.myvariant import fetch_myvariant

__all__ = [
    # Pipeline
    "run_pipeline",
    "annotate_variant",
    # Parsers
    "parse_file",
    # Validators
    "validate_file_bytes",
    "validate_rsid",
    "validate_coordinates",
    # Quality filter
    "apply_quality_filter",
    "filter_stats",
    # Whitelist filters
    "load_filter_set",
    "filter_variants",
    # rsID resolution
    "resolve_rsid",
    "resolve_rsids",
    # Deduplication
    "deduplicate",
    # Scoring
    "score_variant",
    "Tier",
    # Summary
    "generate_summary",
    "ConsumerSummary",
    # Annotators
    "fetch_vep",
    "select_canonical_consequence",
    "fetch_clinvar",
    "fetch_gnomad",
    "fetch_myvariant",
]
