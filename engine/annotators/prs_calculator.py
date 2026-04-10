"""
engine/annotators/prs_calculator.py
====================================
Calculates Polygenic Risk Scores (PRS) for complex traits relevant to
peptide therapy response. Entirely offline — uses published consortia
beta coefficients hardcoded from peer-reviewed GWAS meta-analyses.

Supported traits:
  1. Insulin Resistance  (IRS-PRS)
  2. Autoimmune Thyroiditis  (AIT-PRS)
  3. Systemic Inflammation / CRP  (INF-PRS)

Each trait has a curated set of rsIDs with effect alleles and beta
coefficients from published studies. The PRS is computed as:
    PRS = sum(beta_i * dosage_i) for all rsIDs present in patient data
where dosage = 0 (no risk allele), 1 (heterozygous), or 2 (homozygous).

The raw PRS is normalized to a 0-1 scale using reference population
parameters (mean and SD from European-ancestry GWAS).

Public interface
----------------
    calculate_prs(variants: list[dict], ancestry: str) -> dict
    calculate_single_trait_prs(trait: str, variants: list[dict], ancestry: str) -> dict
    get_inflammatory_baseline(prs_profile: dict) -> str
"""

from __future__ import annotations

from typing import Optional

# ═══════════════════════════════════════════════════════════════════════════════
# PRS VARIANT DATABASES
# ═══════════════════════════════════════════════════════════════════════════════
# Beta coefficients from published GWAS meta-analyses.
# Format: rsID -> {effect_allele, beta, gene, source}

