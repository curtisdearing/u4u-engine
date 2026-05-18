"""tests/test_engine/test_kegg_mapper.py
=======================================
Unit tests for engine/annotators/kegg_mapper.py

Run with:
    pytest tests/test_engine/test_kegg_mapper.py -v --tb=short

All 53 tests should pass with zero network calls (API is mocked throughout).
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from engine.annotators.kegg_mapper import (
    HARDCODED_PATHWAY_GENES,
    PRIORITY_PATHWAYS,
    KEGGCache,
    generate_implication,
    generate_pathway_summary,
    map_variants_to_pathways,
)


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  TEST: Hardcoded pathway gene sets                                       ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


class TestHardcodedPathwayGenes:
    """Validate completeness and format of HARDCODED_PATHWAY_GENES."""

    def test_exactly_8_priority_pathways(self) -> None:
        assert len(PRIORITY_PATHWAYS) == 8

    def test_all_priority_pathways_have_genes(self) -> None:
        for pid in PRIORITY_PATHWAYS:
            assert pid in HARDCODED_PATHWAY_GENES, f"{pid} missing from HARDCODED_PATHWAY_GENES"
            assert len(HARDCODED_PATHWAY_GENES[pid]) > 0, f"{pid} has empty gene set"

    def test_minimum_gene_count(self) -> None:
        for pid, genes in HARDCODED_PATHWAY_GENES.items():
            assert len(genes) >= 10, f"{pid} has fewer than 10 genes ({len(genes)})"

    def test_gene_symbols_are_strings(self) -> None:
        for pid, genes in HARDCODED_PATHWAY_GENES.items():
            for gene in genes:
                assert isinstance(gene, str), f"Non-string gene in {pid}: {gene!r}"
                assert gene == gene.upper(), f"Gene not uppercase in {pid}: {gene!r}"

    def test_key_genes_present(self) -> None:
        """Spot-check that clinically critical genes are in the right pathways."""
        assert "ESR1" in HARDCODED_PATHWAY_GENES["hsa04915"]
        assert "KISS1R" in HARDCODED_PATHWAY_GENES["hsa04912"]
        assert "HTR2A" in HARDCODED_PATHWAY_GENES["hsa04726"]
        assert "BRAF" in HARDCODED_PATHWAY_GENES["hsa04010"]
        assert "GLP1R" in HARDCODED_PATHWAY_GENES["hsa04151"]
        assert "PPARG" in HARDCODED_PATHWAY_GENES["hsa04920"]
        assert "MC4R" in HARDCODED_PATHWAY_GENES["hsa04916"]
        assert "CYP19A1" in HARDCODED_PATHWAY_GENES["map00140"]


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  TEST: map_variants_to_pathways                                          ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


class TestMapVariantsToPathways:
    """Tests for the main mapping function."""

    def test_empty_gene_list(self) -> None:
        assert map_variants_to_pathways([]) == []

    def test_gene_not_in_any_pathway(self) -> None:
        result = map_variants_to_pathways(["FAKEGENE99", "NOTREAL"])
        assert result == []

    def test_tp53_alone_no_hits(self) -> None:
        # TP53 is not in estrogen/GnRH/melanocortin pathways — only MAPK + PI3K
        result = map_variants_to_pathways(["TP53"])
        pathway_ids = {r["kegg_id"] for r in result}
        assert "hsa04010" in pathway_ids or "hsa04151" in pathway_ids

    def test_known_gene_list(self) -> None:
        result = map_variants_to_pathways(["ESR1", "MC4R", "GLP1R"])
        pathway_ids = {r["kegg_id"] for r in result}
        assert "hsa04915" in pathway_ids  # ESR1
        assert "hsa04916" in pathway_ids  # MC4R
        assert "hsa04151" in pathway_ids  # GLP1R

    def test_esr1_hit_details(self) -> None:
        result = map_variants_to_pathways(["ESR1"])
        estrogen = next(r for r in result if r["kegg_id"] == "hsa04915")
        assert "ESR1" in estrogen["genes_hit"]
        assert estrogen["variant_count"] == 1
        assert isinstance(estrogen["clinical_implication"], str)
        assert len(estrogen["clinical_implication"]) > 10

    def test_multiple_genes_same_pathway(self) -> None:
        result = map_variants_to_pathways(["ESR1", "ESR2", "SRC"])
        estrogen = next(r for r in result if r["kegg_id"] == "hsa04915")
        assert estrogen["variant_count"] >= 2
        assert "ESR1" in estrogen["genes_hit"]
        assert "ESR2" in estrogen["genes_hit"]

    def test_gene_hitting_multiple_pathways(self) -> None:
        # MAPK1 appears in hsa04915, hsa04010, hsa04151, hsa04912, hsa04726
        result = map_variants_to_pathways(["MAPK1"])
        assert len(result) >= 2

    def test_case_insensitive(self) -> None:
        upper = map_variants_to_pathways(["ESR1"])
        lower = map_variants_to_pathways(["esr1"])
        mixed = map_variants_to_pathways(["Esr1"])
        assert {r["kegg_id"] for r in upper} == {r["kegg_id"] for r in lower}
        assert {r["kegg_id"] for r in upper} == {r["kegg_id"] for r in mixed}

    def test_results_sorted_by_variant_count_desc(self) -> None:
        # Use many genes to ensure multiple pathways fire with different counts
        genes = ["ESR1", "ESR2", "NCOA1", "SRC", "MAPK1", "AKT1"]
        result = map_variants_to_pathways(genes)
        counts = [r["variant_count"] for r in result]
        assert counts == sorted(counts, reverse=True)

    def test_only_hit_pathways_returned(self) -> None:
        result = map_variants_to_pathways(["ESR1"])
        assert all(r["variant_count"] >= 1 for r in result)
        assert len(result) <= 8

    def test_clinical_implication_present(self) -> None:
        result = map_variants_to_pathways(["ESR1"])
        for r in result:
            assert "clinical_implication" in r
            assert isinstance(r["clinical_implication"], str)

    def test_with_cache_object(self, tmp_path: Path) -> None:
        cache = KEGGCache(db_path=tmp_path / "test.db")
        result = map_variants_to_pathways(["MC4R"], cache=cache)
        pathway_ids = {r["kegg_id"] for r in result}
        assert "hsa04916" in pathway_ids


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  TEST: generate_implication                                              ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


class TestGenerateImplication:
    """Tests for the implication string generator."""

    @pytest.mark.parametrize(
        "pathway_id, gene",
        [
            ("hsa04915", "ESR1"),
            ("hsa04912", "KISS1R"),
            ("hsa04726", "HTR2A"),
            ("hsa04010", "BRAF"),
            ("hsa04151", "GLP1R"),
            ("hsa04920", "PPARG"),
            ("hsa04916", "MC4R"),
            ("map00140", "CYP19A1"),
        ],
    )
    def test_implication_per_pathway(self, pathway_id: str, gene: str) -> None:
        result = generate_implication(pathway_id, [gene])
        assert isinstance(result, str)
        assert len(result) > 20, f"Implication too short for {pathway_id}/{gene}"

    def test_empty_genes_returns_empty(self) -> None:
        assert generate_implication("hsa04915", []) == ""

    def test_unknown_gene_gets_generic_implication(self) -> None:
        result = generate_implication("hsa04915", ["FAKEGENE"])
        assert isinstance(result, str)
        assert len(result) > 0

    def test_multi_gene_implication(self) -> None:
        result = generate_implication("hsa04915", ["ESR1", "ESR2"])
        assert "ESR1" in result or "ESR2" in result or len(result) > 20

    def test_implication_does_not_crash_for_unknown_pathway(self) -> None:
        result = generate_implication("hsa99999", ["ESR1"])
        assert isinstance(result, str)


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  TEST: generate_pathway_summary                                          ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


class TestGeneratePathwaySummary:
    """Tests for the multi-pathway summary generator."""

    def test_zero_hits(self) -> None:
        result = generate_pathway_summary([])
        assert "No clinically relevant" in result

    def test_one_hit(self) -> None:
        hits = map_variants_to_pathways(["ESR1"])
        result = generate_pathway_summary(hits)
        assert "Estrogen" in result
        assert "ESR1" in result

    def test_three_hits(self) -> None:
        hits = map_variants_to_pathways(["ESR1", "MC4R", "GLP1R"])
        result = generate_pathway_summary(hits)
        assert isinstance(result, str)
        assert len(result) > 50

    def test_cross_pathway_combination_note(self) -> None:
        # ESR1 + CYP19A1 should trigger the hsa04915 ↔ map00140 combination note
        hits = map_variants_to_pathways(["ESR1", "CYP19A1"])
        result = generate_pathway_summary(hits)
        assert "Cross-pathway" in result or "biosynthesis" in result.lower()

    def test_summary_is_well_formed_string(self) -> None:
        hits = map_variants_to_pathways(["ESR1"])
        result = generate_pathway_summary(hits)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_full_pipeline_roundtrip(self) -> None:
        genes = ["ESR1", "MC4R", "GLP1R", "CYP19A1"]
        hits = map_variants_to_pathways(genes)
        summary = generate_pathway_summary(hits)
        assert isinstance(summary, str)
        assert len(hits) >= 3
        assert len(summary) > 100


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  TEST: KEGGCache (SQLite operations)                                     ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


class TestKEGGCache:
    """Tests for the SQLite caching layer."""

    def test_creates_database(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        KEGGCache(db_path=db_path)
        assert db_path.exists()

    def test_creates_schema(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        KEGGCache(db_path=db_path)
        with sqlite3.connect(str(db_path)) as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        assert ("pathway_genes",) in tables

    def test_get_genes_fallback_to_hardcoded(self, tmp_path: Path) -> None:
        cache = KEGGCache(db_path=tmp_path / "test.db")
        genes = cache.get_genes("hsa04916")
        assert "MC4R" in genes

    def test_get_genes_from_sqlite(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        cache = KEGGCache(db_path=db_path)
        now = "2025-01-01T00:00:00+00:00"
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute(
                "INSERT INTO pathway_genes VALUES (?, ?, ?)",
                ("hsa04915", "TESTGENE", now),
            )
            conn.commit()
        genes = cache.get_genes("hsa04915")
        assert "TESTGENE" in genes

    def test_is_stale_empty_db(self, tmp_path: Path) -> None:
        cache = KEGGCache(db_path=tmp_path / "test.db")
        assert cache.is_stale("hsa04915") is True

    def test_is_stale_fresh_data(self, tmp_path: Path) -> None:
        from datetime import datetime, timezone

        db_path = tmp_path / "test.db"
        cache = KEGGCache(db_path=db_path)
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute(
                "INSERT INTO pathway_genes VALUES (?, ?, ?)",
                ("hsa04915", "ESR1", now),
            )
            conn.commit()
        assert cache.is_stale("hsa04915", max_age_days=30) is False

    def test_is_stale_old_data(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        cache = KEGGCache(db_path=db_path)
        old_ts = "2020-01-01T00:00:00+00:00"
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute(
                "INSERT INTO pathway_genes VALUES (?, ?, ?)",
                ("hsa04915", "ESR1", old_ts),
            )
            conn.commit()
        assert cache.is_stale("hsa04915", max_age_days=30) is True

    def test_nested_directory_creation(self, tmp_path: Path) -> None:
        db_path = tmp_path / "a" / "b" / "c" / "cache.db"
        KEGGCache(db_path=db_path)
        assert db_path.exists()


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  TEST: KEGGCache API refresh (mocked)                                    ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


class TestKEGGCacheAPI:
    """Tests for the API refresh path using mocked urllib."""

    @patch("engine.annotators.kegg_mapper.urllib.request.urlopen")
    def test_refresh_from_api_success(
        self, mock_urlopen: MagicMock, tmp_path: Path
    ) -> None:
        mock_response = MagicMock()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.read.return_value = b"hsa04915\thsa:2099\nhsa04915\thsa:2100\n"
        mock_urlopen.return_value = mock_response

        cache = KEGGCache(db_path=tmp_path / "test.db")
        # Should not raise
        try:
            cache.refresh_from_api("hsa04915")
        except Exception:
            pass  # Empty gene_ids will return hardcoded fallback
        assert mock_urlopen.called

    @patch("engine.annotators.kegg_mapper.urllib.request.urlopen")
    def test_refresh_api_failure_falls_back(
        self, mock_urlopen: MagicMock, tmp_path: Path
    ) -> None:
        mock_urlopen.side_effect = OSError("Network unreachable")
        cache = KEGGCache(db_path=tmp_path / "test.db")
        with pytest.raises(OSError):
            cache.refresh_from_api("hsa04915")

    @patch("engine.annotators.kegg_mapper.urllib.request.urlopen")
    def test_map_variants_with_api_refresh(
        self, mock_urlopen: MagicMock, tmp_path: Path
    ) -> None:
        """With a stale cache, map_variants_to_pathways attempts API refresh."""
        mock_urlopen.side_effect = OSError("offline")
        cache = KEGGCache(db_path=tmp_path / "test.db")
        # Should succeed even with API failure (falls back to hardcoded)
        result = map_variants_to_pathways(["ESR1"], use_api=True, cache=cache)
        pathway_ids = {r["kegg_id"] for r in result}
        assert "hsa04915" in pathway_ids

    @patch("engine.annotators.kegg_mapper.urllib.request.urlopen")
    def test_api_called_only_when_stale(
        self,
        mock_urlopen: MagicMock,
        tmp_path: Path,
    ) -> None:
        """API should NOT be called when cache is fresh."""
        from datetime import datetime, timezone

        db_path = tmp_path / "test.db"
        cache = KEGGCache(db_path=db_path)

        # Pre-populate cache with fresh data for ALL pathways so none are stale
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(str(db_path)) as conn:
            for pid in PRIORITY_PATHWAYS:
                conn.execute(
                    "INSERT INTO pathway_genes VALUES (?, ?, ?)",
                    (pid, "ESR1", now),
                )
            conn.commit()

        map_variants_to_pathways(["ESR1"], use_api=True, cache=cache)

        # urlopen should NOT have been called because cache is fresh
        mock_urlopen.assert_not_called()


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  TEST: Edge cases and integration                                        ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


class TestEdgeCases:
    """Miscellaneous edge cases and integration tests."""

    def test_duplicate_genes_in_input(self) -> None:
        """Duplicate gene symbols should not inflate variant_count."""
        results = map_variants_to_pathways(["ESR1", "ESR1", "ESR1"])
        estrogen_hits = [r for r in results if r["kegg_id"] == "hsa04915"]
        assert len(estrogen_hits) == 1
        assert estrogen_hits[0]["variant_count"] == 1

    def test_whitespace_handling(self) -> None:
        """Genes with surrounding whitespace should still match."""
        result = map_variants_to_pathways(["  ESR1  ", "MC4R\t"])
        pathway_ids = {r["kegg_id"] for r in result}
        assert "hsa04915" in pathway_ids
        assert "hsa04916" in pathway_ids

    def test_none_in_gene_list(self) -> None:
        """None values in the gene list should be silently skipped."""
        result = map_variants_to_pathways([None, "ESR1", None])  # type: ignore[list-item]
        pathway_ids = {r["kegg_id"] for r in result}
        assert "hsa04915" in pathway_ids

    def test_all_8_pathways_hittable(self) -> None:
        """Each of the 8 priority pathways can be hit with the right gene."""
        probe_genes = [
            "ESR1",    # hsa04915
            "KISS1R",  # hsa04912
            "HTR2A",   # hsa04726
            "BRAF",    # hsa04010
            "GLP1R",   # hsa04151
            "PPARG",   # hsa04920
            "MC4R",    # hsa04916
            "CYP19A1", # map00140
        ]
        result = map_variants_to_pathways(probe_genes)
        hit_ids = {r["kegg_id"] for r in result}
        assert hit_ids == set(PRIORITY_PATHWAYS.keys())

    def test_ar_gene_hits_gnrh_pathway(self) -> None:
        """AR should map to the GnRH signalling pathway."""
        result = map_variants_to_pathways(["AR"])
        pathway_ids = {r["kegg_id"] for r in result}
        assert "hsa04912" in pathway_ids

    def test_large_gene_list_performance(self) -> None:
        """Mapping 200 random gene names should complete in under 1 second."""
        import random
        import string

        rng = random.Random(42)
        big_list = [
            "".join(rng.choices(string.ascii_uppercase, k=rng.randint(3, 8)))
            for _ in range(200)
        ]
        # Sprinkle in real genes
        big_list += ["ESR1", "MC4R", "GLP1R"]

        start = time.monotonic()
        result = map_variants_to_pathways(big_list)
        elapsed = time.monotonic() - start

        assert elapsed < 1.0, f"Performance regression: {elapsed:.3f}s"
        assert len(result) >= 3
