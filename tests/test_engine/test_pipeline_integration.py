"""
Integration tests for engine/pipeline.py
All external API calls are mocked. Tests verify that the pipeline
produces correct output shape and ordering.
"""

import pytest
import responses as resp_lib

from engine import run_pipeline, annotate_variant

# ---------------------------------------------------------------------------
# Mock responses
# ---------------------------------------------------------------------------

VEP_URL     = "https://rest.ensembl.org/vep/human/region"
SEARCH_URL  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
SUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
GNOMAD_URL  = "https://gnomad.broadinstitute.org/api/"
MV_URL      = "https://myvariant.info/v1/query"

VEP_PATHOGENIC = [{
    "most_severe_consequence": "missense_variant",
    "transcript_consequences": [
        {"gene_symbol": "BRCA1", "consequence_terms": ["missense_variant"],
         "flags": ["mane_select"], "canonical": 1}
    ],
    "colocated_variants": [
        {"id": "rs80357906", "clin_sig": ["pathogenic"], "phenotype_or_disease": 1}
    ],
}]

CLINVAR_SEARCH   = {"esearchresult": {"idlist": ["12345"]}}
CLINVAR_SUMMARY  = {
    "result": {"12345": {
        "clinical_significance": {"description": "Pathogenic"},
        "trait_set": [{"trait_name": "Hereditary breast ovarian cancer"}],
    }}
}

GNOMAD_RESULT = {
    "data": {"variant": {
        "genome": {"af": 0.00001, "ac": 2, "an": 200000,
                   "homozygote_count": 0, "popmax": {"af": 0.00002}},
        "exome": None,
    }}
}


def _register_happy_path(rsps):
    rsps.add(rsps.POST, VEP_URL,     json=VEP_PATHOGENIC,  status=200)
    rsps.add(rsps.GET,  SEARCH_URL,  json=CLINVAR_SEARCH,   status=200)
    rsps.add(rsps.GET,  SUMMARY_URL, json=CLINVAR_SUMMARY,  status=200)
    rsps.add(rsps.POST, GNOMAD_URL,  json=GNOMAD_RESULT,    status=200)


# ---------------------------------------------------------------------------
# CSV pipeline (coordinate variants — no rsID resolution needed)
# ---------------------------------------------------------------------------

_CSV_ONE_VARIANT = b"chrom,pos,ref,alt,rsid\n17,41276045,A,G,rs80357906\n"


@resp_lib.activate
def test_pipeline_csv_returns_results():
    _register_happy_path(resp_lib)
    output = run_pipeline(_CSV_ONE_VARIANT, "test.csv")
    assert isinstance(output, dict)
    assert "variants" in output
    assert len(output["variants"]) == 1


@resp_lib.activate
def test_pipeline_result_has_all_required_fields():
    _register_happy_path(resp_lib)
    output = run_pipeline(_CSV_ONE_VARIANT, "test.csv")
    r = output["variants"][0]

    required = [
        "variant_id", "rsid", "location", "consequence", "genes",
        "clinvar", "disease_name", "gnomad_af", "score", "tier", "reasons",
        "clinvar_raw", "frequency_derived_label", "carrier_note",
        "emoji", "headline", "consequence_plain", "rarity_plain",
        "clinvar_plain", "action_hint", "zygosity_plain",
    ]
    for field in required:
        assert field in r, f"Missing field: {field}"


@resp_lib.activate
def test_pipeline_result_gene_not_na():
    _register_happy_path(resp_lib)
    output = run_pipeline(_CSV_ONE_VARIANT, "test.csv")
    results = output["variants"]
    assert results[0]["genes"] != ["N/A"]
    assert "BRCA1" in results[0]["genes"]


@resp_lib.activate
def test_pipeline_pathogenic_scores_critical():
    _register_happy_path(resp_lib)
    output = run_pipeline(_CSV_ONE_VARIANT, "test.csv")
    results = output["variants"]
    assert results[0]["tier"] == "critical"
    assert results[0]["score"] == 1000