PRS_VARIANTS: dict[str, dict] = {
    # ── INSULIN RESISTANCE (IRS-PRS) ──────────────────────────────────────
    "insulin_resistance": {
        "trait_name": "Insulin Resistance",
        "abbreviation": "IRS-PRS",
        "variants": {
            "rs7903146": {"effect_allele": "T", "beta": 0.30, "gene": "TCF7L2", "source": "DIAGRAM 2022"},
            "rs1801282": {"effect_allele": "G", "beta": 0.15, "gene": "PPARG", "source": "MAGIC 2021"},
            "rs560887":  {"effect_allele": "C", "beta": 0.12, "gene": "G6PC2", "source": "MAGIC 2021"},
            "rs780094":  {"effect_allele": "C", "beta": 0.10, "gene": "GCKR", "source": "MAGIC 2021"},
            "rs13266634":{"effect_allele": "A", "beta": 0.12, "gene": "SLC30A8", "source": "DIAGRAM 2022"},
            "rs7754840": {"effect_allele": "G", "beta": 0.08, "gene": "CDKAL1", "source": "DIAGRAM 2022"},
            "rs10830963":{"effect_allele": "G", "beta": 0.09, "gene": "MTNR1B", "source": "MAGIC 2021"},
            "rs1387153": {"effect_allele": "G", "beta": 0.07, "gene": "MTNR1B", "source": "MAGIC 2021"},
            "rs4506565": {"effect_allele": "T", "beta": 0.14, "gene": "TCF7L2", "source": "DIAGRAM 2022"},
            "rs9939609": {"effect_allele": "A", "beta": 0.11, "gene": "FTO", "source": "GIANT 2023"},
            "rs1111875": {"effect_allele": "C", "beta": 0.09, "gene": "HHEX", "source": "DIAGRAM 2022"},
            "rs5219":    {"effect_allele": "T", "beta": 0.07, "gene": "KCNJ11", "source": "DIAGRAM 2022"},
        },
        # Reference population parameters (European ancestry GWAS)
        "population_mean": 0.65,
        "population_sd": 0.35,
        # Ancestry adjustment factors (multiply raw PRS by factor)
        "ancestry_adjustments": {
            "African": 0.85,
            "Caucasian": 1.00,
            "Hispanic": 0.95,
            "Asian": 1.05,
            "Unknown": 1.00,
        },
    },

    # ── AUTOIMMUNE THYROIDITIS (AIT-PRS) ──────────────────────────────────
    "autoimmune_thyroiditis": {
        "trait_name": "Autoimmune Thyroiditis",
        "abbreviation": "AIT-PRS",
        "variants": {
            "rs3184504": {"effect_allele": "A", "beta": 0.22, "gene": "SH2B3", "source": "ThyroidOmics 2022"},
            "rs2476601": {"effect_allele": "A", "beta": 0.35, "gene": "PTPN22", "source": "ThyroidOmics 2022"},
            "rs1800693": {"effect_allele": "A", "beta": 0.15, "gene": "TNFRSF1A", "source": "ThyroidOmics 2022"},
            "rs12720356":{"effect_allele": "G", "beta": 0.18, "gene": "TYK2", "source": "ThyroidOmics 2022"},
            "rs2340475": {"effect_allele": "G", "beta": 0.12, "gene": "FOXE1", "source": "ThyroidOmics 2022"},
            "rs1678542": {"effect_allele": "A", "beta": 0.10, "gene": "LPP", "source": "ThyroidOmics 2022"},
            "rs231775":  {"effect_allele": "G", "beta": 0.20, "gene": "CTLA4", "source": "Graves/Hashimoto GWAS 2021"},
            "rs3087243": {"effect_allele": "A", "beta": 0.16, "gene": "CTLA4", "source": "Graves/Hashimoto GWAS 2021"},
        },
        "population_mean": 0.45,
        "population_sd": 0.30,
        "ancestry_adjustments": {
            "African": 0.75,
            "Caucasian": 1.00,
            "Hispanic": 0.90,
            "Asian": 0.80,
            "Unknown": 1.00,
        },
    },

    # ── SYSTEMIC INFLAMMATION / CRP (INF-PRS) ────────────────────────────
    "systemic_inflammation": {
        "trait_name": "Systemic Inflammation",
        "abbreviation": "INF-PRS",
        "variants": {
            "rs2794520": {"effect_allele": "C", "beta": 0.25, "gene": "CRP", "source": "CHARGE Inflammation 2022"},
            "rs1205":    {"effect_allele": "C", "beta": 0.22, "gene": "CRP", "source": "CHARGE Inflammation 2022"},
            "rs1800795": {"effect_allele": "G", "beta": 0.18, "gene": "IL6", "source": "CHARGE Inflammation 2022"},
            "rs1799724": {"effect_allele": "A", "beta": 0.15, "gene": "TNF", "source": "CHARGE Inflammation 2022"},
            "rs16944":   {"effect_allele": "A", "beta": 0.12, "gene": "IL1B", "source": "CHARGE Inflammation 2022"},
            "rs1333049": {"effect_allele": "G", "beta": 0.10, "gene": "CDKN2B-AS1", "source": "CARDIoGRAM 2021"},
            "rs3091244": {"effect_allele": "A", "beta": 0.14, "gene": "CRP", "source": "CHARGE Inflammation 2022"},
            "rs4420638": {"effect_allele": "G", "beta": 0.16, "gene": "APOC1", "source": "CHARGE Inflammation 2022"},
            "rs4129267": {"effect_allele": "T", "beta": 0.20, "gene": "IL6R", "source": "CHARGE Inflammation 2022"},
            "rs6734238": {"effect_allele": "G", "beta": 0.11, "gene": "IL1F10", "source": "CHARGE Inflammation 2022"},
        },
        "population_mean": 0.55,
        "population_sd": 0.32,
        "ancestry_adjustments": {
            "African": 1.10,
            "Caucasian": 1.00,
            "Hispanic": 1.05,
            "Asian": 0.90,
            "Unknown": 1.00,
        },
    },
}

# ═══════════════════════════════════════════════════════════════════════════════
# RISK CATEGORIES
# ═══════════════════════════════════════════════════════════════════════════════

_RISK_THRESHOLDS = {
    "HIGH": 0.70,      # >= 70th percentile
    "MODERATE": 0.40,  # >= 40th percentile
    "LOW": 0.0,        # < 40th percentile
}


def _percentile_to_category(percentile: float) -> str:
    """Convert normalized percentile (0-1) to risk category."""
    if percentile >= _RISK_THRESHOLDS["HIGH"]:
        return "HIGH"
    elif percentile >= _RISK_THRESHOLDS["MODERATE"]:
        return "MODERATE"
    return "LOW"


