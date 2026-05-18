"""
engine/annotators/receptor_mapper.py
====================================
Maps patient variants to receptor expression predictions and isoform
interpretation. Entirely offline — no API calls required.

Given a list of gene symbols from annotated variants, this module:
  1. Identifies which peptide-relevant receptors are affected
  2. Predicts expression level based on variant functional impact
  3. Estimates dominant isoform based on known variant-isoform associations
  4. Generates clinical interpretation text per receptor

Public interface
----------------
    map_receptors(variants: list[dict]) -> list[dict]
    predict_receptor_expression(gene: str, variants: list[dict]) -> dict
    generate_receptor_summary(receptor_profiles: list[dict]) -> str
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# ═══════════════════════════════════════════════════════════════════════════════
# RECEPTOR DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════════
# Each receptor maps to: gene symbol, known isoforms, expression modifiers,
# and clinical context for peptide therapy.

RECEPTOR_REGISTRY: dict[str, dict] = {
    "ESR1": {
        "full_name": "Estrogen Receptor Alpha",
        "pathway": "Estrogen Signaling",
        "peptide_relevance": [
            "Estradiol (transdermal/oral)",
            "Selective Estrogen Receptor Modulators (SERMs)",
        ],
        "isoforms": [
            {
                "name": "ESR1-FL",
                "description": "Full-length (66 kDa)",
                "function": "Classical nuclear transactivation",
                "default_expression": "NORMAL",
            },
            {
                "name": "ESR1-46",
                "description": "N-terminal truncated (46 kDa)",
                "function": "Membrane-associated rapid signaling; can act as dominant-negative",
                "default_expression": "LOW",
            },
            {
                "name": "ESR1-36",
                "description": "Truncated (36 kDa)",
                "function": "Membrane estrogen signaling; ligand-independent",
                "default_expression": "LOW",
            },
        ],
        "expression_modifiers": {
            "rs2228480": {"direction": "up", "magnitude": "moderate", "isoform_shift": "ESR1-FL"},
            "rs1801132": {"direction": "up", "magnitude": "mild", "isoform_shift": None},
            "rs9383592": {"direction": "up", "magnitude": "moderate", "isoform_shift": "ESR1-FL"},
        },
    },
    "ESR2": {
        "full_name": "Estrogen Receptor Beta",
        "pathway": "Estrogen Signaling",
        "peptide_relevance": [
            "Estradiol",
            "Phytoestrogens",
            "SERMs (tissue-specific effects)",
        ],
        "isoforms": [
            {
                "name": "ESR2-FL",
                "description": "Full-length (59 kDa)",
                "function": "Anti-proliferative; neuroprotective; anxiolytic",
                "default_expression": "NORMAL",
            },
            {
                "name": "ESR2-cx",
                "description": "C-terminal variant",
                "function": "Dominant-negative; inhibits ESR1 and ESR2-FL",
                "default_expression": "LOW",
            },
        ],
        "expression_modifiers": {
            "rs1271572": {"direction": "up", "magnitude": "moderate", "isoform_shift": "ESR2-FL"},
            "rs1256049": {"direction": "down", "magnitude": "mild", "isoform_shift": None},
        },
    },
    "GLP1R": {
        "full_name": "GLP-1 Receptor",
        "pathway": "Incretin Signaling",
        "peptide_relevance": [
            "GLP-1 Agonists (semaglutide, liraglutide)",
            "Tirzepatide (dual GLP-1/GIP)",
        ],
        "isoforms": [
            {
                "name": "GLP1R-FL",
                "description": "Full-length membrane receptor",
                "function": "Incretin signaling; insulin secretion; appetite suppression",
                "default_expression": "NORMAL",
            },
        ],
        "expression_modifiers": {
            "rs6923761": {"direction": "up", "magnitude": "strong", "isoform_shift": "GLP1R-FL"},
            "rs3765467": {"direction": "down", "magnitude": "moderate", "isoform_shift": None},
        },
    },
    "MC4R": {
        "full_name": "Melanocortin-4 Receptor",
        "pathway": "Melanocortin Signaling",
        "peptide_relevance": [
            "Setmelanotide",
            "Alpha-MSH analogues",
            "Appetite regulation peptides",
        ],
        "isoforms": [
            {
                "name": "MC4R-FL",
                "description": "Full-length (37 kDa)",
                "function": "Central appetite regulation; energy homeostasis",
                "default_expression": "NORMAL",
            },
        ],
        "expression_modifiers": {
            "rs17782313": {"direction": "down", "magnitude": "moderate", "isoform_shift": None},
            "rs571312": {"direction": "down", "magnitude": "mild", "isoform_shift": None},
        },
    },
    "OXTR": {
        "full_name": "Oxytocin Receptor",
        "pathway": "Oxytocin Signaling",
        "peptide_relevance": [
            "Oxytocin (intranasal)",
            "Carbetocin",
        ],
        "isoforms": [
            {
                "name": "OXTR-FL",
                "description": "Full-length membrane receptor",
                "function": "Social bonding; uterine contraction; mood regulation",
                "default_expression": "NORMAL",
            },
        ],
        "expression_modifiers": {
            "rs53576": {"direction": "up", "magnitude": "moderate", "isoform_shift": None},
            "rs2254298": {"direction": "down", "magnitude": "mild", "isoform_shift": None},
        },
    },
    "AR": {
        "full_name": "Androgen Receptor",
        "pathway": "Androgen Signaling",
        "peptide_relevance": [
            "Testosterone (TRT)",
            "DHEA",
            "Nandrolone",
        ],
        "isoforms": [
            {
                "name": "AR-FL",
                "description": "Full-length (110 kDa)",
                "function": "Classical androgen transactivation",
                "default_expression": "NORMAL",
            },
            {
                "name": "AR-V7",
                "description": "Splice variant (truncated LBD)",
                "function": "Constitutively active; ligand-independent",
                "default_expression": "LOW",
            },
        ],
        "expression_modifiers": {
            "rs6152": {"direction": "variable", "magnitude": "strong", "isoform_shift": "AR-FL"},
        },
    },
    "GPER1": {
        "full_name": "G-Protein Coupled Estrogen Receptor",
        "pathway": "Rapid Estrogen Signaling",
        "peptide_relevance": [
            "Estradiol (non-genomic effects)",
            "SERMs (G-1 agonist class)",
        ],
        "isoforms": [
            {
                "name": "GPER1-FL",
                "description": "Full-length membrane receptor",
                "function": "Rapid non-genomic estrogen signaling; cardiovascular protection",
                "default_expression": "NORMAL",
            },
        ],
        "expression_modifiers": {
            "rs3808350": {"direction": "up", "magnitude": "mild", "isoform_shift": None},
            "rs3808351": {"direction": "down", "magnitude": "mild", "isoform_shift": None},
        },
    },
    "FSHR": {
        "full_name": "Follicle-Stimulating Hormone Receptor",
        "pathway": "GnRH Downstream",
        "peptide_relevance": [
            "FSH therapy (fertility)",
            "GnRH analogues (indirect)",
        ],
        "isoforms": [
            {
                "name": "FSHR-FL",
                "description": "Full-length membrane receptor",
                "function": "Follicle development; ovarian steroidogenesis",
                "default_expression": "NORMAL",
            },
        ],
        "expression_modifiers": {
            "rs6166": {"direction": "down", "magnitude": "moderate", "isoform_shift": None},
            "rs6165": {"direction": "down", "magnitude": "mild", "isoform_shift": None},
        },
    },
}

# ═══════════════════════════════════════════════════════════════════════════════
# EXPRESSION LEVEL LOGIC
# ═══════════════════════════════════════════════════════════════════════════════

_MAGNITUDE_SCORES = {"strong": 2, "moderate": 1, "mild": 0.5}

_EXPRESSION_THRESHOLDS = {
    # net_score → expression level
    "HIGH": 1.0,
    "LOW": -1.0,
}


def _compute_expression_level(
    base_level: str,
    modifiers_hit: list[dict],
) -> str:
    """Compute net expression level from variant modifiers."""
    if not modifiers_hit:
        return base_level

    net = 0.0
    for mod in modifiers_hit:
        score = _MAGNITUDE_SCORES.get(mod["magnitude"], 0.5)
        if mod["direction"] == "up":
            net += score
        elif mod["direction"] == "down":
            net -= score
        # "variable" contributes nothing to net — handled by CAG repeat module

    if net >= _EXPRESSION_THRESHOLDS["HIGH"]:
        return "HIGH"
    elif net <= _EXPRESSION_THRESHOLDS["LOW"]:
        return "LOW"
    return "NORMAL"


def _determine_dominant_isoform(
    isoforms: list[dict],
    modifiers_hit: list[dict],
) -> dict:
    """Pick the dominant isoform based on variant shifts."""
    shifted_isoform_names = [
        m["isoform_shift"] for m in modifiers_hit if m.get("isoform_shift")
    ]

    if shifted_isoform_names:
        # Pick the most frequently shifted isoform
        target = max(set(shifted_isoform_names), key=shifted_isoform_names.count)
        for iso in isoforms:
            if iso["name"] == target:
                return iso

    # Default: first isoform (full-length)
    return isoforms[0] if isoforms else {}


# ═══════════════════════════════════════════════════════════════════════════════
# CLINICAL INTERPRETATION TEMPLATES
# ═══════════════════════════════════════════════════════════════════════════════

_CLINICAL_TEMPLATES = {
    "HIGH": (
        "{receptor_name} expression estimated HIGH based on genotype. "
        "Patient likely to show enhanced response to {peptides}. "
        "Consider starting at standard or reduced dose with close monitoring."
    ),
    "NORMAL": (
        "{receptor_name} expression estimated NORMAL. "
        "Standard dosing protocols for {peptides} are appropriate."
    ),
    "LOW": (
        "{receptor_name} expression estimated LOW based on genotype. "
        "Patient may show reduced response to {peptides}. "
        "Consider higher dose or alternative receptor targets."
    ),
}


def _generate_interpretation(
    receptor_name: str,
    expression: str,
    peptides: list[str],
) -> str:
    """Generate clinical interpretation text."""
    template = _CLINICAL_TEMPLATES.get(expression, _CLINICAL_TEMPLATES["NORMAL"])
    peptide_str = ", ".join(peptides[:2])
    if len(peptides) > 2:
        peptide_str += f" (+{len(peptides) - 2} more)"
    return template.format(receptor_name=receptor_name, peptides=peptide_str)


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════════

def predict_receptor_expression(
    gene: str,
    variant_rsids: list[str],
) -> Optional[dict]:
    """
    Predict receptor expression and isoform for a single receptor gene.

    Parameters
    ----------
    gene : str
        Gene symbol (e.g., 'ESR1', 'GLP1R').
    variant_rsids : list[str]
        rsIDs from patient's variant calls (e.g., ['rs2228480', 'rs1801132']).

    Returns
    -------
    dict or None
        Receptor profile dict, or None if gene is not in receptor registry.
    """
    gene_upper = gene.upper().strip()
    receptor_def = RECEPTOR_REGISTRY.get(gene_upper)
    if not receptor_def:
        return None

    # Find which expression modifiers are hit by patient variants
    modifiers = receptor_def.get("expression_modifiers", {})
    modifiers_hit = []
    variants_affecting = []
    for rsid in variant_rsids:
        rsid_clean = rsid.split("_")[0] if "_" in rsid else rsid
        if rsid_clean in modifiers:
            modifiers_hit.append(modifiers[rsid_clean])
            variants_affecting.append(rsid)

    # Compute expression level
    base_level = receptor_def["isoforms"][0]["default_expression"]
    expression_level = _compute_expression_level(base_level, modifiers_hit)

    # Determine dominant isoform
    dominant_isoform = _determine_dominant_isoform(
        receptor_def["isoforms"], modifiers_hit
    )

    # Build isoform predictions
    isoform_predictions = []
    for iso in receptor_def["isoforms"]:
        is_dominant = (iso["name"] == dominant_isoform.get("name"))
        iso_expression = expression_level if is_dominant else iso["default_expression"]
        isoform_predictions.append({
            "isoform": iso["name"],
            "description": iso["description"],
            "expression_level": iso_expression,
            "functional_prediction": iso["function"],
            "is_dominant": is_dominant,
        })

    # Clinical interpretation
    interpretation = _generate_interpretation(
        receptor_def["full_name"],
        expression_level,
        receptor_def["peptide_relevance"],
    )

    return {
        "receptor_gene": gene_upper,
        "receptor_name": receptor_def["full_name"],
        "pathway": receptor_def["pathway"],
        "expression_level": expression_level,
        "isoform_predictions": isoform_predictions,
        "variants_affecting": variants_affecting,
        "peptide_relevance": receptor_def["peptide_relevance"],
        "clinical_interpretation": interpretation,
    }


def map_receptors(variants: list[dict]) -> list[dict]:
    """
    Map all patient variants to receptor expression predictions.

    Parameters
    ----------
    variants : list[dict]
        Annotated variant dicts from pipeline. Each must have at least
        'genes' (list[str]) and optionally 'rsid' (str).

    Returns
    -------
    list[dict]
        List of receptor profiles for all receptors affected by patient
        variants. Sorted by expression impact (HIGH first, then LOW, then NORMAL).
    """
    # Collect all gene symbols and rsIDs from variants
    gene_to_rsids: dict[str, list[str]] = {}
    for v in variants:
        genes = v.get("genes", [])
        if isinstance(genes, str):
            genes = [genes]
        rsid = v.get("rsid", "")
        for g in genes:
            g_upper = g.upper().strip()
            if g_upper not in gene_to_rsids:
                gene_to_rsids[g_upper] = []
            if rsid:
                gene_to_rsids[g_upper].append(rsid)

    # Check each receptor in registry
    receptor_profiles = []
    for receptor_gene in RECEPTOR_REGISTRY:
        # Collect all rsIDs from variants matching this gene
        all_rsids = gene_to_rsids.get(receptor_gene, [])

        # Also check if any variant rsID directly matches a modifier
        for v in variants:
            rsid = v.get("rsid", "")
            rsid_clean = rsid.split("_")[0] if "_" in rsid else rsid
            if rsid_clean in RECEPTOR_REGISTRY[receptor_gene].get("expression_modifiers", {}):
                if rsid not in all_rsids:
                    all_rsids.append(rsid)

        if all_rsids:
            profile = predict_receptor_expression(receptor_gene, all_rsids)
            if profile:
                receptor_profiles.append(profile)

    # Sort: HIGH impact first, then LOW, then NORMAL
    _sort_order = {"HIGH": 0, "LOW": 1, "NORMAL": 2}
    receptor_profiles.sort(key=lambda p: _sort_order.get(p["expression_level"], 3))

    return receptor_profiles


def generate_receptor_summary(receptor_profiles: list[dict]) -> str:
    """
    Generate a narrative summary across all receptor profiles.

    Parameters
    ----------
    receptor_profiles : list[dict]
        Output from map_receptors().

    Returns
    -------
    str
        2-4 sentence clinical narrative.
    """
    if not receptor_profiles:
        return "No peptide-relevant receptor variants detected in this patient."

    high = [p for p in receptor_profiles if p["expression_level"] == "HIGH"]
    low = [p for p in receptor_profiles if p["expression_level"] == "LOW"]

    parts = []
    if high:
        names = ", ".join(p["receptor_name"] for p in high)
        parts.append(
            f"Patient shows elevated expression for {names}, "
            f"suggesting enhanced sensitivity to related peptide therapies."
        )
    if low:
        names = ", ".join(p["receptor_name"] for p in low)
        parts.append(
            f"Reduced expression predicted for {names}; "
            f"dose adjustment or alternative targets may be warranted."
        )
    if not high and not low:
        parts.append(
            "All detected receptor expression levels are within normal range. "
            "Standard peptide dosing protocols are appropriate."
        )

    total = len(receptor_profiles)
    parts.append(
        f"Analysis covered {total} receptor{'s' if total != 1 else ''} "
        f"across {len(set(p['pathway'] for p in receptor_profiles))} signaling pathways."
    )

    return " ".join(parts)
