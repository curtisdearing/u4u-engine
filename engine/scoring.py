"""
engine/scoring.py
=================
Scores and tiers an annotated variant based on clinical evidence.

Evidence sources — weighted in priority order
----------------------------------------------
  1. ClinVar classification  (highest — peer-reviewed clinical consensus)
  2. Functional consequence  (LoF > missense > synonymous)
  3. Population frequency    (rare variants score higher)
  4. Zygosity modifier       (carrier status for recessive genes)

Short-circuit rules
-------------------
  - ClinVar pathogenic  → score = 1000, tier = CRITICAL immediately
  - ClinVar benign      → score = 1,    tier = LOW immediately
    Nothing overrides these. They represent expert clinical consensus.

Tier thresholds
---------------
    CRITICAL  score ≥ 500
    HIGH      score ≥ 100
    MEDIUM    score ≥ 30
    LOW       score <  30

Frequency-derived label
-----------------------
When ClinVar classification is absent or VUS, a supplementary
`frequency_derived_label` field is added based on gnomAD AF.
This field is additive context — it NEVER overwrites the `clinvar`
field. The consumer can display both clearly differentiated.

Zygosity / carrier detection
-----------------------------
When a variant is heterozygous AND the condition is autosomal recessive
(detected from the disease name or ClinVar classification string), the
score is reduced by 50% and a `carrier_note` is set. This prevents carrier
variants from appearing at the top of the results list incorrectly.

Public interface
----------------
    score_variant(annotated: dict) -> dict
"""

from enum import Enum


class Tier(str, Enum):
    CRITICAL = "critical"
    HIGH     = "high"
    MEDIUM   = "medium"
    LOW      = "low"


# Consequence severity groups (Ensembl VEP SO terms)
HIGH_IMPACT = frozenset({
    "stop_gained", "frameshift_variant", "splice_donor_variant",
    "splice_acceptor_variant", "start_lost", "stop_lost",
    "transcript_ablation", "transcript_amplification",
})
MODERATE_IMPACT = frozenset({
    "missense_variant", "inframe_deletion", "inframe_insertion",
    "protein_altering_variant",
})
LOW_IMPACT = frozenset({
    "synonymous_variant", "intron_variant", "intergenic_variant",
    "upstream_gene_variant", "downstream_gene_variant",
    "3_prime_UTR_variant", "5_prime_UTR_variant",
})

# Keywords in disease names / ClinVar text that indicate autosomal recessive
_RECESSIVE_KEYWORDS = frozenset({
    "autosomal recessive", "recessive", "homozygous", "biallelic",
})