# ═══════════════════════════════════════════════════════════════════════════════
# CORE PRS CALCULATION
# ═══════════════════════════════════════════════════════════════════════════════

def _extract_rsid(variant: dict) -> str:
    """Extract clean rsID from variant dict."""
    rsid = variant.get("rsid", "")
    if not rsid:
        return ""
    # Handle rsID_allele format (e.g., "rs2228480_C")
    return rsid.split("_")[0].lower().strip()


def _get_dosage(variant: dict) -> int:
    """
    Get allele dosage from variant zygosity.
    HOM = 2 copies of alt allele, HET = 1 copy.
    """
    zygosity = variant.get("zygosity", "").upper()
    if zygosity in ("HOM", "HOMOZYGOUS", "1/1"):
        return 2
    elif zygosity in ("HET", "HETEROZYGOUS", "0/1", "1/0"):
        return 1
    # Default: assume heterozygous if zygosity unknown but variant present
    return 1


def _normalize_prs(
    raw_score: float,
    pop_mean: float,
    pop_sd: float,
) -> float:
    """
    Normalize raw PRS to 0-1 scale using population z-score → CDF.
    Uses a simple sigmoid approximation of the normal CDF.
    """
    if pop_sd <= 0:
        return 0.5

    z = (raw_score - pop_mean) / pop_sd

    # Logistic approximation of normal CDF: 1 / (1 + exp(-1.7 * z))
    import math
    try:
        cdf = 1.0 / (1.0 + math.exp(-1.7 * z))
    except OverflowError:
        cdf = 0.0 if z < 0 else 1.0

    return round(min(max(cdf, 0.0), 1.0), 4)


