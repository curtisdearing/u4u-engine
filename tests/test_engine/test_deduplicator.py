"""Tests for engine/deduplicator.py"""

from engine.deduplicator import deduplicate


def _v(chrom, pos, ref, alt, rsid=None):
    return {
        "chrom": chrom, "pos": pos, "ref": ref, "alt": alt,
        "rsid": rsid, "variant_type": "coordinate",
        "genotype": None, "zygosity": "unknown", "gq": None, "dp": None,
    }


def test_removes_exact_duplicate():
    variants = [_v("1", 100, "A", "T"), _v("1", 100, "A", "T")]
    result = deduplicate(variants)
    assert len(result) == 1


def test_keeps_different_positions():
    variants = [_v("1", 100, "A", "T"), _v("1", 200, "A", "T")]
    result = deduplicate(variants)
    assert len(result) == 2


def test_keeps_different_alleles():
    variants = [_v("1", 100, "A", "T"), _v("1", 100, "A", "C")]
    result = deduplicate(variants)
    assert len(result) == 2


def test_prefers_entry_with_rsid():
    no_rsid   = _v("1", 100, "A", "T", rsid=None)
    with_rsid = _v("1", 100, "A", "T", rsid="rs123")
    # no_rsid first
    result = deduplicate([no_rsid, with_rsid])
    assert len(result) == 1
    assert result[0]["rsid"] == "rs123"


def test_chr_prefix_normalized():
    v1 = _v("chr1",  100, "A", "T")
    v2 = _v("1",     100, "A", "T")
    result = deduplicate([v1, v2])
    assert len(result) == 1


def test_skips_variants_without_coordinates():
    # rsid_only variants have no pos/ref/alt — should be skipped, not crash
    rsid_only = {"chrom": None, "pos": None, "ref": None, "alt": None,
                 "rsid": "rs1", "variant_type": "rsid_only"}
    coord     = _v("1", 100, "A", "T", rsid="rs2")
    result    = deduplicate([rsid_only, coord])
    assert len(result) == 1
    assert result[0]["rsid"] == "rs2"


def test_empty_input():
    assert deduplicate([]) == []
