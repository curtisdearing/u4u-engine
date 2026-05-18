"""
tests/test_engine/test_receptor_mapper.py
==========================================
Unit tests for the receptor genetics mapper module.
Covers: registry validation, expression prediction, isoform logic,
        clinical interpretation, map_receptors, and edge cases.

Run: pytest tests/test_engine/test_receptor_mapper.py -v
"""

import pytest
from engine.annotators.receptor_mapper import (
    RECEPTOR_REGISTRY,
    predict_receptor_expression,
    map_receptors,
    generate_receptor_summary,
    _compute_expression_level,
    _determine_dominant_isoform,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Test Registry Validation
# ═══════════════════════════════════════════════════════════════════════════════

class TestReceptorRegistry:
    """Validate the receptor registry data structure."""

    def test_registry_has_minimum_receptors(self):
        assert len(RECEPTOR_REGISTRY) >= 8

    @pytest.mark.parametrize("gene", [
        "ESR1", "ESR2", "GLP1R", "MC4R", "OXTR", "AR", "GPER1", "FSHR",
    ])
    def test_all_expected_receptors_present(self, gene):
        assert gene in RECEPTOR_REGISTRY

    @pytest.mark.parametrize("gene", list(RECEPTOR_REGISTRY.keys()))
    def test_receptor_has_required_fields(self, gene):
        rec = RECEPTOR_REGISTRY[gene]
        assert "full_name" in rec
        assert "pathway" in rec
        assert "peptide_relevance" in rec
        assert "isoforms" in rec
        assert len(rec["isoforms"]) >= 1
        assert "expression_modifiers" in rec

    @pytest.mark.parametrize("gene", list(RECEPTOR_REGISTRY.keys()))
    def test_isoforms_have_required_fields(self, gene):
        for iso in RECEPTOR_REGISTRY[gene]["isoforms"]:
            assert "name" in iso
            assert "description" in iso
            assert "function" in iso
            assert "default_expression" in iso
            assert iso["default_expression"] in ("HIGH", "NORMAL", "LOW")

    @pytest.mark.parametrize("gene", list(RECEPTOR_REGISTRY.keys()))
    def test_modifiers_have_valid_direction(self, gene):
        for rsid, mod in RECEPTOR_REGISTRY[gene]["expression_modifiers"].items():
            assert mod["direction"] in ("up", "down", "variable")
            assert mod["magnitude"] in ("strong", "moderate", "mild")


# ═══════════════════════════════════════════════════════════════════════════════
# Test Expression Level Computation
# ═══════════════════════════════════════════════════════════════════════════════

class TestExpressionLevel:
    """Test the expression level scoring logic."""

    def test_no_modifiers_returns_base(self):
        assert _compute_expression_level("NORMAL", []) == "NORMAL"

    def test_single_strong_up_returns_high(self):
        mods = [{"direction": "up", "magnitude": "strong"}]
        assert _compute_expression_level("NORMAL", mods) == "HIGH"

    def test_single_strong_down_returns_low(self):
        mods = [{"direction": "down", "magnitude": "strong"}]
        assert _compute_expression_level("NORMAL", mods) == "LOW"

    def test_moderate_up_returns_high(self):
        mods = [{"direction": "up", "magnitude": "moderate"}]
        assert _compute_expression_level("NORMAL", mods) == "HIGH"

    def test_two_mild_up_returns_high(self):
        mods = [
            {"direction": "up", "magnitude": "mild"},
            {"direction": "up", "magnitude": "mild"},
        ]
        assert _compute_expression_level("NORMAL", mods) == "HIGH"

    def test_opposing_modifiers_cancel(self):
        mods = [
            {"direction": "up", "magnitude": "moderate"},
            {"direction": "down", "magnitude": "moderate"},
        ]
        assert _compute_expression_level("NORMAL", mods) == "NORMAL"

    def test_mild_single_returns_normal(self):
        mods = [{"direction": "up", "magnitude": "mild"}]
        assert _compute_expression_level("NORMAL", mods) == "NORMAL"

    def test_variable_direction_neutral(self):
        mods = [{"direction": "variable", "magnitude": "strong"}]
        assert _compute_expression_level("NORMAL", mods) == "NORMAL"


# ═══════════════════════════════════════════════════════════════════════════════
# Test Isoform Prediction
# ═══════════════════════════════════════════════════════════════════════════════

class TestIsoformPrediction:
    """Test dominant isoform determination."""

    def test_no_shift_returns_first_isoform(self):
        isoforms = [
            {"name": "ISO-A", "default_expression": "NORMAL"},
            {"name": "ISO-B", "default_expression": "LOW"},
        ]
        mods = [{"direction": "up", "magnitude": "moderate", "isoform_shift": None}]
        result = _determine_dominant_isoform(isoforms, mods)
        assert result["name"] == "ISO-A"

    def test_shift_selects_target_isoform(self):
        isoforms = [
            {"name": "ISO-A", "default_expression": "NORMAL"},
            {"name": "ISO-B", "default_expression": "LOW"},
        ]
        mods = [{"direction": "up", "magnitude": "moderate", "isoform_shift": "ISO-B"}]
        result = _determine_dominant_isoform(isoforms, mods)
        assert result["name"] == "ISO-B"

    def test_empty_modifiers_returns_first(self):
        isoforms = [{"name": "ISO-A", "default_expression": "NORMAL"}]
        result = _determine_dominant_isoform(isoforms, [])
        assert result["name"] == "ISO-A"

    def test_empty_isoforms_returns_empty(self):
        result = _determine_dominant_isoform([], [])
        assert result == {}


# ═══════════════════════════════════════════════════════════════════════════════
# Test predict_receptor_expression
# ═══════════════════════════════════════════════════════════════════════════════

class TestPredictReceptorExpression:
    """Test the single-receptor prediction function."""

    def test_unknown_gene_returns_none(self):
        assert predict_receptor_expression("FAKE_GENE", ["rs123"]) is None

    def test_esr1_with_known_variant(self):
        result = predict_receptor_expression("ESR1", ["rs2228480"])
        assert result is not None
        assert result["receptor_gene"] == "ESR1"
        assert result["expression_level"] in ("HIGH", "NORMAL", "LOW")
        assert len(result["isoform_predictions"]) >= 1
        assert result["variants_affecting"] == ["rs2228480"]

    def test_esr1_with_allele_suffix(self):
        """rsIDs with _allele suffix should be cleaned."""
        result = predict_receptor_expression("ESR1", ["rs2228480_C"])
        assert result is not None
        assert "rs2228480_C" in result["variants_affecting"]

    def test_glp1r_high_expression(self):
        result = predict_receptor_expression("GLP1R", ["rs6923761"])
        assert result is not None
        assert result["expression_level"] == "HIGH"
        assert "GLP-1" in result["clinical_interpretation"]

    def test_case_insensitive_gene(self):
        result = predict_receptor_expression("esr1", ["rs2228480"])
        assert result is not None
        assert result["receptor_gene"] == "ESR1"

    def test_no_matching_variants(self):
        result = predict_receptor_expression("ESR1", ["rs9999999"])
        assert result is not None
        assert result["expression_level"] == "NORMAL"
        assert result["variants_affecting"] == []

    def test_result_has_all_required_fields(self):
        result = predict_receptor_expression("MC4R", ["rs17782313"])
        assert result is not None
        for key in [
            "receptor_gene", "receptor_name", "pathway",
            "expression_level", "isoform_predictions",
            "variants_affecting", "peptide_relevance",
            "clinical_interpretation",
        ]:
            assert key in result

    def test_isoform_predictions_structure(self):
        result = predict_receptor_expression("ESR1", ["rs2228480"])
        for iso in result["isoform_predictions"]:
            assert "isoform" in iso
            assert "expression_level" in iso
            assert "functional_prediction" in iso
            assert "is_dominant" in iso

    def test_esr2_reduced_expression(self):
        result = predict_receptor_expression("ESR2", ["rs1256049"])
        assert result is not None
        # Mild down should not cross threshold to LOW
        assert result["expression_level"] == "NORMAL"


# ═══════════════════════════════════════════════════════════════════════════════
# Test map_receptors (Main Entry Point)
# ═══════════════════════════════════════════════════════════════════════════════

class TestMapReceptors:
    """Test the main mapping function with variant lists."""

    def test_empty_variants(self):
        assert map_receptors([]) == []

    def test_single_variant_esr1(self):
        variants = [{"genes": ["ESR1"], "rsid": "rs2228480"}]
        results = map_receptors(variants)
        assert len(results) >= 1
        assert results[0]["receptor_gene"] == "ESR1"

    def test_multiple_genes(self):
        variants = [
            {"genes": ["ESR1"], "rsid": "rs2228480"},
            {"genes": ["GLP1R"], "rsid": "rs6923761"},
        ]
        results = map_receptors(variants)
        genes = [r["receptor_gene"] for r in results]
        assert "ESR1" in genes
        assert "GLP1R" in genes

    def test_variant_with_string_genes(self):
        """genes field as string instead of list."""
        variants = [{"genes": "ESR1", "rsid": "rs2228480"}]
        results = map_receptors(variants)
        assert len(results) >= 1

    def test_sorting_high_first(self):
        variants = [
            {"genes": ["MC4R"], "rsid": "rs17782313"},  # likely NORMAL or LOW
            {"genes": ["GLP1R"], "rsid": "rs6923761"},  # HIGH
        ]
        results = map_receptors(variants)
        if len(results) >= 2:
            # HIGH should sort before NORMAL/LOW
            levels = [r["expression_level"] for r in results]
            if "HIGH" in levels:
                assert levels[0] == "HIGH" or levels.index("HIGH") == 0

    def test_no_matching_receptors(self):
        variants = [{"genes": ["BRCA1"], "rsid": "rs80357906"}]
        results = map_receptors(variants)
        assert results == []

    def test_rsid_matches_modifier_directly(self):
        """rsID in variant should match modifier even if gene isn't listed."""
        variants = [{"genes": [], "rsid": "rs6923761"}]
        results = map_receptors(variants)
        genes = [r["receptor_gene"] for r in results]
        assert "GLP1R" in genes

    def test_deduplication(self):
        """Same gene/rsid appearing twice shouldn't create duplicate profiles."""
        variants = [
            {"genes": ["ESR1"], "rsid": "rs2228480"},
            {"genes": ["ESR1"], "rsid": "rs2228480"},
        ]
        results = map_receptors(variants)
        esr1_count = sum(1 for r in results if r["receptor_gene"] == "ESR1")
        assert esr1_count == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Test generate_receptor_summary
# ═══════════════════════════════════════════════════════════════════════════════

class TestGenerateReceptorSummary:
    """Test narrative summary generation."""

    def test_empty_profiles(self):
        summary = generate_receptor_summary([])
        assert "No peptide-relevant receptor variants" in summary

    def test_high_expression_mentioned(self):
        profiles = [{
            "receptor_gene": "GLP1R",
            "receptor_name": "GLP-1 Receptor",
            "expression_level": "HIGH",
            "pathway": "Incretin Signaling",
        }]
        summary = generate_receptor_summary(profiles)
        assert "elevated" in summary.lower() or "enhanced" in summary.lower()
        assert "GLP-1 Receptor" in summary

    def test_low_expression_mentioned(self):
        profiles = [{
            "receptor_gene": "MC4R",
            "receptor_name": "Melanocortin-4 Receptor",
            "expression_level": "LOW",
            "pathway": "Melanocortin Signaling",
        }]
        summary = generate_receptor_summary(profiles)
        assert "reduced" in summary.lower() or "low" in summary.lower()

    def test_all_normal_message(self):
        profiles = [{
            "receptor_gene": "FSHR",
            "receptor_name": "FSH Receptor",
            "expression_level": "NORMAL",
            "pathway": "GnRH Downstream",
        }]
        summary = generate_receptor_summary(profiles)
        assert "normal" in summary.lower()

    def test_pathway_count_in_summary(self):
        profiles = [
            {"receptor_gene": "ESR1", "receptor_name": "ESR1", "expression_level": "HIGH", "pathway": "Estrogen"},
            {"receptor_gene": "GLP1R", "receptor_name": "GLP1R", "expression_level": "HIGH", "pathway": "Incretin"},
        ]
        summary = generate_receptor_summary(profiles)
        assert "2 receptor" in summary
        assert "2 signaling" in summary
