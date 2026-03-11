"""
Tests for engine/annotators/vep.py, clinvar.py, gnomad.py, myvariant.py
All external HTTP calls are mocked — no network required.
"""

import json
import pytest
import responses as resp_lib

from engine.annotators.vep      import fetch_vep, select_canonical_consequence
from engine.annotators.clinvar  import fetch_clinvar
from engine.annotators.gnomad   import fetch_gnomad
from engine.annotators.myvariant import fetch_myvariant


# ============================================================
# VEP
# ============================================================

_VEP_URL = "https://rest.ensembl.org/vep/human/region"

_VEP_RESPONSE = [{
    "most_severe_consequence": "missense_variant",
    "transcript_consequences": [
        {
            "gene_symbol": "BRCA1",
            "consequence_terms": ["missense_variant"],
            "canonical": 1,
            "flags": ["mane_select"],
        }
    ],
    "colocated_variants": [
        {
            "id": "rs80357906",
            "clin_sig": ["pathogenic"],
            "phenotype_or_disease": 1,
        }
    ],
}]


@resp_lib.activate
def test_fetch_vep_returns_result():
    resp_lib.add(resp_lib.POST, _VEP_URL, json=_VEP_RESPONSE, status=200)
    result = fetch_vep("17", 41276045, "A", "G")
    assert result is not None
    assert result["most_severe_consequence"] == "missense_variant"


@resp_lib.activate
def test_fetch_vep_extracts_fallback_clinvar():
    resp_lib.add(resp_lib.POST, _VEP_URL, json=_VEP_RESPONSE, status=200)
    result = fetch_vep("17", 41276045, "A", "G")
    assert result["_fallback_clinvar"]["clinical_significance"] == "pathogenic"


@resp_lib.activate
def test_fetch_vep_returns_none_on_failure():
    resp_lib.add(resp_lib.POST, _VEP_URL, json={}, status=500)
    result = fetch_vep("17", 41276045, "A", "G")
    assert result is None


def test_fetch_vep_invalid_coords_returns_none():
    result = fetch_vep("99", -1, "X", "Y")
    assert result is None


def test_select_canonical_mane_select():
    vep = {
        "most_severe_consequence": "missense_variant",
        "transcript_consequences": [
            {"gene_symbol": "BRCA1", "consequence_terms": ["missense_variant"],
             "flags": ["mane_select"], "canonical": 1},
            {"gene_symbol": "BRCA1", "consequence_terms": ["intron_variant"],
             "flags": [], "canonical": 0},
        ],
    }
    csq, genes = select_canonical_consequence(vep)
    assert csq == "missense_variant"
    assert "BRCA1" in genes


def test_select_canonical_falls_back_to_canonical():
    vep = {
        "most_severe_consequence": "stop_gained",
        "transcript_consequences": [
            {"gene_symbol": "TP53", "consequence_terms": ["stop_gained"],
             "flags": [], "canonical": 1},
        ],
    }
    csq, genes = select_canonical_consequence(vep)
    assert csq == "stop_gained"
    assert "TP53" in genes


def test_select_canonical_last_resort_fallback():
    vep = {
        "most_severe_consequence": "intergenic_variant",
        "transcript_consequences": [],
    }
    csq, genes = select_canonical_consequence(vep)
    assert csq == "intergenic_variant"
    assert genes == []


# ============================================================
# ClinVar
# ============================================================

_SEARCH_URL  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
_SUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

_SEARCH_RESPONSE = {"esearchresult": {"idlist": ["12345"]}}
_SUMMARY_RESPONSE = {
    "result": {
        "12345": {
            "clinical_significance": {"description": "Pathogenic"},
            "trait_set": [{"trait_name": "Hereditary breast ovarian cancer"}],
        }
    }
}


@resp_lib.activate
def test_fetch_clinvar_returns_pathogenic():
    resp_lib.add(resp_lib.GET, _SEARCH_URL,  json=_SEARCH_RESPONSE,  status=200)
    resp_lib.add(resp_lib.GET, _SUMMARY_URL, json=_SUMMARY_RESPONSE, status=200)
    result = fetch_clinvar("rs80357906")
    assert result is not None
    assert result["clinical_significance"] == "pathogenic"
    assert result["disease_name"] == "Hereditary breast ovarian cancer"


