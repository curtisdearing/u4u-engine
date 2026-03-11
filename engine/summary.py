"""
engine/summary.py
=================
Generates plain-English consumer summaries from scored variant dicts.
This is the primary user-facing output of the engine.

ConsumerSummary fields
----------------------
    emoji             : str          — 🔴🟠🟡🟢 visual tier indicator
    headline          : str          — one-sentence plain-English summary
    consequence_plain : str          — molecular impact in plain English
    rarity_plain      : str          — population frequency in plain English
    clinvar_plain     : str          — clinical classification in plain English
    disease_name      : str | None   — associated disease/condition (human-readable)
    condition_key     : str | None   — stable lookup key: "OMIM:<id>", "MedGen:<id>",
                                       "ClinVar:<uid>", or None
    action_hint       : str          — recommended next step for the user
    tier              : str          — "critical" | "high" | "medium" | "low"
    zygosity_plain    : str | None   — plain-English zygosity statement
    carrier_note      : str | None   — set when variant is a carrier finding

Public interface
----------------
    generate_summary(scored: dict) -> ConsumerSummary
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ConsumerSummary:
    emoji:             str
    headline:          str
    consequence_plain: str
    rarity_plain:      str
    clinvar_plain:     str
    disease_name:      Optional[str]
    condition_key:     Optional[str]
    action_hint:       str
    tier:              str
    zygosity_plain:    Optional[str]
    carrier_note:      Optional[str]


# ---------------------------------------------------------------------------
# Consequence → plain English
# ---------------------------------------------------------------------------

_CONSEQUENCE_MAP = {
    "stop_gained":
        "creates a premature stop signal in the protein, typically breaking its function",
    "frameshift_variant":
        "disrupts the way the gene is read, heavily altering the resulting protein",
    "splice_donor_variant":
        "interferes with how the gene's instructions are spliced together",
    "splice_acceptor_variant":
        "interferes with how the gene's instructions are spliced together",
    "start_lost":
        "removes the starting signal for the protein, preventing its creation",
    "stop_lost":
        "removes the stop signal, causing an abnormally long and potentially non-functional protein",
    "transcript_ablation":
        "deletes an entire transcript, eliminating the gene product",
    "missense_variant":
        "changes a single building block (amino acid) in the protein",
    "inframe_deletion":
        "removes one or more amino acids from the protein without disrupting the reading frame",
    "inframe_insertion":
        "adds one or more amino acids to the protein without disrupting the reading frame",
    "synonymous_variant":
        "does not change the protein's building blocks — a silent variant",
    "intron_variant":
        "occurs in a non-coding region within the gene",
    "intergenic_variant":
        "occurs in a region between genes",
    "3_prime_UTR_variant":
        "occurs in the 3′ untranslated region, which can affect gene expression levels",
    "5_prime_UTR_variant":
        "occurs in the 5′ untranslated region, which can affect how the gene is turned on",
    "protein_altering_variant":
        "alters the protein sequence in a way that may affect its function",
}


def _consequence_to_plain(consequence: str) -> str:
    return _CONSEQUENCE_MAP.get(
        consequence,
        f"has a subtle or unclassified effect ({consequence.replace('_', ' ')})",
    )


# ---------------------------------------------------------------------------
# gnomAD AF → plain English
# ---------------------------------------------------------------------------

def _af_to_rarity(af: Optional[float]) -> str:
    if af is None:
        return "not yet observed in large public genome databases"
    if af == 0:
        return "extremely rare — allele frequency is effectively zero in public databases"
    if af < 0.0001:
        return "ultra-rare (seen in less than 1 in 10,000 people)"
    if af < 0.001:
        return "very rare (seen in roughly 1 in 1,000 people)"
    if af < 0.01:
        return "rare (seen in about 1 in 100 people)"
    if af < 0.05:
        return f"uncommon (seen in about {af * 100:.1f}% of people)"
    return f"common (seen in about {af * 100:.1f}% of people)"


# ---------------------------------------------------------------------------
# ClinVar → plain English
# ---------------------------------------------------------------------------

def _clinvar_to_plain(clinvar: Optional[str], disease: Optional[str]) -> str:
    if not clinvar:
        return "has no specific clinical classification in ClinVar"

    c = clinvar.lower()
    if "pathogenic" in c and "likely" not in c:
        base = "is classified as **disease-causing (pathogenic)**"
    elif "likely pathogenic" in c:
        base = "is classified as **likely disease-causing**"
    elif "benign" in c and "likely" not in c:
        base = "is classified as **harmless (benign)**"
    elif "likely benign" in c:
        base = "is classified as **likely harmless**"
    elif "uncertain" in c or "vus" in c:
        base = (
            "is classified as **having uncertain significance (VUS)** — "
            "there isn't yet enough evidence to know if it affects health"
        )
    else:
        base = f"is classified as {clinvar.replace('_', ' ')}"

    if disease and disease.lower() not in {"not provided", "not specified", "see cases"}:
        base += f" for {disease}"

    return base


# ---------------------------------------------------------------------------
# Zygosity → plain English
# ---------------------------------------------------------------------------

def _zygosity_to_plain(zygosity: Optional[str]) -> Optional[str]:
    if not zygosity or zygosity == "unknown":
        return None
    if zygosity == "heterozygous":
        return "You carry one copy of this variant (heterozygous)."
    if zygosity == "homozygous_alt":
        return "You carry two copies of this variant (homozygous)."
    if zygosity == "homozygous_ref":
        return None  # shouldn't reach summary — filtered out upstream
    return None


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------

def generate_summary(scored: dict) -> ConsumerSummary:
    """
    Convert a scored variant dict into a plain-English ConsumerSummary.

    Parameters
    ----------
    scored : dict
        Output of score_variant(). Expected keys:
        tier, consequence, clinvar, disease_name, gnomad_af, genes,
        zygosity, carrier_note.

    Returns
    -------
    ConsumerSummary
    """
    tier          = scored.get("tier", "low")
    consequence   = scored.get("consequence", "unknown")
    clinvar       = scored.get("clinvar")
    disease       = scored.get("disease_name")
    condition_key = scored.get("condition_key")
    gnomad_af     = scored.get("gnomad_af")
    genes_list    = scored.get("genes") or []
    zygosity      = scored.get("zygosity")
    carrier_note  = scored.get("carrier_note")

    genes = ", ".join(genes_list) if genes_list else "a non-coding region"

    consequence_plain = f"At the molecular level, this variant {_consequence_to_plain(consequence)}."
    rarity_plain      = f"In the general population, this variant is {_af_to_rarity(gnomad_af)}."
    clinvar_plain     = f"According to clinical geneticists, this variant {_clinvar_to_plain(clinvar, disease)}."
    zygosity_plain    = _zygosity_to_plain(zygosity)

    # Carrier findings get special headline/action treatment regardless of tier
    if carrier_note:
        emoji    = "🔵"
        headline = f"You appear to be a carrier of a variant in {genes}."
        action_hint = (
            "As a carrier of a recessive variant, you typically won't be affected "
            "by this condition yourself. This may be relevant for family planning — "
            "consider discussing with a genetic counselor if you have questions."
        )
    elif tier == "critical":
        emoji    = "🔴"
        headline = f"This variant in {genes} is known to cause disease."
        action_hint = (
            "Consider discussing this finding with a genetic counselor or your doctor, "
            "especially if you have a personal or family history of related conditions."
        )
    elif tier == "high":
        emoji    = "🟠"
        headline = f"This variant in {genes} is highly suspicious or likely to disrupt gene function."
        action_hint = (
            "This finding may be important. Discussing it with a healthcare provider "
            "could help clarify any potential risks."
        )
    elif tier == "medium":
        emoji    = "🟡"
        headline = f"There is currently uncertain or limited evidence about this variant in {genes}."
        action_hint = (
            "Most variants of uncertain significance turn out to be harmless, but "
            "classification can change as new research is published."
        )
    else:
        emoji    = "🟢"
        headline = f"This is a low-risk variant in {genes}."
        action_hint = (
            "No specific action is needed. This variant is generally considered "
            "harmless or is very common in the population."
        )

    return ConsumerSummary(
        emoji=emoji,
        headline=headline,
        consequence_plain=consequence_plain,
        rarity_plain=rarity_plain,
        clinvar_plain=clinvar_plain,
        disease_name=disease,
        condition_key=condition_key,
        action_hint=action_hint,
        tier=tier,
        zygosity_plain=zygosity_plain,
        carrier_note=carrier_note,
    )