def calculate_single_trait_prs(
    trait: str,
    variants: list[dict],
    ancestry: str = "Unknown",
) -> Optional[dict]:
    """
    Calculate PRS for a single trait.

    Parameters
    ----------
    trait : str
        Trait key: 'insulin_resistance', 'autoimmune_thyroiditis', or 'systemic_inflammation'.
    variants : list[dict]
        Patient variant dicts with 'rsid' and 'zygosity' fields.
    ancestry : str
        Patient ancestry for population adjustment.

    Returns
    -------
    dict or None
        Trait PRS result, or None if trait not found.
    """
    trait_key = trait.lower().strip().replace(" ", "_")
    trait_data = PRS_VARIANTS.get(trait_key)
    if not trait_data:
        return None

    # Build rsID lookup from patient variants
    patient_rsids: dict[str, dict] = {}
    for v in variants:
        rsid = _extract_rsid(v)
        if rsid:
            patient_rsids[rsid] = v

    # Calculate raw PRS
    raw_score = 0.0
    variants_contributing = []
    total_possible = 0.0

    for rsid, info in trait_data["variants"].items():
        rsid_lower = rsid.lower()
        total_possible += info["beta"] * 2  # max contribution = beta * 2 (homozygous)

        if rsid_lower in patient_rsids:
            dosage = _get_dosage(patient_rsids[rsid_lower])
            contribution = info["beta"] * dosage
            raw_score += contribution
            variants_contributing.append({
                "rsid": rsid,
                "gene": info["gene"],
                "dosage": dosage,
                "beta": info["beta"],
                "contribution": round(contribution, 4),
            })

    # Apply ancestry adjustment
    adj_factor = trait_data["ancestry_adjustments"].get(ancestry, 1.0)
    adjusted_score = raw_score * adj_factor

    # Normalize to 0-1 percentile
    normalized = _normalize_prs(
        adjusted_score,
        trait_data["population_mean"],
        trait_data["population_sd"],
    )

    # Convert to percentile (0-100)
    percentile = round(normalized * 100, 1)
    risk_category = _percentile_to_category(normalized)

    # Top contributing variants (sorted by contribution descending)
    variants_contributing.sort(key=lambda x: x["contribution"], reverse=True)
    top_variants = [
        f"{v['rsid']} ({v['gene']}, +{v['contribution']:.2f} risk)"
        for v in variants_contributing[:5]
    ]

    return {
        "trait": trait_data["trait_name"],
        "abbreviation": trait_data["abbreviation"],
        "prs_score": round(normalized, 4),
        "risk_percentile": percentile,
        "risk_category": risk_category,
        "raw_score": round(raw_score, 4),
        "adjusted_score": round(adjusted_score, 4),
        "ancestry_adjustment": adj_factor,
        "variants_found": len(variants_contributing),
        "variants_total": len(trait_data["variants"]),
        "top_variants": top_variants,
        "all_contributing_variants": variants_contributing,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_prs(
    variants: list[dict],
    ancestry: str = "Unknown",
) -> dict:
    """
    Calculate all PRS traits for a patient.

    Parameters
    ----------
    variants : list[dict]
        Annotated variant dicts from pipeline. Must have 'rsid' field.
    ancestry : str
        Patient ancestry for adjustment: African, Caucasian, Hispanic, Asian, Unknown.

    Returns
    -------
    dict
        Complete PRS profile with all trait scores and inflammatory baseline.
    """
    trait_results = {}
    for trait_key in PRS_VARIANTS:
        result = calculate_single_trait_prs(trait_key, variants, ancestry)
        if result:
            trait_results[trait_key] = result

    # Compute inflammatory baseline reactivity
    inflammatory_baseline = get_inflammatory_baseline(trait_results)

    # Generate clinical summary
    clinical_summary = _generate_prs_summary(trait_results, inflammatory_baseline)

    return {
        "trait_scores": trait_results,
        "inflammatory_cytokine_baseline": inflammatory_baseline,
        "clinical_summary": clinical_summary,
        "ancestry_used": ancestry,
        "traits_calculated": len(trait_results),
    }


def get_inflammatory_baseline(prs_results: dict) -> str:
    """
    Determine baseline immune system reactivity from inflammation PRS.

    A high PRS for inflammatory cytokines indicates a highly reactive
    baseline immune system — important for peptide therapy response
    and autoimmune risk assessment.

    Parameters
    ----------
    prs_results : dict
        Dict of trait_key -> trait result from calculate_prs.

    Returns
    -------
    str
        'LOW', 'MODERATE', or 'HIGH'
    """
    inf_result = prs_results.get("systemic_inflammation")
    if not inf_result:
        return "MODERATE"  # Default if no inflammation data

    score = inf_result.get("prs_score", 0.5)
    if score >= 0.70:
        return "HIGH"
    elif score >= 0.40:
        return "MODERATE"
    return "LOW"


def _generate_prs_summary(
    trait_results: dict,
    inflammatory_baseline: str,
) -> str:
    """Generate clinical narrative from all PRS results."""
    if not trait_results:
        return "No polygenic risk score data available for this patient."

    parts = []
    high_traits = [
        t for t in trait_results.values() if t["risk_category"] == "HIGH"
    ]
    moderate_traits = [
        t for t in trait_results.values() if t["risk_category"] == "MODERATE"
    ]

    if high_traits:
        names = ", ".join(f"{t['trait']} ({t['risk_percentile']}th percentile)" for t in high_traits)
        parts.append(f"Elevated polygenic risk detected for: {names}.")

    if moderate_traits:
        names = ", ".join(t["trait"] for t in moderate_traits)
        parts.append(f"Moderate polygenic risk for: {names}.")

    if not high_traits and not moderate_traits:
        parts.append("All polygenic risk scores are within normal range.")

    # Inflammatory baseline context
    if inflammatory_baseline == "HIGH":
        parts.append(
            "Baseline immune reactivity is HIGH — this patient's genetics predict "
            "elevated inflammatory cytokine production. Consider baseline CRP, IL-6, "
            "TNF-alpha labs before peptide therapy. Anti-inflammatory co-therapy "
            "(omega-3, curcumin, low-glycemic diet) may be warranted."
        )
    elif inflammatory_baseline == "MODERATE":
        parts.append(
            "Baseline immune reactivity is MODERATE. Standard inflammatory monitoring "
            "is appropriate."
        )

    return " ".join(parts)
