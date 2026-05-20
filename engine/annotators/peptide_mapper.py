"""
engine/annotators/peptide_mapper.py
====================================
Maps patient variants to peptide therapy candidates based on genotyping
gene targets from the peptides.csv knowledge base. Entirely offline —
no API calls required.

Each peptide entry defines which genes should be genotyped to predict
response. This module checks which of those genes appear in the patient's
variant results and returns coverage metrics.

Public interface
----------------
    map_peptide_coverage(variants: list[dict]) -> dict
    generate_peptide_summary(mapping: dict) -> str
"""

from __future__ import annotations

from typing import Optional


# ═══════════════════════════════════════════════════════════════════════════════
# PEPTIDE → GENE MAPPINGS (derived from peptides.csv)
# ═══════════════════════════════════════════════════════════════════════════════

PEPTIDE_GENE_MAP: dict[str, dict] = {
    "GHK-Cu + BPC-157 + TB-500": {
        "genes": {"COL1A1", "COL1A2", "SMYD3"},
        "rationale": (
            "Predict ECM repair capacity and collagen synthetic response."
        ),
        "refs": ["[1-3]"],
        "category": "tissue_repair",
        "category_display": "Tissue Repair / Collagen Synthesis",
    },
    "CJC-1295 + Ipamorelin": {
        "genes": {"GHSR"},
        "rationale": (
            "Identify loss-of-function receptor variants that blunt "
            "GH secretagogue response."
        ),
        "refs": ["[4-7]"],
        "category": "growth_hormone",
        "category_display": "Growth Hormone Secretagogue",
    },
    "BPC-157 + TB-500": {
        "genes": {"NOS3"},
        "rationale": (
            "Predict NO-dependent angiogenic and healing response."
        ),
        "refs": ["[8-9]"],
        "category": "angiogenesis",
        "category_display": "Angiogenesis / Healing",
    },
    "AOD-9604": {
        "genes": {"ADRB3"},
        "rationale": (
            "Predict lipolytic response; Trp64Arg variant impairs "
            "β3-AR function."
        ),
        "refs": ["[10]"],
        "category": "weight_management",
        "category_display": "Weight Management / Lipolysis",
    },
    "MOTS-c": {
        "genes": {"MT-RNR1"},  # mtDNA m.1382A>C mapped to MT-RNR1 locus
        "rationale": (
            "K14Q substitution in MOTS-c peptide reduces "
            "insulin-sensitizing activity (males)."
        ),
        "refs": ["[11]"],
        "category": "metabolic",
        "category_display": "Metabolic / Insulin Sensitization",
    },
    "Epithalon": {
        "genes": {"TERT"},
        "rationale": (
            "Stratify telomerase activation benefit vs. cancer risk "
            "(VNTR2-1, rs2736100)."
        ),
        "refs": ["[12-14]"],
        "category": "longevity",
        "category_display": "Longevity / Telomere Maintenance",
    },
    "Thymosin Alpha-1": {
        "genes": {"TLR2", "TLR4", "TLR9"},
        "rationale": (
            "Predict immunomodulatory response via TLR-dependent "
            "DC activation."
        ),
        "refs": ["[15-17]"],
        "category": "immune",
        "category_display": "Immune Modulation",
    },
    "Matrixyl": {
        "genes": {"COL1A1", "IRF4"},
        "rationale": (
            "Predict collagen synthesis upregulation capacity."
        ),
        "refs": ["[2-3, 18]"],
        "category": "skin",
        "category_display": "Skin / Anti-Aging",
    },
    "Argireline": {
        "genes": {"SNAP25"},
        "rationale": (
            "Predict SNARE-complex modulation efficacy "
            "(parallels BoNT-A pharmacogenomics)."
        ),
        "refs": ["[19-20]"],
        "category": "skin",
        "category_display": "Skin / Neuromodulation",
    },
    "SNAP-8": {
        "genes": {"SNAP25", "SV2C"},
        "rationale": (
            "Predict neuromodulatory efficacy and duration."
        ),
        "refs": ["[19, 21]"],
        "category": "skin",
        "category_display": "Skin / Neuromodulation",
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# REFERENCE LIBRARY (derived from peptides.csv refs column)
# ═══════════════════════════════════════════════════════════════════════════════

PEPTIDE_REFERENCES: dict[int, str] = {
    1: "Injectable Peptide Therapy: A Primer for Orthopaedic and Sports Medicine Physicians. The American Journal of Sports Medicine. 2026. Mayfield CK, Bolia IK, Feingold CL, et al.",
    2: "Safety and Efficacy of Approved and Unapproved Peptide Therapies for Musculoskeletal Injuries and Athletic Performance. Sports Medicine. 2026. Mendias CL, Awan TM.",
    3: "Multifunctionality and Possible Medical Application of the BPC 157 Peptide-Literature and Patent Review. Pharmaceuticals. 2025. Józwiak M, Bauer M, Kamysz W, Kleczkowska P.",
    4: "GHK Peptide as a Natural Modulator of Multiple Cellular Pathways in Skin Regeneration. BioMed Research International. 2014. Pickart L, Vasquez-Soltero JM, Margolina A.",
    5: "Bioactive oligopeptides in dermatology: Part I. Experimental Dermatology. 2012. Reddy B, Jow T, Hantash BM.",
    6: "Deciphering the Molecular Clock: Exploring Molecular Mechanisms and Genetic Influences on Skin Ageing. Biogerontology. 2025. Ng HY, Wu YS, Biswas M, Sim MS.",
    7: "NF-κB Accumulation Associated With COL1A1 Transactivators Defects During Chronological Aging Represses Type I Collagen Expression. The Journal of Investigative Dermatology. 2012. Bigot N, et al.",
    8: "Ghrelin and Growth Hormone (GH) Secretagogues Potentiate GH-releasing Hormone (GHRH)-induced Cyclic Adenosine 3',5'-Monophosphate Production. Endocrinology. 2002. Cunha SR, Mayo KE.",
    9: "Growth Hormone-Releasing Hormone as an Agonist of the Ghrelin Receptor GHS-R1a. PNAS. 2008. Casanueva FF, et al.",
    10: "Identification and Functional Analysis of Novel Human Growth Hormone Secretagogue Receptor (GHSR) Gene Mutations. JCEM. 2011. Inoue H, et al.",
    11: "GH Secretagogue Receptor Gene Polymorphisms Are Associated With Stature Throughout Childhood. European Journal of Endocrinology. 2012. Riedl S, et al.",
    12: "Variations in the Ghrelin Receptor Gene Associate With Obesity and Glucose Metabolism. PloS One. 2008. Mager U, et al.",
    13: "Ghrelin Receptor Mutations and Human Obesity. Progress in Molecular Biology and Translational Science. 2016. Wang W, Tao YX.",
    14: "BPC 157 Therapy: Targeting Angiogenesis and Nitric Oxide. Pharmaceuticals. 2025. Sikiric P, et al.",
    15: "Stable Gastric Pentadecapeptide BPC 157 as a Therapy and Safety Key. Pharmaceuticals. 2025. Sikiric P, et al.",
    16: "The Effects of Human GH and Its Lipolytic Fragment (AOD9604) on Lipid Metabolism. Endocrinology. 2001. Heffernan M, et al.",
    17: "Obesity Drugs in Clinical Development. Current Opinion in Investigational Drugs. 2006. Halford JC.",
    18: "MOTS-c: A Novel Mitochondrial-Derived Peptide Regulating Muscle and Fat Metabolism. Free Radical Biology & Medicine. 2016. Lee C, et al.",
    19: "The Mitochondrial-Derived Peptide MOTS-c Promotes Metabolic Homeostasis and Reduces Obesity and Insulin Resistance. Cell Metabolism. 2015. Lee C, et al.",
    20: "A Pro-Diabetogenic mtDNA Polymorphism in the Mitochondrial-Derived Peptide, MOTS-c. Aging. 2021. Zempo H, et al.",
    21: "Epitalon Increases Telomere Length in Human Cell Lines. Biogerontology. 2025. Al-Dulaimi S, et al.",
    22: "Polymorphic Tandem DNA Repeats Activate the Human Telomerase Reverse Transcriptase Gene. PNAS. 2021. Xu T, et al.",
}


# ═══════════════════════════════════════════════════════════════════════════════
# MAPPING FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════

def map_peptide_coverage(variants: list[dict]) -> dict:
    """
    Map patient variants to peptide therapy candidates.

    For each peptide in PEPTIDE_GENE_MAP, checks how many of the required
    genotyping genes appear in the patient's variant gene list.

    Parameters
    ----------
    variants : list[dict]
        Annotated variant dicts from the pipeline. Each should have a
        'genes' key (list[str] or str).

    Returns
    -------
    dict
        {
            "recommendations": list[dict],  # per-peptide coverage results
            "summary_text": str,            # plain-English summary
            "genes_found_total": list[str],  # all unique patient genes
            "peptides_with_coverage": int,   # count of peptides with >0% coverage
        }
    """
    # Collect all unique genes from patient variants
    patient_genes: set[str] = set()
    for v in variants:
        genes = v.get("genes", [])
        if isinstance(genes, str):
            genes = [genes]
        for g in genes:
            if g:
                patient_genes.add(g.upper())

    recommendations = []
    for peptide_name, info in PEPTIDE_GENE_MAP.items():
        target_genes = info["genes"]
        # Normalize comparison to uppercase
        target_upper = {g.upper() for g in target_genes}
        genes_found = sorted(patient_genes & target_upper)
        coverage = len(genes_found) / max(len(target_genes), 1)

        recommendations.append({
            "peptide_name": peptide_name,
            "genes_for_genotyping": sorted(target_genes),
            "genes_found": genes_found,
            "genes_missing": sorted(target_upper - patient_genes),
            "coverage": round(coverage, 2),
            "rationale": info["rationale"],
            "references": info["refs"],
            "category": info["category"],
            "category_display": info["category_display"],
        })

    # Sort: highest coverage first, then alphabetical
    recommendations.sort(key=lambda r: (-r["coverage"], r["peptide_name"]))

    peptides_with_coverage = sum(1 for r in recommendations if r["coverage"] > 0)
    summary_text = generate_peptide_summary(recommendations)

    return {
        "recommendations": recommendations,
        "summary_text": summary_text,
        "genes_found_total": sorted(patient_genes),
        "peptides_with_coverage": peptides_with_coverage,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

def generate_peptide_summary(recommendations: list[dict]) -> str:
    """
    Generate a plain-English summary of peptide coverage results.

    Parameters
    ----------
    recommendations : list[dict]
        Output of map_peptide_coverage()["recommendations"].

    Returns
    -------
    str
        Multi-sentence summary.
    """
    if not recommendations:
        return (
            "No peptide therapy candidates were evaluated. "
            "No variant data was available for analysis."
        )

    covered = [r for r in recommendations if r["coverage"] > 0]
    full = [r for r in recommendations if r["coverage"] >= 1.0]
    partial = [r for r in recommendations if 0 < r["coverage"] < 1.0]
    uncovered = [r for r in recommendations if r["coverage"] == 0]

    parts = []

    if full:
        names = ", ".join(r["peptide_name"] for r in full)
        parts.append(
            f"Full genotyping coverage ({len(full)} peptide"
            f"{'s' if len(full) != 1 else ''}): {names}. "
            f"All target genes have variant data on file."
        )

    if partial:
        details = "; ".join(
            f"{r['peptide_name']} ({int(r['coverage']*100)}%)"
            for r in partial
        )
        parts.append(
            f"Partial coverage ({len(partial)} peptide"
            f"{'s' if len(partial) != 1 else ''}): {details}."
        )

    if uncovered:
        parts.append(
            f"{len(uncovered)} peptide"
            f"{'s have' if len(uncovered) != 1 else ' has'} "
            f"no genotyping data available yet."
        )

    if not covered:
        parts.append(
            "No peptide-relevant genes were found in the patient's "
            "variant data. Additional genotyping may be needed."
        )

    return " ".join(parts)
