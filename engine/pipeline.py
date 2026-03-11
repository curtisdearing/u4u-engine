"""
engine/pipeline.py
==================
Orchestrates the full variant analysis pipeline. Raw file bytes go in,
a sorted list of scored and summarized variant dicts comes out.

This is the function your workers call. It has zero knowledge of HTTP
servers, job queues, databases, or UI frameworks — those concerns belong
to the wrapper layer.

Pipeline steps
--------------
  1.  validate_file_bytes      — size, magic bytes, UTF-8 check
  2.  parse_file               — VCF / 23andMe / CSV / rsID list
  3.  apply_quality_filter     — drop hom-ref, failed calls, low GQ/DP, indels
  4.  filter_variants          — rsID whitelist (ACMG81, pharma, carrier…)
  5.  resolve_rsids             — Ensembl REST: rsid_only → coordinates
  6.  deduplicate               — key by (chrom, pos, ref, alt)
  7.  annotate_variant (loop)  — VEP + ClinVar + gnomAD + MyVariant fallback
  8.  score_variant  (loop)    — clinical score, tier, zygosity, carrier note
  9.  generate_summary (loop)  — plain-English consumer output
  10. sort by score descending

Public interface
----------------
    run_pipeline(
        file_bytes: bytes,
        filename: str,
        filters: list[str] = (),
        data_dir: str = "data",
        progress_callback: callable = None,
    ) -> list[dict]

    annotate_variant(v: dict) -> dict   — usable alone for cache-aware workers
"""

from .parsers      import parse_file
from .validators   import validate_file_bytes
from .quality_filter import apply_quality_filter, filter_stats
from .filters      import filter_variants
from .rsid_resolver import resolve_rsids
from .deduplicator import deduplicate
from .annotators.vep     import fetch_vep, select_canonical_consequence
from .annotators.clinvar import fetch_clinvar
from .annotators.gnomad  import fetch_gnomad
from .annotators.myvariant import fetch_myvariant
from .scoring  import score_variant
from .summary  import generate_summary


def run_pipeline(
    file_bytes: bytes,
    filename: str,
    filters: list = (),
    data_dir: str = "data",
    progress_callback=None,
) -> list[dict]:
    """
    Run the full variant analysis pipeline.

    Parameters
    ----------
    file_bytes : bytes
        Raw file content. Never written to disk by this function.
    filename : str
        Original filename — used for format detection and validation only.
    filters : list[str]
        rsID filter filenames to apply (e.g. ["acmg81_rsids.txt"]).
        Empty list = process all variants (use for VCF files).
    data_dir : str
        Path to the directory containing filter files.
    progress_callback : callable | None
        Optional function called as progress_callback(step: str, pct: int).

    Returns
    -------
    list[dict]
        Variants sorted by score descending. Each dict contains all
        annotation, scoring, and summary fields. See annotate_variant()
        and score_variant() for the full field list.
    """
    def _progress(step: str, pct: int):
        if progress_callback:
            progress_callback(step, pct)

    # ── Step 1: Validate ────────────────────────────────────────────────────
    _progress("Validating file", 2)
    validate_file_bytes(file_bytes, filename)

    # ── Step 2: Parse ───────────────────────────────────────────────────────
    _progress("Parsing file", 5)
    raw_variants = parse_file(file_bytes, filename)

    # ── Step 3: Quality filter ──────────────────────────────────────────────
    _progress("Applying quality filter", 8)
    quality_filtered = apply_quality_filter(raw_variants)
    stats = filter_stats(raw_variants, quality_filtered)
    if stats["removed_count"]:
        _progress(
            f"Quality filter: removed {stats['removed_count']} low-quality / "
            f"reference calls ({stats['removed_pct']}%)",
            10,
        )

    # ── Step 4: rsID whitelist filter ───────────────────────────────────────
    _progress("Applying gene panel filter", 12)
    panel_filtered = filter_variants(quality_filtered, list(filters), data_dir)

    # ── Step 5: Resolve rsid_only variants to coordinates ───────────────────
    rsid_only   = [(v["rsid"], v.get("genotype")) for v in panel_filtered
                   if v["variant_type"] == "rsid_only"]
    coord_vars  = [v for v in panel_filtered if v["variant_type"] == "coordinate"]

    if rsid_only:
        _progress(f"Resolving {len(rsid_only)} rsIDs via Ensembl", 15)

        def _resolve_progress(current, total):
            pct = 15 + int((current / max(total, 1)) * 10)
            _progress(f"Resolving rsIDs ({current}/{total})", pct)

        resolved = resolve_rsids(rsid_only, progress_callback=_resolve_progress)
        coord_vars.extend(resolved)

    # ── Step 6: Deduplicate ─────────────────────────────────────────────────
    _progress("Deduplicating variants", 26)
    unique_variants = deduplicate(coord_vars)

    # ── Steps 7–9: Annotate → Score → Summarize ─────────────────────────────
    total        = len(unique_variants)
    final_results = []

    for i, v in enumerate(unique_variants):
        pct  = 30 + int((i / max(total, 1)) * 60)
        name = v.get("rsid") or f"{v.get('chrom')}:{v.get('pos')}"
        _progress(f"Annotating {name} ({i+1}/{total})", pct)

        # Step 7: Annotate
        annotated = annotate_variant(v)

        # Step 8: Score
        scored = score_variant(annotated)

        # Step 9: Summarize
        summary = generate_summary(scored)

        # Merge summary fields into the result dict
        combined = dict(scored)
        combined.update({
            "emoji":             summary.emoji,
            "headline":          summary.headline,
            "consequence_plain": summary.consequence_plain,
            "rarity_plain":      summary.rarity_plain,
            "clinvar_plain":     summary.clinvar_plain,
            "action_hint":       summary.action_hint,
            "zygosity_plain":    summary.zygosity_plain,
            # carrier_note is already in scored — no need to duplicate
        })
        final_results.append(combined)

    # ── Step 10: Sort ────────────────────────────────────────────────────────
    final_results.sort(key=lambda x: x["score"], reverse=True)

    _progress("Complete", 100)
    return final_results