@resp_lib.activate
def test_pipeline_sorted_by_score_descending():
    # Two variants — pathogenic first, then benign
    csv = (
        b"chrom,pos,ref,alt,rsid\n"
        b"17,41276045,A,G,rs80357906\n"
        b"1,100,A,T,rs1\n"
    )
    # First variant: pathogenic
    resp_lib.add(resp_lib.POST, VEP_URL, json=VEP_PATHOGENIC, status=200)
    resp_lib.add(resp_lib.GET,  SEARCH_URL,  json=CLINVAR_SEARCH,  status=200)
    resp_lib.add(resp_lib.GET,  SUMMARY_URL, json=CLINVAR_SUMMARY, status=200)
    resp_lib.add(resp_lib.POST, GNOMAD_URL,  json=GNOMAD_RESULT,   status=200)

    # Second variant: benign
    resp_lib.add(resp_lib.POST, VEP_URL, json=[{
        "most_severe_consequence": "synonymous_variant",
        "transcript_consequences": [
            {"gene_symbol": "GENE2", "consequence_terms": ["synonymous_variant"],
             "canonical": 1, "flags": []}
        ],
        "colocated_variants": [],
    }], status=200)
    resp_lib.add(resp_lib.GET,  SEARCH_URL,
                 json={"esearchresult": {"idlist": ["99999"]}}, status=200)
    resp_lib.add(resp_lib.GET,  SUMMARY_URL, json={
        "result": {"99999": {
            "clinical_significance": {"description": "Benign"},
            "trait_set": [],
        }}
    }, status=200)
    resp_lib.add(resp_lib.POST, GNOMAD_URL, json={
        "data": {"variant": {
            "genome": {"af": 0.15, "ac": 30000, "an": 200000,
                       "homozygote_count": 4000, "popmax": {"af": 0.20}},
            "exome": None,
        }}
    }, status=200)

    results = run_pipeline(csv, "test.csv")
    variants = results["variants"]
    assert len(variants) == 2
    assert variants[0]["score"] >= variants[1]["score"]


# ---------------------------------------------------------------------------
# Validation errors propagate
# ---------------------------------------------------------------------------

def test_pipeline_rejects_empty_file():
    with pytest.raises(ValueError, match="empty"):
        run_pipeline(b"", "test.csv")


def test_pipeline_rejects_invalid_vcf_header():
    with pytest.raises(ValueError, match="VCF"):
        run_pipeline(b"not a vcf header\ndata\n", "test.vcf")


def test_pipeline_rejects_oversized_file():
    big = b"x" * (101 * 1024 * 1024)
    with pytest.raises(ValueError, match="100 MB"):
        run_pipeline(big, "test.csv")


# ---------------------------------------------------------------------------
# No duplicate results
# ---------------------------------------------------------------------------

@resp_lib.activate
def test_pipeline_no_duplicate_results():
    """Same variant appearing twice in CSV should produce one result."""
    csv = (
        b"chrom,pos,ref,alt,rsid\n"
        b"17,41276045,A,G,rs80357906\n"
        b"17,41276045,A,G,rs80357906\n"  # exact duplicate
    )
    _register_happy_path(resp_lib)
    output = run_pipeline(csv, "test.csv")
    assert len(output["variants"]) == 1


# ---------------------------------------------------------------------------
# annotate_variant standalone
# ---------------------------------------------------------------------------

@resp_lib.activate
def test_annotate_variant_standalone():
    _register_happy_path(resp_lib)
    v = {
        "chrom": "17", "pos": 41276045, "ref": "A", "alt": "G",
        "rsid": "rs80357906", "variant_type": "coordinate",
        "genotype": None, "zygosity": "heterozygous", "gq": None, "dp": None,
    }
    result = annotate_variant(v)
    assert result["clinvar"] == "pathogenic"
    assert "BRCA1" in result["genes"]
    assert result["gnomad_af"] is not None


# ---------------------------------------------------------------------------
# V3 enrichment keys present
# ---------------------------------------------------------------------------

@resp_lib.activate
def test_pipeline_returns_bpc157_prediction():
    _register_happy_path(resp_lib)
    output = run_pipeline(_CSV_ONE_VARIANT, "test.csv")
    assert "bpc157_prediction" in output
    bpc = output["bpc157_prediction"]
    assert "responder_tier" in bpc
    assert "disclaimer" in bpc
    assert "NOT FDA-approved" in bpc["disclaimer"]


@resp_lib.activate
def test_pipeline_returns_peptide_recommendations():
    _register_happy_path(resp_lib)
    output = run_pipeline(_CSV_ONE_VARIANT, "test.csv")
    assert "peptide_recommendations" in output
    pr = output["peptide_recommendations"]
    assert "recommendations" in pr
    assert "summary_text" in pr
    assert isinstance(pr["recommendations"], list)
    assert len(pr["recommendations"]) > 0


@resp_lib.activate
def test_pipeline_returns_all_v3_keys():
    _register_happy_path(resp_lib)
    output = run_pipeline(_CSV_ONE_VARIANT, "test.csv")
    for key in ["variants", "pathway_summary", "receptor_genetics",
                "prs_profile", "ar_cag_repeat", "bpc157_prediction",
                "peptide_recommendations"]:
        assert key in output, f"Missing V3 key: {key}"
