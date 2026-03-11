"""Tests for engine/quality_filter.py"""

import pytest
from engine.quality_filter import apply_quality_filter, filter_stats, GQ_THRESHOLD, DP_THRESHOLD


def _v(**kwargs):
    """Build a minimal variant dict with defaults."""
    base = {
        "chrom": "1", "pos": 100, "ref": "A", "alt": "T",
        "rsid": "rs1", "variant_type": "coordinate",
        "genotype": "AT", "zygosity": "heterozygous",
        "gq": 30, "dp": 20,
    }
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# Rule 1: homozygous_ref
# ---------------------------------------------------------------------------

def test_drops_homozygous_ref():
    v = _v(zygosity="homozygous_ref")
    assert apply_quality_filter([v]) == []


def test_keeps_heterozygous():
    v = _v(zygosity="heterozygous")
    assert len(apply_quality_filter([v])) == 1


def test_keeps_homozygous_alt():
    v = _v(zygosity="homozygous_alt")
    assert len(apply_quality_filter([v])) == 1


# ---------------------------------------------------------------------------
# Rule 2: failed / indel genotype strings
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("genotype", ["--", "NN", ".", "-", "DI", "II", "DD"])
def test_drops_failed_genotype_strings(genotype):
    v = _v(genotype=genotype)
    assert apply_quality_filter([v]) == []


@pytest.mark.parametrize("genotype", ["DT", "TI", "ID"])
def test_drops_genotypes_containing_id(genotype):
    v = _v(genotype=genotype)
    assert apply_quality_filter([v]) == []


# ---------------------------------------------------------------------------
# Rule 3: GQ threshold
# ---------------------------------------------------------------------------

def test_drops_low_gq():
    v = _v(gq=GQ_THRESHOLD - 1)
    assert apply_quality_filter([v]) == []


def test_keeps_gq_at_threshold():
    v = _v(gq=GQ_THRESHOLD)
    assert len(apply_quality_filter([v])) == 1


def test_keeps_gq_none():
    # GQ absent (e.g. 23andMe variant) — should not be dropped by this rule
    v = _v(gq=None)
    assert len(apply_quality_filter([v])) == 1


# ---------------------------------------------------------------------------
# Rule 4: DP threshold
# ---------------------------------------------------------------------------

def test_drops_low_dp():
    v = _v(dp=DP_THRESHOLD - 1)
    assert apply_quality_filter([v]) == []


def test_keeps_dp_at_threshold():
    v = _v(dp=DP_THRESHOLD)
    assert len(apply_quality_filter([v])) == 1


def test_keeps_dp_none():
    v = _v(dp=None)
    assert len(apply_quality_filter([v])) == 1


# ---------------------------------------------------------------------------
# Rule 5: VCF indels (ref/alt length > 1)
# ---------------------------------------------------------------------------

def test_drops_insertion():
    v = _v(ref="A", alt="AT")
    assert apply_quality_filter([v]) == []


def test_drops_deletion():
    v = _v(ref="AT", alt="A")
    assert apply_quality_filter([v]) == []


def test_keeps_snv():
    v = _v(ref="A", alt="T")
    assert len(apply_quality_filter([v])) == 1


# ---------------------------------------------------------------------------
# Rule 6: anomalous 23andMe genotype
# ---------------------------------------------------------------------------

def test_drops_long_genotype_without_ref_alt():
    v = _v(ref=None, alt=None, genotype="ATCG")
    assert apply_quality_filter([v]) == []


# ---------------------------------------------------------------------------
# filter_stats
# ---------------------------------------------------------------------------

def test_filter_stats():
    original = [_v(), _v(zygosity="homozygous_ref"), _v(gq=5)]
    filtered  = apply_quality_filter(original)
    stats = filter_stats(original, filtered)
    assert stats["original_count"] == 3
    assert stats["filtered_count"] == 1
    assert stats["removed_count"]  == 2
    assert stats["removed_pct"]    == pytest.approx(66.7, abs=0.1)