@resp_lib.activate
def test_fetch_clinvar_returns_none_when_not_found():
    resp_lib.add(resp_lib.GET, _SEARCH_URL, json={"esearchresult": {"idlist": []}}, status=200)
    result = fetch_clinvar("rs9999999999")
    assert result is None


def test_fetch_clinvar_invalid_rsid_returns_none():
    result = fetch_clinvar("not_an_rsid")
    assert result is None


def test_fetch_clinvar_none_rsid_returns_none():
    result = fetch_clinvar(None)
    assert result is None


# ============================================================
# gnomAD
# ============================================================

_GNOMAD_URL = "https://gnomad.broadinstitute.org/api/"

_GNOMAD_RESPONSE = {
    "data": {
        "variant": {
            "genome": {
                "af": 0.0023,
                "ac": 460,
                "an": 200000,
                "homozygote_count": 2,
                "popmax": {"af": 0.005},
            },
            "exome": None,
        }
    }
}


@resp_lib.activate
def test_fetch_gnomad_returns_af():
    resp_lib.add(resp_lib.POST, _GNOMAD_URL, json=_GNOMAD_RESPONSE, status=200)
    result = fetch_gnomad("17", 41276045, "A", "G")
    assert result is not None
    assert result["af"] == pytest.approx(0.0023)
    assert result["source"] == "genome"


@resp_lib.activate
def test_fetch_gnomad_r4_fallback_to_r2():
    # First call (r4) returns no variant; second call (r2.1) succeeds
    resp_lib.add(resp_lib.POST, _GNOMAD_URL,
                 json={"data": {"variant": None}}, status=200)
    resp_lib.add(resp_lib.POST, _GNOMAD_URL,
                 json=_GNOMAD_RESPONSE, status=200)
    result = fetch_gnomad("17", 41276045, "A", "G")
    assert result is not None
    assert result["dataset"] == "gnomad_r2_1"


@resp_lib.activate
def test_fetch_gnomad_returns_none_when_absent():
    resp_lib.add(resp_lib.POST, _GNOMAD_URL,
                 json={"data": {"variant": None}}, status=200)
    resp_lib.add(resp_lib.POST, _GNOMAD_URL,
                 json={"data": {"variant": None}}, status=200)
    result = fetch_gnomad("17", 41276045, "A", "G")
    assert result is None


def test_fetch_gnomad_invalid_coords_returns_none():
    result = fetch_gnomad("99", -1, "X", "Y")
    assert result is None


# ============================================================
# MyVariant.info (fallback)
# ============================================================

_MV_QUERY_URL = "https://myvariant.info/v1/query"

_MV_HIT = {
    "hits": [{
        "chrom": "17",
        "vcf": {"position": "41276045"},
        "clinvar": {
            "rcv": [{
                "clinical_significance": "Pathogenic",
                "conditions": {"name": "BRCA1 cancer"},
                "review_status": "reviewed_by_expert_panel",
            }]
        },
        "gnomad_exome": {
            "af": {"af": 0.0001, "popmax": 0.0003}
        },
    }]
}


@resp_lib.activate
def test_fetch_myvariant_by_rsid():
    resp_lib.add(resp_lib.GET, _MV_QUERY_URL, json=_MV_HIT, status=200)
    result = fetch_myvariant(rsid="rs80357906", chrom="17", pos=41276045)
    assert result is not None
    assert result["clinvar_classification"] == "pathogenic"
    assert result["gnomad_af"] == pytest.approx(0.0001)


@resp_lib.activate
def test_fetch_myvariant_returns_none_on_empty_hits():
    resp_lib.add(resp_lib.GET, _MV_QUERY_URL, json={"hits": []}, status=200)
    result = fetch_myvariant(rsid="rs0000000")
    assert result is None