def score_variant(annotated: dict) -> dict:
    """
    Compute a clinical priority score and assign a tier.

    Parameters
    ----------
    annotated : dict
        Output of annotate_variant() from pipeline.py. Must contain:
        consequence, genes, clinvar, disease_name, gnomad_af, zygosity.

    Returns
    -------
    dict
        Input dict extended with:
            score                  : int
            tier                   : str ("critical"|"high"|"medium"|"low")
            reasons                : list[str]  — human-readable scoring factors
            clinvar_raw            : str | None — original ClinVar classification
            frequency_derived_label: str | None — additive frequency context
            carrier_note           : str | None — set for heterozygous recessive variants
    """
    result = dict(annotated)
    score   = 0
    reasons = []

    clinvar      = (annotated.get("clinvar") or "").lower()
    gnomad_af    = annotated.get("gnomad_af")
    consequence  = annotated.get("consequence", "unknown")
    genes        = annotated.get("genes", [])
    zygosity     = annotated.get("zygosity") or "unknown"
    disease_name = (annotated.get("disease_name") or "").lower()

    # Preserve the raw ClinVar value so the presentation layer can show both
    result["clinvar_raw"] = annotated.get("clinvar")

    # ── 1. ClinVar short-circuits ────────────────────────────────────────────
    if "pathogenic" in clinvar and "likely" not in clinvar:
        score += 1000
        reasons.append("⚠️ ClinVar: PATHOGENIC")
        result.update({
            "score": score, "tier": Tier.CRITICAL.value,
            "reasons": reasons,
            "frequency_derived_label": None,
            "carrier_note": None,
        })
        return result

    if "benign" in clinvar and "likely" not in clinvar:
        score = 1
        reasons.append("✅ ClinVar: Benign")
        result.update({
            "score": score, "tier": Tier.LOW.value,
            "reasons": reasons,
            "frequency_derived_label": None,
            "carrier_note": None,
        })
        return result

    # ── 1b. Non-short-circuit ClinVar classifications ────────────────────────
    if "likely pathogenic" in clinvar:
        score += 500
        reasons.append("⚠️ ClinVar: Likely Pathogenic")
    elif "likely benign" in clinvar:
        score = 5
        reasons.append("✅ ClinVar: Likely Benign")
    elif "uncertain" in clinvar or "vus" in clinvar:
        score += 50
        reasons.append("❓ ClinVar: VUS (uncertain significance)")

    # ── 2. Functional consequence ─────────────────────────────────────────────
    if consequence in HIGH_IMPACT:
        score += 100
        reasons.append(f"High-impact consequence: {consequence}")
    elif consequence in MODERATE_IMPACT:
        score += 50
        reasons.append(f"Moderate-impact consequence: {consequence}")
    elif consequence in LOW_IMPACT:
        score += 5
        reasons.append(f"Low-impact consequence: {consequence}")
    else:
        score += 1
        reasons.append(f"Consequence: {consequence} (unclassified)")

    # ── 3. Population frequency ───────────────────────────────────────────────
    if gnomad_af is None:
        reasons.append("No gnomAD frequency data")
    elif gnomad_af == 0:
        score += 30
        reasons.append("Absent in gnomAD (AF = 0)")
    elif gnomad_af < 0.0001:
        score += 20
        reasons.append(f"Ultra-rare in gnomAD (AF = {gnomad_af:.2e})")
    elif gnomad_af < 0.001:
        score += 10
        reasons.append(f"Very rare in gnomAD (AF = {gnomad_af:.4f})")
    elif gnomad_af < 0.01:
        score += 5
        reasons.append(f"Rare in gnomAD (AF = {gnomad_af:.3f})")
    else:
        score -= 20
        reasons.append(f"Common variant in gnomAD (AF = {gnomad_af:.1%})")

    # ── 4. Gene presence ─────────────────────────────────────────────────────
    if genes:
        reasons.append(f"Gene(s): {', '.join(sorted(genes))}")
    else:
        score -= 10
        reasons.append("Intergenic (no gene annotation)")

    # ── 5. Frequency-derived label (additive — never overwrites ClinVar) ──────
    frequency_derived_label = None
    no_clinvar = not clinvar or clinvar in ("", "uncertain significance", "vus")
    if no_clinvar or "uncertain" in clinvar or "vus" in clinvar:
        if gnomad_af is not None:
            if gnomad_af >= 0.05:
                frequency_derived_label = "Likely benign (common in population)"
            elif gnomad_af < 0.0001:
                frequency_derived_label = "Uncertain significance (ultra-rare variant)"

    # ── 6. Zygosity / carrier detection ──────────────────────────────────────
    carrier_note = None
    is_recessive = _is_recessive_context(clinvar, disease_name)

    if zygosity == "heterozygous" and is_recessive:
        score = int(score * 0.5)
        carrier_note = (
            "Carrier finding — this gene is associated with a recessive condition. "
            "Carrying one copy typically does not cause the condition but may be "
            "relevant for family planning."
        )
        reasons.append("Zygosity: heterozygous in recessive gene (score halved)")
    elif zygosity == "homozygous_alt":
        reasons.append("Zygosity: homozygous alternate (two copies)")
    elif zygosity == "heterozygous":
        reasons.append("Zygosity: heterozygous (one copy)")

    # ── Tier assignment ───────────────────────────────────────────────────────
    if score >= 500:
        tier = Tier.CRITICAL
    elif score >= 100:
        tier = Tier.HIGH
    elif score >= 30:
        tier = Tier.MEDIUM
    else:
        tier = Tier.LOW

    result.update({
        "score":                   score,
        "tier":                    tier.value,
        "reasons":                 reasons,
        "frequency_derived_label": frequency_derived_label,
        "carrier_note":            carrier_note,
    })
    return result


def _is_recessive_context(clinvar: str, disease_name: str) -> bool:
    """Return True if either the ClinVar text or disease name suggest autosomal recessive."""
    combined = f"{clinvar} {disease_name}".lower()
    return any(kw in combined for kw in _RECESSIVE_KEYWORDS)
