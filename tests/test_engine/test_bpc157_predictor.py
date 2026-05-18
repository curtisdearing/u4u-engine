"""
Unit tests for engine/annotators/bpc157_predictor.py

Tests verify pathway mapping, rsID modifier scoring, responder tier
assignment, biomarker selection, and summary generation.
"""

import pytest

from engine.annotators.bpc157_predictor import (
    predict_bpc157_response,
    generate_bpc157_summary,
    BPC157_PATHWAY_GENES,
    BPC157_MODIFIER_RSIDS,
    _DISCLAIMER,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_variant(genes, rsid=None, consequence="missense_variant"):
    """Create a minimal annotated variant dict."""
    return {
        "genes": genes if isinstance(genes, list) else [genes],
        "rsid": rsid,
        "consequence": consequence,
        "chrom": "1",
        "pos": 100,
        "ref": "A",
        "alt": "T",
        "zygosity": "heterozygous",
    }


# ---------------------------------------------------------------------------
# predict_bpc157_response — basic behavior
# ---------------------------------------------------------------------------

class TestPredictBpc157Response:

    def test_empty_variants_returns_low_confidence(self):
        result = predict_bpc157_response([])
        assert result["responder_tier"] == "low_confidence"
        assert result["composite_score"] == 0.0
        assert result["pathways_affected"] == []
        assert result["candidate_factors"] == []
        assert result["disclaimer"] == _DISCLAIMER

    def test_irrelevant_genes_return_low_confidence(self):
        variants = [_make_variant("BRCA1"), _make_variant("TP53")]
        result = predict_bpc157_response(variants)
        assert result["responder_tier"] == "low_confidence"
        assert result["pathways_affected"] == []

    def test_inflammatory_genes_trigger_pathways(self):
        variants = [
            _make_variant("IL6"),
            _make_variant("TNF"),
            _make_variant("CRP"),
        ]
        result = predict_bpc157_response(variants)
        pathway_keys = [p["pathway"] for p in result["pathways_affected"]]
        assert "inflammatory_cytokines" in pathway_keys
        assert result["composite_score"] > 0

    def test_gi_genes_trigger_gut_pathway(self):
        variants = [
            _make_variant("TJP1"),
            _make_variant("OCLN"),
        ]
        result = predict_bpc157_response(variants)
        pathway_keys = [p["pathway"] for p in result["pathways_affected"]]
        assert "gut_barrier" in pathway_keys
        assert result["primary_use_case"] == "gastrointestinal"

    def test_collagen_genes_trigger_tissue_pathway(self):
        variants = [
            _make_variant("COL1A1"),
            _make_variant("MMP9"),
        ]
        result = predict_bpc157_response(variants)
        pathway_keys = [p["pathway"] for p in result["pathways_affected"]]
        assert "collagen_tissue_repair" in pathway_keys

    def test_nos3_gene_triggers_no_pathway(self):
        variants = [_make_variant("NOS3")]
        result = predict_bpc157_response(variants)
        pathway_keys = [p["pathway"] for p in result["pathways_affected"]]
        assert "NO_eNOS_signaling" in pathway_keys

    def test_multiple_pathways_raises_score(self):
        """Variants hitting multiple pathways should score higher than one."""
        single = predict_bpc157_response([_make_variant("NOS3")])
        multi = predict_bpc157_response([
            _make_variant("NOS3"),
            _make_variant("IL6"),
            _make_variant("VEGFA"),
            _make_variant("COL1A1"),
        ])
        assert multi["composite_score"] > single["composite_score"]

    def test_disclaimer_always_present(self):
        for variants in [[], [_make_variant("NOS3")]]:
            result = predict_bpc157_response(variants)
            assert "NOT FDA-approved" in result["disclaimer"]
            assert len(result["disclaimer"]) > 100


# ---------------------------------------------------------------------------
# rsID modifier scoring
# ---------------------------------------------------------------------------

class TestRsidModifiers:

    def test_known_rsid_adds_candidate_factor(self):
        variants = [_make_variant("NOS3", rsid="rs1799983")]
        result = predict_bpc157_response(variants)
        assert len(result["candidate_factors"]) >= 1
        factor = result["candidate_factors"][0]
        assert factor["rsid"] == "rs1799983"
        assert factor["gene"] == "NOS3"
        assert factor["direction"] == "impaired"

    def test_inflammatory_rsids_boost_score(self):
        # Without modifier rsID
        base = predict_bpc157_response([_make_variant("IL6")])
        # With IL6 modifier rsID
        boosted = predict_bpc157_response([
            _make_variant("IL6", rsid="rs1800795"),
        ])
        assert boosted["composite_score"] > base["composite_score"]

    def test_unknown_rsid_ignored(self):
        variants = [_make_variant("NOS3", rsid="rs99999999")]
        result = predict_bpc157_response(variants)
        assert len(result["candidate_factors"]) == 0


# ---------------------------------------------------------------------------
# Responder tier assignment
# ---------------------------------------------------------------------------

class TestResponderTiers:

    def test_many_pathways_hit_is_likely_good(self):
        """Hitting many pathways with modifier rsIDs should yield likely_good."""
        variants = [
            _make_variant("NOS3", rsid="rs1799983"),  # NO + 1.5
            _make_variant("IL6", rsid="rs1800795"),    # inflammatory + 1.5
            _make_variant("VEGFA", rsid="rs2010963"),  # angiogenesis + 1.0
            _make_variant("COL1A1", rsid="rs1800012"), # collagen + 1.0
        ]
        result = predict_bpc157_response(variants)
        assert result["responder_tier"] == "likely_good"

    def test_single_pathway_is_uncertain_or_possible(self):
        result = predict_bpc157_response([_make_variant("NOS3")])
        assert result["responder_tier"] in ("uncertain", "possible", "low_confidence")

    def test_empty_is_low_confidence(self):
        result = predict_bpc157_response([])
        assert result["responder_tier"] == "low_confidence"


# ---------------------------------------------------------------------------
# Biomarker recommendations
# ---------------------------------------------------------------------------

class TestBiomarkers:

    def test_always_includes_core_inflammatory_and_safety(self):
        result = predict_bpc157_response([_make_variant("NOS3")])
        names = [b["name"] for b in result["biomarker_recommendations"]]
        assert "hs-CRP" in names
        assert "CBC with platelets" in names

    def test_gi_use_case_includes_gut_biomarkers(self):
        variants = [_make_variant("TJP1"), _make_variant("OCLN"), _make_variant("CDH1")]
        result = predict_bpc157_response(variants)
        names = [b["name"] for b in result["biomarker_recommendations"]]
        assert "Fecal calprotectin" in names
        assert "Serum zonulin" in names

    def test_msk_use_case_includes_tissue_markers(self):
        variants = [
            _make_variant("COL1A1", rsid="rs1800012"),
            _make_variant("GHR", rsid="rs6180"),
            _make_variant("MMP9", rsid="rs3918242"),
        ]
        result = predict_bpc157_response(variants)
        names = [b["name"] for b in result["biomarker_recommendations"]]
        assert "PIIINP (Procollagen III)" in names or "PINP (Procollagen I)" in names


# ---------------------------------------------------------------------------
# Summary generation
# ---------------------------------------------------------------------------

class TestGenerateSummary:

    def test_empty_prediction_returns_text(self):
        result = predict_bpc157_response([])
        assert len(result["summary_text"]) > 0
        assert "BPC-157" in result["summary_text"]

    def test_good_candidate_summary_mentions_likely(self):
        variants = [
            _make_variant("NOS3", rsid="rs1799983"),
            _make_variant("IL6", rsid="rs1800795"),
            _make_variant("VEGFA", rsid="rs2010963"),
            _make_variant("COL1A1", rsid="rs1800012"),
        ]
        result = predict_bpc157_response(variants)
        assert "LIKELY GOOD" in result["summary_text"]

    def test_summary_standalone_function(self):
        prediction = {
            "responder_tier": "possible",
            "pathways_affected": [{"pathway": "test", "genes_hit": ["NOS3"]}],
            "primary_use_case_display": "Musculoskeletal / Soft-Tissue Healing",
            "candidate_factors": [],
        }
        text = generate_bpc157_summary(prediction)
        assert len(text) > 0
        assert "POSSIBLE" in text

    def test_elevated_factors_mentioned(self):
        prediction = {
            "responder_tier": "likely_good",
            "pathways_affected": [{"pathway": "test"}],
            "primary_use_case_display": "Anti-Inflammatory / Recovery",
            "candidate_factors": [
                {"rsid": "rs1800795", "gene": "IL6", "direction": "elevated",
                 "effect": "test", "pathway": "inflammatory_cytokines"},
            ],
        }
        text = generate_bpc157_summary(prediction)
        assert "IL6" in text
        assert "anti-inflammatory" in text.lower()


# ---------------------------------------------------------------------------
# Pathway gene coverage
# ---------------------------------------------------------------------------

class TestPathwayData:

    def test_all_pathways_have_required_fields(self):
        for key, pathway in BPC157_PATHWAY_GENES.items():
            assert "display_name" in pathway, f"{key} missing display_name"
            assert "genes" in pathway, f"{key} missing genes"
            assert "relevance" in pathway, f"{key} missing relevance"
            assert "use_cases" in pathway, f"{key} missing use_cases"
            assert len(pathway["genes"]) > 0, f"{key} has empty gene set"

    def test_all_modifiers_reference_valid_pathways(self):
        for rsid, mod in BPC157_MODIFIER_RSIDS.items():
            assert mod["pathway"] in BPC157_PATHWAY_GENES, (
                f"Modifier {rsid} references unknown pathway: {mod['pathway']}"
            )

    def test_all_modifiers_reference_valid_genes(self):
        all_genes = set()
        for pathway in BPC157_PATHWAY_GENES.values():
            all_genes.update(pathway["genes"])
        for rsid, mod in BPC157_MODIFIER_RSIDS.items():
            assert mod["gene"] in all_genes, (
                f"Modifier {rsid} references gene {mod['gene']} not in any pathway"
            )


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_genes_as_string_not_list(self):
        """Some variants may have genes as a string instead of list."""
        variant = {
            "genes": "NOS3",  # string, not list
            "rsid": None,
            "consequence": "missense_variant",
        }
        result = predict_bpc157_response([variant])
        assert len(result["pathways_affected"]) > 0

    def test_missing_genes_key(self):
        variant = {"rsid": "rs1799983", "consequence": "missense_variant"}
        result = predict_bpc157_response([variant])
        # Should still pick up the rsID modifier
        assert len(result["candidate_factors"]) >= 1

    def test_rsid_with_underscore_suffix(self):
        """rsIDs sometimes have '_A' suffix in variant dicts."""
        variant = _make_variant("NOS3", rsid="rs1799983_A")
        result = predict_bpc157_response([variant])
        assert len(result["candidate_factors"]) >= 1
