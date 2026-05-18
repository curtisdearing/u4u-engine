"""
engine/annotators/bpc157_predictor.py
=====================================
Predicts BPC-157 (Body Protection Compound-157) response likelihood
based on patient variant data. Entirely offline — no API calls required.

BPC-157 is a synthetic 15-amino-acid peptide derived from human gastric
juice studied in preclinical models for regenerative, cytoprotective,
anti-inflammatory, and angiogenic effects. It is NOT FDA-approved.

This module maps patient variants to BPC-157-relevant pathways and
generates a speculative responder profile based on mechanism-of-action
extrapolations from preclinical data. All outputs carry prominent
disclaimers.

Pathways covered (from Grok Plan)
---------------------------------
  - NO/eNOS signaling
  - VEGF/angiogenesis (VEGFR2)
  - Inflammatory cytokines (NF-κB, IL-6, TNF-α)
  - Growth hormone / IGF-1 axis
  - Collagen / tissue repair
  - Antioxidant / HO-1 induction
  - Gut barrier integrity
  - Dopamine / serotonin modulation

Public interface
----------------
    filter_bpc157_relevant(variants: list[dict]) -> list[dict]
    predict_bpc157_response(variants: list[dict]) -> dict
    generate_bpc157_summary(prediction: dict) -> str
"""

from __future__ import annotations

from typing import Optional


# ═══════════════════════════════════════════════════════════════════════════════
# DISCLAIMER — always included in output
# ═══════════════════════════════════════════════════════════════════════════════

_DISCLAIMER = (
    "BPC-157 is NOT FDA-approved for any medical use. All predictions are "
    "speculative extrapolations from preclinical (mostly rodent) data and "
    "mechanism-of-action reasoning. No validated human biomarkers or genetic "
    "predictors exist. Human data are extremely limited (small retrospective "
    "series only, no large RCTs). This is NOT medical advice. Consult a "
    "qualified physician experienced in peptide or regenerative medicine. "
    "Potential risks include unknown long-term effects, theoretical "
    "angiogenesis concerns in cancer, sourcing/quality issues, and "
    "legal/regulatory problems."
)


# ═══════════════════════════════════════════════════════════════════════════════
# BPC-157–RELEVANT PATHWAY → GENE MAPPINGS
# ═══════════════════════════════════════════════════════════════════════════════

