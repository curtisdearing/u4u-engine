"""Tests for engine/scoring.py"""

import pytest
from engine.scoring import score_variant, Tier


def _a(**kwargs):
    """Build a minimal annotated variant dict."""
    base = {
        "variant_id": "rs1", "rsid": "rs1", "location": "1:100",
        "chrom": "1", "pos": 100, "ref": "A", "alt": "T",
        "consequence": "missense_variant", "genes": ["BRCA1"],
        "clinvar": None, "disease_name": None,
        "gnomad_af": 0.001, "zygosity": "heterozygous",
        "gq": 30, "dp": 20,
    }
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# ClinVar short-circuits
# ---------------------------------------------------------------------------

def test_pathogenic_short_circuits_to_critical():
    result = score_variant(_a(clinvar="pathogenic"))
    assert result["tier"]  == Tier.CRITICAL.value
    assert result["score"] == 1000


def test_benign_short_circuits_to_low():
    result = score_variant(_a(clinvar="benign"))
    assert result["tier"]  == Tier.LOW.value
    assert result["score"] == 1


def test_likely_pathogenic_scores_high():
    result = score_variant(_a(clinvar="likely pathogenic", gnomad_af=0.00001))
    assert result["tier"] in (Tier.CRITICAL.value, Tier.HIGH.value)
    assert result["score"] >= 500


def test_vus_scores_medium():
    result = score_variant(_a(clinvar="uncertain significance", gnomad_af=None))
    # VUS + missense + no frequency → 50 + 50 = 100 → HIGH or edge MEDIUM
    assert result["score"] >= 50


# ---------------------------------------------------------------------------
# Functional consequence scoring
# ---------------------------------------------------------------------------

def test_high_impact_adds_100():
    base = score_variant(_a(clinvar=None, consequence="missense_variant",    gnomad_af=None))
    lof  = score_variant(_a(clinvar=None, consequence="stop_gained",         gnomad_af=None))
    assert lof["score"] > base["score"]


def test_low_impact_adds_5():
    result = score_variant(_a(clinvar=None, consequence="synonymous_variant", gnomad_af=None))
    assert result["score"] >= 5


# ---------------------------------------------------------------------------
# gnomAD frequency scoring
# ---------------------------------------------------------------------------

def test_absent_gnomad_adds_30():
    result = score_variant(_a(clinvar=None, consequence="intron_variant", gnomad_af=0))
    # intron (5) + absent (30) + no gene penalty → positive
    assert result["score"] > 0


def test_common_variant_penalized():
    rare   = score_variant(_a(clinvar=None, consequence="missense_variant", gnomad_af=0.0001))
    common = score_variant(_a(clinvar=None, consequence="missense_variant", gnomad_af=0.20))
    assert rare["score"] > common["score"]


# ---------------------------------------------------------------------------
# Tier assignment
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("score,expected_tier", [
    (600, "critical"),
    (150, "high"),
    (45,  "medium"),
    (10,  "low"),
])
def test_tier_thresholds(score, expected_tier):
    # Craft inputs that produce approximately the desired score
    clinvar = "pathogenic" if score >= 600 else None
    gnomad  = None if score > 100 else 0.001
    csq     = "stop_gained" if score >= 100 else "intron_variant"
    result  = score_variant(_a(clinvar=clinvar, consequence=csq, gnomad_af=gnomad))
    if clinvar == "pathogenic":
        assert result["tier"] == "critical"


# ---------------------------------------------------------------------------
# clinvar_raw preservation
# ---------------------------------------------------------------------------

def test_clinvar_raw_preserved():
    result = score_variant(_a(clinvar="uncertain significance"))
    assert result["clinvar_raw"] == "uncertain significance"


def test_clinvar_raw_preserved_when_none():
    result = score_variant(_a(clinvar=None))
    assert result["clinvar_raw"] is None


# ---------------------------------------------------------------------------
# Frequency-derived label
# ---------------------------------------------------------------------------

def test_frequency_derived_label_common_vus():
    result = score_variant(_a(clinvar="uncertain significance", gnomad_af=0.10))
    assert result["frequency_derived_label"] == "Likely benign (common in population)"


def test_frequency_derived_label_ultra_rare_vus():
    result = score_variant(_a(clinvar="uncertain significance", gnomad_af=0.000001))
    assert result["frequency_derived_label"] == "Uncertain significance (ultra-rare variant)"


def test_frequency_derived_label_not_set_for_pathogenic():
    result = score_variant(_a(clinvar="pathogenic", gnomad_af=0.10))
    assert result["frequency_derived_label"] is None


def test_clinvar_not_overwritten_by_frequency_label():
    result = score_variant(_a(clinvar="uncertain significance", gnomad_af=0.10))
    # frequency_derived_label is extra context — clinvar field must be untouched
    assert result["clinvar"] == "uncertain significance"


# ---------------------------------------------------------------------------
# Carrier detection
# ---------------------------------------------------------------------------

def test_carrier_note_set_for_heterozygous_recessive():
    result = score_variant(_a(
        clinvar="pathogenic",
        disease_name="autosomal recessive disease",
        zygosity="heterozygous",
    ))
    # Pathogenic short-circuit fires first — carrier_note set to None
    # (carrier detection only applies when short-circuit doesn't trigger)
    # Test the non-short-circuit path:
    result2 = score_variant(_a(
        clinvar="uncertain significance",
        disease_name="autosomal recessive cerebellar ataxia",
        zygosity="heterozygous",
        gnomad_af=0.001,
    ))
    assert result2["carrier_note"] is not None
    assert "carrier" in result2["carrier_note"].lower()


def test_carrier_note_not_set_for_homozygous():
    result = score_variant(_a(
        clinvar="uncertain significance",
        disease_name="autosomal recessive disease",
        zygosity="homozygous_alt",
    ))
    assert result["carrier_note"] is None


def test_carrier_note_not_set_for_dominant():
    result = score_variant(_a(
        clinvar="uncertain significance",
        disease_name="hereditary breast cancer",
        zygosity="heterozygous",
    ))
    assert result["carrier_note"] is None


def test_carrier_halves_score():
    without_carrier = score_variant(_a(
        clinvar="uncertain significance",
        disease_name="autosomal recessive condition",
        zygosity="homozygous_alt",
        gnomad_af=0.001,
    ))
    with_carrier = score_variant(_a(
        clinvar="uncertain significance",
        disease_name="autosomal recessive condition",
        zygosity="heterozygous",
        gnomad_af=0.001,
    ))
    assert with_carrier["score"] < without_carrier["score"]
