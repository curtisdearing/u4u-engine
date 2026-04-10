"""
tests/test_engine/test_prs_calculator.py
=========================================
Unit tests for the polygenic risk score calculator module.
Covers: variant databases, single-trait PRS, multi-trait PRS,
        inflammatory baseline, ancestry adjustment, and edge cases.

Run: pytest tests/test_engine/test_prs_calculator.py -v
"""

import pytest
from engine.annotators.prs_calculator import (
    PRS_VARIANTS,
    calculate_prs,
    calculate_single_trait_prs,
    get_inflammatory_baseline,
    _extract_rsid,
    _get_dosage,
    _normalize_prs,
    _percentile_to_category,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Test PRS Variant Database
# ═══════════════════════════════════════════════════════════════════════════════

class TestPRSVariantDatabase:
    """Validate the PRS variant database structure."""

    def test_three_traits_present(self):
        assert "insulin_resistance" in PRS_VARIANTS
        assert "autoimmune_thyroiditis" in PRS_VARIANTS
        assert "systemic_inflammation" in PRS_VARIANTS

    @pytest.mark.parametrize("trait", list(PRS_VARIANTS.keys()))
    def test_trait_has_required_fields(self, trait):
        t = PRS_VARIANTS[trait]
        assert "trait_name" in t
        assert "abbreviation" in t
        assert "variants" in t
        assert len(t["variants"]) >= 6
        assert "population_mean" in t
        assert "population_sd" in t
        assert t["population_sd"] > 0
        assert "ancestry_adjustments" in t

    @pytest.mark.parametrize("trait", list(PRS_VARIANTS.keys()))
    def test_variants_have_required_fields(self, trait):
        for rsid, info in PRS_VARIANTS[trait]["variants"].items():
            assert rsid.startswith("rs"), f"{rsid} should start with rs"
            assert "effect_allele" in info
            assert "beta" in info
            assert info["beta"] > 0
            assert "gene" in info
            assert "source" in info

    def test_insulin_resistance_has_12_variants(self):
        assert len(PRS_VARIANTS["insulin_resistance"]["variants"]) == 12

    def test_autoimmune_thyroiditis_has_8_variants(self):
        assert len(PRS_VARIANTS["autoimmune_thyroiditis"]["variants"]) == 8

    def test_systemic_inflammation_has_10_variants(self):
        assert len(PRS_VARIANTS["systemic_inflammation"]["variants"]) == 10

    @pytest.mark.parametrize("trait", list(PRS_VARIANTS.keys()))
    def test_ancestry_adjustments_complete(self, trait):
        adj = PRS_VARIANTS[trait]["ancestry_adjustments"]
        for ancestry in ["African", "Caucasian", "Hispanic", "Asian", "Unknown"]:
            assert ancestry in adj
            assert adj[ancestry] > 0
        assert adj["Caucasian"] == 1.0  # Reference population


# ═══════════════════════════════════════════════════════════════════════════════
# Test Helper Functions
# ═══════════════════════════════════════════════════════════════════════════════

class TestHelperFunctions:
    """Test internal utility functions."""

    def test_extract_rsid_simple(self):
        assert _extract_rsid({"rsid": "rs7903146"}) == "rs7903146"

    def test_extract_rsid_with_allele(self):
        assert _extract_rsid({"rsid": "rs7903146_T"}) == "rs7903146"

    def test_extract_rsid_empty(self):
        assert _extract_rsid({}) == ""
        assert _extract_rsid({"rsid": ""}) == ""

    def test_get_dosage_het(self):
        assert _get_dosage({"zygosity": "HET"}) == 1
        assert _get_dosage({"zygosity": "HETEROZYGOUS"}) == 1
        assert _get_dosage({"zygosity": "0/1"}) == 1

    def test_get_dosage_hom(self):
        assert _get_dosage({"zygosity": "HOM"}) == 2
        assert _get_dosage({"zygosity": "HOMOZYGOUS"}) == 2
        assert _get_dosage({"zygosity": "1/1"}) == 2

    def test_get_dosage_unknown(self):
        assert _get_dosage({}) == 1  # Default to HET

    def test_normalize_prs_center(self):
        """Score at population mean should normalize to ~0.5."""
        result = _normalize_prs(0.65, 0.65, 0.35)
        assert 0.45 <= result <= 0.55

    def test_normalize_prs_high(self):
        """Score well above mean should normalize > 0.8."""
        result = _normalize_prs(1.5, 0.65, 0.35)
        assert result > 0.8

    def test_normalize_prs_low(self):
        """Score well below mean should normalize < 0.2."""
        result = _normalize_prs(0.0, 0.65, 0.35)
        assert result < 0.2

    def test_normalize_prs_zero_sd(self):
        """Zero SD should return 0.5."""
        assert _normalize_prs(1.0, 0.5, 0.0) == 0.5

    def test_percentile_to_category_high(self):
        assert _percentile_to_category(0.85) == "HIGH"
        assert _percentile_to_category(0.70) == "HIGH"

    def test_percentile_to_category_moderate(self):
        assert _percentile_to_category(0.55) == "MODERATE"
        assert _percentile_to_category(0.40) == "MODERATE"

    def test_percentile_to_category_low(self):
        assert _percentile_to_category(0.20) == "LOW"
        assert _percentile_to_category(0.0) == "LOW"


# ═══════════════════════════════════════════════════════════════════════════════
# Test Single Trait PRS
# ═══════════════════════════════════════════════════════════════════════════════

class TestSingleTraitPRS:
    """Test calculate_single_trait_prs function."""

    def test_unknown_trait_returns_none(self):
        assert calculate_single_trait_prs("fake_trait", [], "Unknown") is None

    def test_empty_variants_returns_low_score(self):
        result = calculate_single_trait_prs("insulin_resistance", [], "Caucasian")
        assert result is not None
        assert result["raw_score"] == 0.0
        assert result["variants_found"] == 0

    def test_single_matching_variant_het(self):
        variants = [{"rsid": "rs7903146", "zygosity": "HET"}]
        result = calculate_single_trait_prs("insulin_resistance", variants, "Caucasian")
        assert result is not None
        assert result["variants_found"] == 1
        assert result["raw_score"] == 0.30  # beta = 0.30, dosage = 1

    def test_single_matching_variant_hom(self):
        variants = [{"rsid": "rs7903146", "zygosity": "HOM"}]
        result = calculate_single_trait_prs("insulin_resistance", variants, "Caucasian")
        assert result is not None
        assert result["raw_score"] == 0.60  # beta = 0.30, dosage = 2

    def test_multiple_variants_additive(self):
        variants = [
            {"rsid": "rs7903146", "zygosity": "HET"},  # beta 0.30
            {"rsid": "rs1801282", "zygosity": "HET"},  # beta 0.15
        ]
        result = calculate_single_trait_prs("insulin_resistance", variants, "Caucasian")
        assert result is not None
        assert result["raw_score"] == pytest.approx(0.45, abs=0.01)
        assert result["variants_found"] == 2

    def test_result_has_all_fields(self):
        variants = [{"rsid": "rs7903146", "zygosity": "HET"}]
        result = calculate_single_trait_prs("insulin_resistance", variants, "Caucasian")
        for key in [
            "trait", "abbreviation", "prs_score", "risk_percentile",
            "risk_category", "raw_score", "adjusted_score",
            "ancestry_adjustment", "variants_found", "variants_total",
            "top_variants", "all_contributing_variants",
        ]:
            assert key in result

    def test_top_variants_sorted_by_contribution(self):
        variants = [
            {"rsid": "rs780094", "zygosity": "HET"},    # beta 0.10
            {"rsid": "rs7903146", "zygosity": "HET"},   # beta 0.30 (highest)
            {"rsid": "rs1801282", "zygosity": "HET"},   # beta 0.15
        ]
        result = calculate_single_trait_prs("insulin_resistance", variants, "Caucasian")
        contribs = result["all_contributing_variants"]
        assert contribs[0]["rsid"] == "rs7903146"  # highest contribution first

    def test_case_insensitive_rsid(self):
        variants = [{"rsid": "RS7903146", "zygosity": "HET"}]
        result = calculate_single_trait_prs("insulin_resistance", variants, "Caucasian")
        assert result["variants_found"] == 1

    def test_trait_name_normalization(self):
        """Spaces and capitalization should be handled."""
        variants = [{"rsid": "rs7903146", "zygosity": "HET"}]
        result = calculate_single_trait_prs("Insulin Resistance", variants, "Caucasian")
        assert result is not None


# ═══════════════════════════════════════════════════════════════════════════════
# Test Ancestry Adjustment
# ═══════════════════════════════════════════════════════════════════════════════

class TestAncestryAdjustment:
    """Test ancestry-based PRS adjustments."""

    def test_caucasian_no_adjustment(self):
        variants = [{"rsid": "rs7903146", "zygosity": "HET"}]
        result = calculate_single_trait_prs("insulin_resistance", variants, "Caucasian")
        assert result["ancestry_adjustment"] == 1.0
        assert result["raw_score"] == result["adjusted_score"]

    def test_african_adjustment_applied(self):
        variants = [{"rsid": "rs7903146", "zygosity": "HET"}]
        result = calculate_single_trait_prs("insulin_resistance", variants, "African")
        assert result["ancestry_adjustment"] == 0.85
        assert result["adjusted_score"] == pytest.approx(0.30 * 0.85, abs=0.01)

    def test_unknown_ancestry_neutral(self):
        variants = [{"rsid": "rs7903146", "zygosity": "HET"}]
        result = calculate_single_trait_prs("insulin_resistance", variants, "Unknown")
        assert result["ancestry_adjustment"] == 1.0

    @pytest.mark.parametrize("ancestry", ["African", "Caucasian", "Hispanic", "Asian"])
    def test_all_ancestries_produce_results(self, ancestry):
        variants = [{"rsid": "rs7903146", "zygosity": "HET"}]
        result = calculate_single_trait_prs("insulin_resistance", variants, ancestry)
        assert result is not None
        assert result["prs_score"] > 0


# ═══════════════════════════════════════════════════════════════════════════════
# Test Full PRS Calculation
# ═══════════════════════════════════════════════════════════════════════════════

class TestCalculatePRS:
    """Test the multi-trait PRS calculator."""

    def test_empty_variants(self):
        result = calculate_prs([], "Caucasian")
        assert result is not None
        assert result["traits_calculated"] == 3
        assert "inflammatory_cytokine_baseline" in result

    def test_all_three_traits_calculated(self):
        variants = [
            {"rsid": "rs7903146", "zygosity": "HET"},  # insulin_resistance
            {"rsid": "rs2476601", "zygosity": "HET"},  # autoimmune_thyroiditis
            {"rsid": "rs2794520", "zygosity": "HET"},  # systemic_inflammation
        ]
        result = calculate_prs(variants, "Caucasian")
        assert "insulin_resistance" in result["trait_scores"]
        assert "autoimmune_thyroiditis" in result["trait_scores"]
        assert "systemic_inflammation" in result["trait_scores"]

    def test_clinical_summary_present(self):
        variants = [{"rsid": "rs7903146", "zygosity": "HET"}]
        result = calculate_prs(variants, "Caucasian")
        assert "clinical_summary" in result
        assert len(result["clinical_summary"]) > 20

    def test_ancestry_passed_through(self):
        variants = [{"rsid": "rs7903146", "zygosity": "HET"}]
        result = calculate_prs(variants, "Hispanic")
        assert result["ancestry_used"] == "Hispanic"


# ═══════════════════════════════════════════════════════════════════════════════
# Test Inflammatory Baseline
# ═══════════════════════════════════════════════════════════════════════════════

class TestInflammatoryBaseline:
    """Test the inflammatory cytokine baseline indicator."""

    def test_no_inflammation_data_returns_moderate(self):
        assert get_inflammatory_baseline({}) == "MODERATE"

    def test_high_inflammation_score(self):
        results = {
            "systemic_inflammation": {"prs_score": 0.85}
        }
        assert get_inflammatory_baseline(results) == "HIGH"

    def test_moderate_inflammation_score(self):
        results = {
            "systemic_inflammation": {"prs_score": 0.55}
        }
        assert get_inflammatory_baseline(results) == "MODERATE"

    def test_low_inflammation_score(self):
        results = {
            "systemic_inflammation": {"prs_score": 0.20}
        }
        assert get_inflammatory_baseline(results) == "LOW"

    def test_boundary_high(self):
        results = {"systemic_inflammation": {"prs_score": 0.70}}
        assert get_inflammatory_baseline(results) == "HIGH"

    def test_boundary_moderate(self):
        results = {"systemic_inflammation": {"prs_score": 0.40}}
        assert get_inflammatory_baseline(results) == "MODERATE"


# ═══════════════════════════════════════════════════════════════════════════════
# Test Edge Cases
# ═══════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_variant_with_no_rsid(self):
        variants = [{"genes": ["TCF7L2"], "zygosity": "HET"}]
        result = calculate_prs(variants, "Caucasian")
        assert result is not None  # Should not crash

    def test_duplicate_rsids(self):
        variants = [
            {"rsid": "rs7903146", "zygosity": "HET"},
            {"rsid": "rs7903146", "zygosity": "HET"},
        ]
        result = calculate_single_trait_prs("insulin_resistance", variants, "Caucasian")
        # Second occurrence overwrites first in dict — dosage from last one used
        assert result["variants_found"] == 1

    def test_rsid_with_allele_suffix(self):
        variants = [{"rsid": "rs7903146_T", "zygosity": "HET"}]
        result = calculate_single_trait_prs("insulin_resistance", variants, "Caucasian")
        assert result["variants_found"] == 1

    def test_all_variants_present_high_risk(self):
        """If all 12 insulin_resistance variants present HET, score should be HIGH."""
        all_rsids = list(PRS_VARIANTS["insulin_resistance"]["variants"].keys())
        variants = [{"rsid": rsid, "zygosity": "HET"} for rsid in all_rsids]
        result = calculate_single_trait_prs("insulin_resistance", variants, "Caucasian")
        assert result["variants_found"] == 12
        assert result["risk_category"] == "HIGH"

    def test_prs_score_bounded_0_1(self):
        """PRS score should always be between 0 and 1."""
        all_rsids = list(PRS_VARIANTS["insulin_resistance"]["variants"].keys())
        variants = [{"rsid": rsid, "zygosity": "HOM"} for rsid in all_rsids]
        result = calculate_single_trait_prs("insulin_resistance", variants, "Caucasian")
        assert 0.0 <= result["prs_score"] <= 1.0

    def test_high_inflammation_triggers_clinical_advice(self):
        """HIGH inflammatory baseline should mention CRP/IL-6 in summary."""
        all_rsids = list(PRS_VARIANTS["systemic_inflammation"]["variants"].keys())
        variants = [{"rsid": rsid, "zygosity": "HOM"} for rsid in all_rsids]
        result = calculate_prs(variants, "Caucasian")
        if result["inflammatory_cytokine_baseline"] == "HIGH":
            assert "CRP" in result["clinical_summary"] or "inflammatory" in result["clinical_summary"].lower()