BPC157_PATHWAY_GENES: dict[str, dict] = {
    "NO_eNOS_signaling": {
        "display_name": "NO / eNOS Signaling",
        "genes": {"NOS3", "NOS2"},
        "relevance": (
            "BPC-157 upregulates eNOS expression and NO production, "
            "central to its cytoprotective and vasoprotective effects."
        ),
        "use_cases": ["musculoskeletal", "gastrointestinal", "anti_inflammatory"],
    },
    "VEGF_angiogenesis": {
        "display_name": "VEGF / Angiogenesis (VEGFR2)",
        "genes": {"VEGFA", "KDR", "FLT1"},
        "relevance": (
            "BPC-157 enhances angiogenesis via VEGFR2 upregulation, "
            "promoting tissue healing and perfusion."
        ),
        "use_cases": ["musculoskeletal", "general"],
    },
    "inflammatory_cytokines": {
        "display_name": "Inflammatory Cytokines (NF-κB / IL-6 / TNF-α)",
        "genes": {"IL6", "TNF", "CRP", "IL1B", "NFKB1"},
        "relevance": (
            "BPC-157 attenuates pro-inflammatory cytokines and NF-κB; "
            "shifts M1→M2 macrophage polarization."
        ),
        "use_cases": ["anti_inflammatory", "musculoskeletal", "gastrointestinal"],
    },
    "growth_hormone_IGF": {
        "display_name": "Growth Hormone / IGF-1 Axis",
        "genes": {"GHR", "IGF1", "GH1"},
        "relevance": (
            "BPC-157 upregulates growth hormone receptors in tendon "
            "fibroblasts, enhancing collagen deposition and repair."
        ),
        "use_cases": ["musculoskeletal"],
    },
    "collagen_tissue_repair": {
        "display_name": "Collagen / Tissue Repair",
        "genes": {"COL1A1", "COL3A1", "MMP2", "MMP9"},
        "relevance": (
            "BPC-157 enhances collagen organization, fibroblast activity, "
            "and biomechanical strength of healing tissues."
        ),
        "use_cases": ["musculoskeletal", "general"],
    },
    "antioxidant_HO1": {
        "display_name": "Antioxidant / HO-1 Induction",
        "genes": {"HMOX1", "SOD2", "GPX1"},
        "relevance": (
            "BPC-157 induces heme oxygenase-1 (HO-1) and reduces "
            "lipid peroxidation / oxidative stress markers."
        ),
        "use_cases": ["anti_inflammatory", "general"],
    },
    "gut_barrier": {
        "display_name": "Gut Barrier Integrity",
        "genes": {"TJP1", "OCLN", "CDH1"},
        "relevance": (
            "BPC-157 stabilizes tight junctions, reduces intestinal "
            "permeability, and protects gastric/intestinal mucosa."
        ),
        "use_cases": ["gastrointestinal"],
    },
    "dopamine_serotonin": {
        "display_name": "Dopamine / Serotonin Modulation",
        "genes": {"DRD2", "HTR2A", "SLC6A4", "COMT"},
        "relevance": (
            "BPC-157 modulates dopamine and serotonin systems with "
            "potential neuroprotective and mood-regulating effects."
        ),
        "use_cases": ["general"],
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# rsID → MODIFIER EFFECTS FOR BPC-157 PATHWAY GENES
# ═══════════════════════════════════════════════════════════════════════════════
# Speculative associations based on known functional polymorphisms in
# BPC-157–relevant pathway genes. These are NOT validated BPC-157 predictors.

BPC157_MODIFIER_RSIDS: dict[str, dict] = {
    # NO/eNOS — rs1799983 (Glu298Asp in NOS3, reduced NO production)
    "rs1799983": {
        "gene": "NOS3",
        "pathway": "NO_eNOS_signaling",
        "direction": "impaired",
        "effect": "Glu298Asp — reduced eNOS activity; may benefit more from BPC-157 NO rescue",
        "predictor_weight": 1.5,
    },
    # VEGF — rs2010963 (VEGF +405 G>C, affects VEGF expression)
    "rs2010963": {
        "gene": "VEGFA",
        "pathway": "VEGF_angiogenesis",
        "direction": "impaired",
        "effect": "Reduced VEGF expression; BPC-157's VEGFR2 upregulation may compensate",
        "predictor_weight": 1.0,
    },
    # Inflammation — rs1800795 (IL-6 -174G>C)
    "rs1800795": {
        "gene": "IL6",
        "pathway": "inflammatory_cytokines",
        "direction": "elevated",
        "effect": "Higher baseline IL-6 expression; BPC-157 anti-inflammatory effect may be stronger",
        "predictor_weight": 1.5,
    },
    # TNF — rs1800629 (TNF-α -308G>A, higher TNF-α production)
    "rs1800629": {
        "gene": "TNF",
        "pathway": "inflammatory_cytokines",
        "direction": "elevated",
        "effect": "Higher TNF-α production; stronger anti-inflammatory signal expected with BPC-157",
        "predictor_weight": 1.5,
    },
    # Collagen — rs1800012 (COL1A1 Sp1 binding site; affects collagen production)
    "rs1800012": {
        "gene": "COL1A1",
        "pathway": "collagen_tissue_repair",
        "direction": "impaired",
        "effect": "Altered collagen I production; BPC-157 may boost compensatory repair",
        "predictor_weight": 1.0,
    },
    # GHR — rs6180 (GHR exon 10 polymorphism)
    "rs6180": {
        "gene": "GHR",
        "pathway": "growth_hormone_IGF",
        "direction": "variable",
        "effect": "GHR variant affecting receptor sensitivity; BPC-157 GHR upregulation may interact",
        "predictor_weight": 0.5,
    },
    # Antioxidant — rs2071746 (HMOX1 promoter GT repeat length tag)
    "rs2071746": {
        "gene": "HMOX1",
        "pathway": "antioxidant_HO1",
        "direction": "impaired",
        "effect": "Reduced HO-1 inducibility; may benefit from BPC-157 antioxidant rescue",
        "predictor_weight": 1.0,
    },
    # COMT — rs4680 (Val158Met — affects dopamine metabolism)
    "rs4680": {
        "gene": "COMT",
        "pathway": "dopamine_serotonin",
        "direction": "variable",
        "effect": "Val/Met switch affects dopamine catabolism; BPC-157 DA modulation may vary",
        "predictor_weight": 0.5,
    },
    # Serotonin transporter — rs25531 (SLC6A4 promoter, affects 5-HTT expression)
    "rs25531": {
        "gene": "SLC6A4",
        "pathway": "dopamine_serotonin",
        "direction": "variable",
        "effect": "Serotonin transporter expression variant; BPC-157 serotonergic effects may vary",
        "predictor_weight": 0.5,
    },
    # MMP9 — rs3918242 (MMP-9 -1562C>T promoter, affects matrix remodeling)
    "rs3918242": {
        "gene": "MMP9",
        "pathway": "collagen_tissue_repair",
        "direction": "elevated",
        "effect": "Higher MMP-9 expression; accelerated matrix remodeling may synergize with BPC-157",
        "predictor_weight": 1.0,
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# PRE-BUILT LOOKUP SETS — computed once at module load for fast filtering
# ═══════════════════════════════════════════════════════════════════════════════

_BPC157_ALL_GENES: frozenset[str] = frozenset(
    gene
    for pathway in BPC157_PATHWAY_GENES.values()
    for gene in pathway["genes"]
)

_BPC157_ALL_RSIDS: frozenset[str] = frozenset(BPC157_MODIFIER_RSIDS.keys())


# ═══════════════════════════════════════════════════════════════════════════════
# BIOMARKER RECOMMENDATIONS (from Grok Plan)
# ═══════════════════════════════════════════════════════════════════════════════

_BIOMARKER_PANELS: dict[str, list[dict]] = {
    "core_inflammatory": [
        {"name": "hs-CRP", "expected_change": "decrease", "category": "Inflammatory"},
        {"name": "IL-6 (serum)", "expected_change": "decrease", "category": "Inflammatory"},
        {"name": "TNF-α (serum)", "expected_change": "decrease", "category": "Inflammatory"},
    ],
    "gut_specific": [
        {"name": "Fecal calprotectin", "expected_change": "decrease", "category": "GI"},
        {"name": "Serum zonulin", "expected_change": "decrease", "category": "GI"},
    ],
    "tissue_repair": [
        {"name": "PIIINP (Procollagen III)", "expected_change": "increase", "category": "MSK"},
        {"name": "PINP (Procollagen I)", "expected_change": "increase", "category": "MSK"},
    ],
    "angiogenesis": [
        {"name": "Serum VEGF", "expected_change": "increase (modest)", "category": "Vascular"},
    ],
    "oxidative_stress": [
        {"name": "MDA (Malondialdehyde)", "expected_change": "decrease", "category": "Oxidative"},
        {"name": "Total antioxidant capacity", "expected_change": "increase", "category": "Oxidative"},
    ],
    "hormonal": [
        {"name": "IGF-1", "expected_change": "possible increase", "category": "Hormonal"},
    ],
    "safety": [
        {"name": "CBC with platelets", "expected_change": "monitor", "category": "Safety"},
        {"name": "CMP (liver/kidney)", "expected_change": "monitor", "category": "Safety"},
        {"name": "Coagulation studies", "expected_change": "monitor (if indicated)", "category": "Safety"},
    ],
}


# ═══════════════════════════════════════════════════════════════════════════════
# USE-CASE DISPLAY METADATA
# ═══════════════════════════════════════════════════════════════════════════════

_USE_CASE_META = {
    "musculoskeletal": {
        "display": "Musculoskeletal / Soft-Tissue Healing",
        "description": (
            "Tendon/ligament injuries, muscle tears, joint pain, "
            "post-surgical recovery. Strongest preclinical support."
        ),
    },
    "gastrointestinal": {
        "display": "Gastrointestinal Repair & Cytoprotection",
        "description": (
            "Leaky gut, NSAID-induced damage, ulcers, IBD symptoms. "
            "Strong preclinical evidence for mucosal healing."
        ),
    },
    "anti_inflammatory": {
        "display": "Anti-Inflammatory / Recovery",
        "description": (
            "Chronic low-grade inflammation, athletic recovery, "
            "wound healing, organ protection."
        ),
    },
    "general": {
        "display": "General / Emerging",
        "description": (
            "Neuroprotection, mood modulation, or conditions without "
            "a primary specific use-case match."
        ),
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# RESPONDER TIER LOGIC
# ═══════════════════════════════════════════════════════════════════════════════

_TIER_THRESHOLDS = {
    "likely_good": 3.0,
    "possible": 1.5,
    "uncertain": 0.5,
    # below uncertain → "low_confidence"
}


def _assign_responder_tier(score: float) -> str:
    if score >= _TIER_THRESHOLDS["likely_good"]:
        return "likely_good"
    elif score >= _TIER_THRESHOLDS["possible"]:
        return "possible"
    elif score >= _TIER_THRESHOLDS["uncertain"]:
        return "uncertain"
    return "low_confidence"


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════════

def filter_bpc157_relevant(variants: list[dict]) -> list[dict]:
    """
    Filter variants to only those relevant to BPC-157 prediction.

    A variant is relevant if ANY of its genes appear in a BPC-157 pathway
    OR its rsID is a known BPC-157 modifier. This should be called BEFORE
    running the full prediction to avoid processing irrelevant loci.

    Parameters
    ----------
    variants : list[dict]
        Raw or annotated variant dicts. Each should have 'genes' (list[str]
        or str) and optionally 'rsid' (str).

    Returns
    -------
    list[dict]
        Subset of input variants that are relevant to BPC-157 pathways.
    """
    relevant: list[dict] = []

    for v in variants:
        # Check genes
        genes = v.get("genes", [])
        if isinstance(genes, str):
            genes = [genes]
        gene_match = any(g.upper().strip() in _BPC157_ALL_GENES for g in genes)

        # Check rsID
        rsid = v.get("rsid") or ""
        if rsid:
            rsid_clean = rsid.split("_")[0] if "_" in rsid else rsid
            rsid_match = rsid_clean in _BPC157_ALL_RSIDS
        else:
            rsid_match = False

        if gene_match or rsid_match:
            relevant.append(v)

    return relevant


def predict_bpc157_response(variants: list[dict]) -> dict:
    """
    Predict BPC-157 response likelihood from patient variant data.

    Step 1: Filters input to only BPC-157-relevant variants (by gene/rsID).
    Step 2: Analyzes pathway overlap and rsID modifier effects.
    Step 3: Scores and assigns a responder tier.

    Parameters
    ----------
    variants : list[dict]
        Annotated variant dicts from the pipeline. Each must have at least
        'genes' (list[str]) and optionally 'rsid' (str), 'consequence' (str).

    Returns
    -------
    dict
        Prediction result with keys:
          responder_tier       : str — "likely_good"|"possible"|"uncertain"|"low_confidence"
          composite_score      : float — raw prediction score
          pathways_affected    : list[dict] — pathway details with genes hit
          primary_use_case     : str — most likely use-case match
          primary_use_case_display : str — human-readable use-case name
          biomarker_recommendations : list[dict] — recommended lab tests
          candidate_factors    : list[dict] — matched predictor factors
          relevant_variant_count : int — number of variants that passed the filter
          total_variant_count    : int — total variants received before filtering
          summary_text         : str — plain-English narrative
          disclaimer           : str — standard warning
    """
    # ── Step 1: Filter to BPC-157-relevant variants only ──────────────────────
    total_count = len(variants)
    relevant_variants = filter_bpc157_relevant(variants)

    # ── Step 2: Collect genes and rsIDs from relevant variants only ────────────
    patient_genes: set[str] = set()
    patient_rsids: set[str] = set()
    gene_consequences: dict[str, list[str]] = {}

    for v in relevant_variants:
        genes = v.get("genes", [])
        if isinstance(genes, str):
            genes = [genes]
        rsid = v.get("rsid") or ""
        consequence = v.get("consequence", "unknown")

        for g in genes:
            g_upper = g.upper().strip()
            patient_genes.add(g_upper)
            if g_upper not in gene_consequences:
                gene_consequences[g_upper] = []
            gene_consequences[g_upper].append(consequence)

        if rsid:
            rsid_clean = rsid.split("_")[0] if "_" in rsid else rsid
            patient_rsids.add(rsid_clean)

    # ── Pathway overlap analysis ──────────────────────────────────────────────
    pathways_affected: list[dict] = []
    use_case_votes: dict[str, float] = {}
    composite_score = 0.0

    for pathway_key, pathway_def in BPC157_PATHWAY_GENES.items():
        genes_hit = patient_genes & pathway_def["genes"]
        if not genes_hit:
            continue

        # Weight by number of genes hit in this pathway
        pathway_weight = len(genes_hit) / len(pathway_def["genes"])

        pathways_affected.append({
            "pathway": pathway_key,
            "display_name": pathway_def["display_name"],
            "genes_hit": sorted(genes_hit),
            "total_genes": len(pathway_def["genes"]),
            "coverage": round(pathway_weight, 2),
            "relevance": pathway_def["relevance"],
        })

        composite_score += pathway_weight

        # Vote for use cases
        for uc in pathway_def["use_cases"]:
            use_case_votes[uc] = use_case_votes.get(uc, 0) + pathway_weight

    # ── rsID-specific modifier effects ────────────────────────────────────────
    candidate_factors: list[dict] = []

    for rsid in patient_rsids:
        modifier = BPC157_MODIFIER_RSIDS.get(rsid)
        if modifier:
            candidate_factors.append({
                "rsid": rsid,
                "gene": modifier["gene"],
                "pathway": modifier["pathway"],
                "direction": modifier["direction"],
                "effect": modifier["effect"],
            })
            composite_score += modifier["predictor_weight"]

            # Boost relevant use cases
            pathway_def = BPC157_PATHWAY_GENES.get(modifier["pathway"], {})
            for uc in pathway_def.get("use_cases", []):
                use_case_votes[uc] = use_case_votes.get(uc, 0) + modifier["predictor_weight"]

    # ── Determine primary use case ────────────────────────────────────────────
    if use_case_votes:
        primary_use_case = max(use_case_votes, key=use_case_votes.get)
    else:
        primary_use_case = "general"

    uc_meta = _USE_CASE_META.get(primary_use_case, _USE_CASE_META["general"])

    # ── Assign responder tier ─────────────────────────────────────────────────
    responder_tier = _assign_responder_tier(composite_score)

    # ── Select biomarker recommendations ──────────────────────────────────────
    biomarkers = _select_biomarkers(pathways_affected, primary_use_case)

    # ── Generate summary text ─────────────────────────────────────────────────
    summary_text = generate_bpc157_summary({
        "responder_tier": responder_tier,
        "composite_score": round(composite_score, 2),
        "pathways_affected": pathways_affected,
        "primary_use_case": primary_use_case,
        "primary_use_case_display": uc_meta["display"],
        "candidate_factors": candidate_factors,
    })

    return {
        "responder_tier": responder_tier,
        "composite_score": round(composite_score, 2),
        "pathways_affected": pathways_affected,
        "primary_use_case": primary_use_case,
        "primary_use_case_display": uc_meta["display"],
        "primary_use_case_description": uc_meta["description"],
        "biomarker_recommendations": biomarkers,
        "candidate_factors": candidate_factors,
        "relevant_variant_count": len(relevant_variants),
        "total_variant_count": total_count,
        "summary_text": summary_text,
        "disclaimer": _DISCLAIMER,
    }


def _select_biomarkers(
    pathways_affected: list[dict],
    primary_use_case: str,
) -> list[dict]:
    """Select biomarker panels based on affected pathways and use case."""
    selected: list[dict] = []
    seen_names: set[str] = set()

    # Always include core inflammatory and safety panels
    for panel_key in ["core_inflammatory", "safety"]:
        for marker in _BIOMARKER_PANELS[panel_key]:
            if marker["name"] not in seen_names:
                selected.append(marker)
                seen_names.add(marker["name"])

    # Add use-case specific panels
    pathway_keys = {p["pathway"] for p in pathways_affected}

    if primary_use_case == "gastrointestinal" or "gut_barrier" in pathway_keys:
        for marker in _BIOMARKER_PANELS["gut_specific"]:
            if marker["name"] not in seen_names:
                selected.append(marker)
                seen_names.add(marker["name"])

    if primary_use_case == "musculoskeletal" or "collagen_tissue_repair" in pathway_keys:
        for marker in _BIOMARKER_PANELS["tissue_repair"]:
            if marker["name"] not in seen_names:
                selected.append(marker)
                seen_names.add(marker["name"])

    if "VEGF_angiogenesis" in pathway_keys:
        for marker in _BIOMARKER_PANELS["angiogenesis"]:
            if marker["name"] not in seen_names:
                selected.append(marker)
                seen_names.add(marker["name"])

    if "antioxidant_HO1" in pathway_keys:
        for marker in _BIOMARKER_PANELS["oxidative_stress"]:
            if marker["name"] not in seen_names:
                selected.append(marker)
                seen_names.add(marker["name"])

    if "growth_hormone_IGF" in pathway_keys:
        for marker in _BIOMARKER_PANELS["hormonal"]:
            if marker["name"] not in seen_names:
                selected.append(marker)
                seen_names.add(marker["name"])

    return selected


def generate_bpc157_summary(prediction: dict) -> str:
    """
    Generate a plain-English narrative summary for BPC-157 prediction.

    Parameters
    ----------
    prediction : dict
        Partial or full prediction dict (needs at minimum: responder_tier,
        pathways_affected, primary_use_case_display, candidate_factors).

    Returns
    -------
    str
        2–4 sentence clinical narrative.
    """
    tier = prediction.get("responder_tier", "low_confidence")
    pathways = prediction.get("pathways_affected", [])
    use_case = prediction.get("primary_use_case_display", "General")
    factors = prediction.get("candidate_factors", [])

    if not pathways and not factors:
        return (
            "No BPC-157-relevant pathway variants detected in this patient's "
            "genome. Insufficient genetic data to predict response. Clinical "
            "assessment and biomarker testing are recommended if considering "
            "BPC-157 therapy."
        )

    parts = []

    # Tier-specific opening
    tier_text = {
        "likely_good": (
            f"Genetic profile suggests a LIKELY GOOD candidate for BPC-157, "
            f"with {len(pathways)} relevant pathway(s) affected."
        ),
        "possible": (
            f"Genetic profile suggests a POSSIBLE candidate for BPC-157, "
            f"with {len(pathways)} relevant pathway(s) showing partial overlap."
        ),
        "uncertain": (
            f"Genetic profile provides UNCERTAIN evidence for BPC-157 candidacy. "
            f"Only {len(pathways)} pathway(s) showed weak overlap."
        ),
        "low_confidence": (
            "Genetic profile provides LOW CONFIDENCE for predicting BPC-157 response. "
            "Very limited pathway overlap detected."
        ),
    }
    parts.append(tier_text.get(tier, tier_text["low_confidence"]))

    # Use case
    parts.append(f"Primary predicted use case: {use_case}.")

    # Modifier highlights
    if factors:
        elevated = [f for f in factors if f["direction"] == "elevated"]
        impaired = [f for f in factors if f["direction"] == "impaired"]
        if elevated:
            genes = ", ".join(f["gene"] for f in elevated)
            parts.append(
                f"Elevated activity detected in {genes} — BPC-157's "
                f"anti-inflammatory effects may provide stronger benefit."
            )
        if impaired:
            genes = ", ".join(f["gene"] for f in impaired)
            parts.append(
                f"Impaired function detected in {genes} — BPC-157 may "
                f"help compensate via alternative pathway activation."
            )

    return " ".join(parts)