def annotate_variant(v: dict) -> dict:
    """
    Annotate a single coordinate variant using VEP, ClinVar, gnomAD, and
    MyVariant.info as a fallback.

    This function is exported directly for use in cache-aware workers:
        result = cache.get(key) or annotate_variant(v)

    Parameters
    ----------
    v : dict
        A coordinate variant dict (chrom, pos, ref, alt, rsid).

    Returns
    -------
    dict
        The input dict extended with:
        variant_id, location, consequence, genes,
        clinvar, disease_name, condition_key, gnomad_af, gnomad_popmax,
        gnomad_homozygote_count.

        condition_key is a stable lookup key for the associated condition:
            "OMIM:<id>"      — OMIM MIM number (preferred)
            "MedGen:<id>"    — NCBI MedGen concept ID
            "ClinVar:<uid>"  — ClinVar Variation UID (last resort)
            None             — no ClinVar record or lookup failed
    """
    chrom = v.get("chrom")
    pos   = v.get("pos")
    ref   = v.get("ref")
    alt   = v.get("alt")
    rsid  = v.get("rsid")

    result = dict(v)
    result["variant_id"] = rsid or f"{chrom}:{pos}"
    result["location"]   = f"{chrom}:{pos}"

    # ── VEP ──────────────────────────────────────────────────────────────────
    vep_data = fetch_vep(chrom, pos, ref, alt)
    if vep_data:
        consequence, genes = select_canonical_consequence(vep_data)
        result["consequence"] = consequence
        result["genes"]       = genes
        fallback_cv           = vep_data.get("_fallback_clinvar", {})
    else:
        result["consequence"] = "unknown"
        result["genes"]       = []
        fallback_cv           = {}

    # ── ClinVar (primary: NCBI eUtils; fallback: VEP colocated) ─────────────
    cv_data = fetch_clinvar(rsid) if rsid else None

    if cv_data and cv_data.get("clinical_significance"):
        result["clinvar"]        = cv_data["clinical_significance"]
        result["disease_name"]   = cv_data.get("disease_name")
        result["condition_key"]  = cv_data.get("condition_key")
    elif fallback_cv.get("clinical_significance"):
        result["clinvar"]        = fallback_cv["clinical_significance"]
        result["disease_name"]   = fallback_cv.get("disease_name")
        result["condition_key"]  = fallback_cv.get("condition_key")
    else:
        result["clinvar"]        = None
        result["disease_name"]   = None
        result["condition_key"]  = None

    # ── gnomAD (primary: GraphQL API) ────────────────────────────────────────
    gnomad_data = fetch_gnomad(chrom, pos, ref, alt)
    if gnomad_data:
        result["gnomad_af"]               = gnomad_data.get("af")
        result["gnomad_popmax"]           = gnomad_data.get("popmax_af")
        result["gnomad_homozygote_count"] = gnomad_data.get("homozygote_count")
    else:
        result["gnomad_af"]               = None
        result["gnomad_popmax"]           = None
        result["gnomad_homozygote_count"] = None

    # ── MyVariant.info fallback ───────────────────────────────────────────────
    # If we're still missing ClinVar or gnomAD data, try MyVariant.info
    missing_clinvar = not result.get("clinvar")
    missing_gnomad  = result.get("gnomad_af") is None

    if missing_clinvar or missing_gnomad:
        mv = fetch_myvariant(rsid=rsid, chrom=chrom, pos=pos, ref=ref, alt=alt)
        if mv:
            if missing_clinvar and mv.get("clinvar_classification"):
                result["clinvar"]       = mv["clinvar_classification"]
                result["disease_name"]  = mv.get("clinvar_condition")
                # Only overwrite condition_key from MyVariant if we don't
                # already have one from the primary ClinVar lookup.
                if not result.get("condition_key"):
                    result["condition_key"] = mv.get("condition_key")
            if missing_gnomad and mv.get("gnomad_af") is not None:
                result["gnomad_af"]    = mv["gnomad_af"]
                result["gnomad_popmax"] = mv.get("gnomad_popmax")

    return result
