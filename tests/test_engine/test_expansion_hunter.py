"""
tests/test_expansion_hunter.py
==============================
Unit tests for the AR CAG repeat calling module.

Covers:
  - interpret_cag_repeat() at every clinical breakpoint boundary
  - Ancestry correction for all five populations + unknown
  - call_ar_cag_repeat() graceful degradation (None / missing file)
  - parse_eh_output() with mocked VCF + JSON files
  - run_expansion_hunter() with mocked subprocess.run
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Import the module under test.
# When running pytest from the project root the package layout is available.
# For isolated test runs, adjust PYTHONPATH or use `pip install -e .`.
from engine.repeat_callers.expansion_hunter import (
    AR_CAG_REPEAT_SPEC,
    call_ar_cag_repeat,
    interpret_cag_repeat,
    parse_eh_output,
    run_expansion_hunter,
)


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  FIXTURES                                                                ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


@pytest.fixture()
def mock_eh_vcf(tmp_path: Path) -> Path:
    """Write a minimal ExpansionHunter VCF with an AR CAG repeat record."""
    vcf_content = textwrap.dedent("""\
        ##fileformat=VCFv4.1
        ##INFO=<ID=REPCN,Number=.,Type=String,Description="Repeat counts">
        #CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE
        chrX\t67545316\tAR\t.\t<STR19>\t.\tPASS\tEND=67545385;REF=23;RL=69;RU=CAG;VARID=AR;REPCN=19\tGT:SO:REPCN:REPCI:ADSP:ADFL:ADIR\t0/1:SPANNING/SPANNING:19:18-20:5:10:30
    """)
    p = tmp_path / "ar_cag_result.vcf"
    p.write_text(vcf_content)
    return p


@pytest.fixture()
def mock_eh_json(tmp_path: Path) -> Path:
    """Write a minimal ExpansionHunter JSON output for the AR locus."""
    json_data = {
        "LocusResults": {
            "AR": {
                "AlleleCount": [19],
                "Variants": {
                    "AR": {
                        "ReferenceRegion": "chrX:67545316-67545385",
                        "RepeatSize": 19,
                        "RepeatSizeConfidenceInterval": {
                            "Low": 18,
                            "High": 20,
                        },
                        "ReadSupport": {
                            "SpanningReads": 5,
                            "FlankingReads": 10,
                            "InrepeatReads": 30,
                        },
                    }
                },
            }
        }
    }
    p = tmp_path / "ar_cag_result.json"
    p.write_text(json.dumps(json_data, indent=2))
    return p


@pytest.fixture()
def mock_eh_vcf_diploid(tmp_path: Path) -> Path:
    """VCF with diploid AR call (two alleles)."""
    vcf_content = textwrap.dedent("""\
        ##fileformat=VCFv4.1
        #CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE
        chrX\t67545316\tAR\t.\t<STR19>,<STR25>\t.\tPASS\tEND=67545385;REF=23;RL=69;RU=CAG;VARID=AR;REPCN=19/25\tGT:REPCN\t1/2:19/25
    """)
    p = tmp_path / "ar_cag_diploid.vcf"
    p.write_text(vcf_content)
    return p


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  TEST: AR_CAG_REPEAT_SPEC constant                                      ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


class TestARCAGRepeatSpec:
    """Verify the variant catalog constant is well-formed."""

    def test_is_valid_json(self) -> None:
        data = json.loads(AR_CAG_REPEAT_SPEC)
        assert isinstance(data, dict)

    def test_has_required_keys(self) -> None:
        data = json.loads(AR_CAG_REPEAT_SPEC)
        for key in ("LocusId", "LocusStructure", "ReferenceRegion", "VariantType"):
            assert key in data, f"Missing key: {key}"

    def test_locus_id_is_ar(self) -> None:
        data = json.loads(AR_CAG_REPEAT_SPEC)
        assert data["LocusId"] == "AR"

    def test_reference_region_is_hg38(self) -> None:
        data = json.loads(AR_CAG_REPEAT_SPEC)
        assert data["ReferenceRegion"].startswith("chrX:")


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  TEST: interpret_cag_repeat — breakpoint boundaries                      ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


class TestInterpretCAGRepeat:
    """Test every boundary in the clinical interpretation logic."""

    # ------------------------------------------------------------------
    # Boundary tests: (repeat_count, expected_sensitivity, expected_flag)
    # ------------------------------------------------------------------

    @pytest.mark.parametrize(
        "repeat_count, expected_sensitivity, expected_flag",
        [
            # < 18 → VERY_HIGH / CRITICAL
            (10, "VERY_HIGH", "CRITICAL"),
            (17, "VERY_HIGH", "CRITICAL"),
            # 18–22 → HIGH / MEDIUM  (18 inclusive, 22 inclusive)
            (18, "HIGH", "MEDIUM"),
            (20, "HIGH", "MEDIUM"),
            (22, "HIGH", "MEDIUM"),
            # 23–26 → NORMAL / INFO
            (23, "NORMAL", "INFO"),
            (25, "NORMAL", "INFO"),
            (26, "NORMAL", "INFO"),
            # 27–31 → REDUCED / MEDIUM
            (27, "REDUCED", "MEDIUM"),
            (29, "REDUCED", "MEDIUM"),
            (31, "REDUCED", "MEDIUM"),
            # 32–35 → LOW / HIGH
            (32, "LOW", "HIGH"),
            (34, "LOW", "HIGH"),
            (35, "LOW", "HIGH"),
            # > 35 → VERY_LOW_PATHOLOGIC / CRITICAL
            (36, "VERY_LOW_PATHOLOGIC", "CRITICAL"),
            (40, "VERY_LOW_PATHOLOGIC", "CRITICAL"),
            (50, "VERY_LOW_PATHOLOGIC", "CRITICAL"),
        ],
    )
    def test_sensitivity_breakpoints(
        self,
        repeat_count: int,
        expected_sensitivity: str,
        expected_flag: str,
    ) -> None:
        result = interpret_cag_repeat(repeat_count)
        assert result["sensitivity_level"] == expected_sensitivity, (
            f"repeat={repeat_count}: got {result['sensitivity_level']}, "
            f"expected {expected_sensitivity}"
        )
        assert result["flag_level"] == expected_flag, (
            f"repeat={repeat_count}: got {result['flag_level']}, "
            f"expected {expected_flag}"
        )

    def test_dosing_text_populated(self) -> None:
        """Every interpretation must include non-empty dosing guidance."""
        for count in (10, 18, 23, 27, 32, 36):
            result = interpret_cag_repeat(count)
            assert isinstance(result["dosing_implication"], str)
            assert len(result["dosing_implication"]) > 10

    def test_clinical_note_populated(self) -> None:
        """Every interpretation must include a clinical note."""
        for count in (10, 18, 23, 27, 32, 36):
            result = interpret_cag_repeat(count)
            assert isinstance(result["clinical_note"], str)
            assert len(result["clinical_note"]) > 20

    def test_pathologic_halt_message(self) -> None:
        """CAG > 35 must contain HALT and neurology referral language."""
        result = interpret_cag_repeat(36)
        assert "HALT" in result["dosing_implication"]
        assert "neurology" in result["dosing_implication"].lower()

    def test_return_dict_structure(self) -> None:
        """Verify the full shape of the return dict."""
        result = interpret_cag_repeat(22, sex="female", ancestry="caucasian")
        required_keys = {
            "sensitivity_level",
            "dosing_implication",
            "flag_level",
            "ancestry_context",
            "clinical_note",
        }
        assert required_keys.issubset(result.keys())


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  TEST: interpret_cag_repeat — ancestry correction                        ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


class TestAncestryCorrection:
    """Test ancestry reference range adjustments."""

    @pytest.mark.parametrize(
        "ancestry, expected_mean",
        [
            ("african", 20),
            ("afro-caribbean", 20),
            ("caucasian", 22),
            ("hispanic", 23),
            ("asian", 24),
            ("unknown", 22),
        ],
    )
    def test_population_mean(self, ancestry: str, expected_mean: int) -> None:
        result = interpret_cag_repeat(22, ancestry=ancestry)
        ctx = result["ancestry_context"]
        assert ctx["population_mean"] == expected_mean

    def test_below_mean_flagged(self) -> None:
        """A value below population mean → 'below' + 'elevated AR activity'."""
        result = interpret_cag_repeat(19, ancestry="caucasian")
        ctx = result["ancestry_context"]
        assert ctx["patient_vs_mean"] == "below"
        assert "elevated AR activity" in ctx["interpretation"]

    def test_above_mean_flagged(self) -> None:
        """A value above population mean → 'above' + 'reduced AR sensitivity'."""
        result = interpret_cag_repeat(26, ancestry="caucasian")
        ctx = result["ancestry_context"]
        assert ctx["patient_vs_mean"] == "above"
        assert "reduced AR sensitivity" in ctx["interpretation"]

    def test_at_mean_flagged(self) -> None:
        """A value at population mean → 'at' + 'typical'."""
        result = interpret_cag_repeat(22, ancestry="caucasian")
        ctx = result["ancestry_context"]
        assert ctx["patient_vs_mean"] == "at"
        assert "typical" in ctx["interpretation"]

    def test_unknown_ancestry_note(self) -> None:
        """Unknown ancestry should include a caveat note."""
        result = interpret_cag_repeat(22, ancestry="unknown")
        ctx = result["ancestry_context"]
        assert "unconfirmed" in ctx["interpretation"].lower()

    def test_african_ancestry_elevated_note(self) -> None:
        """African ancestry at value below mean should mention elevated AR."""
        result = interpret_cag_repeat(18, ancestry="african")
        ctx = result["ancestry_context"]
        assert ctx["population_mean"] == 20
        assert ctx["patient_vs_mean"] == "below"

    def test_ancestry_case_insensitive(self) -> None:
        """Ancestry matching should be case-insensitive."""
        result_lower = interpret_cag_repeat(22, ancestry="caucasian")
        result_upper = interpret_cag_repeat(22, ancestry="CAUCASIAN")
        result_mixed = interpret_cag_repeat(22, ancestry="Caucasian")
        assert (
            result_lower["ancestry_context"]["population_mean"]
            == result_upper["ancestry_context"]["population_mean"]
            == result_mixed["ancestry_context"]["population_mean"]
            == 22
        )

    def test_unknown_ancestry_fallback(self) -> None:
        """Unrecognized ancestry strings should fall back to 'unknown'."""
        result = interpret_cag_repeat(22, ancestry="martian")
        ctx = result["ancestry_context"]
        assert ctx["population_mean"] == 22  # unknown default
        assert "unconfirmed" in ctx["interpretation"].lower()


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  TEST: call_ar_cag_repeat — graceful degradation                         ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


class TestCallARCAGRepeatGraceful:
    """Test graceful degradation when BAM input is unavailable."""

    def test_none_bam_path(self) -> None:
        """None bam_path → available=False with helpful message."""
        result = call_ar_cag_repeat(None)
        assert result["available"] is False
        assert "BAM/CRAM input required" in result["reason"]
        assert "recommendation" in result

    def test_nonexistent_bam_path(self) -> None:
        """Non-existent file → available=False with file-not-found reason."""
        result = call_ar_cag_repeat("/nonexistent/path/sample.bam")
        assert result["available"] is False
        assert "not found" in result["reason"].lower()

    def test_nonexistent_bam_has_recommendation(self) -> None:
        """Error dicts should always include a recommendation."""
        result = call_ar_cag_repeat("/nonexistent/path/sample.bam")
        assert "recommendation" in result

    def test_return_keys_on_none(self) -> None:
        """Graceful degradation dict must have exactly these keys."""
        result = call_ar_cag_repeat(None)
        assert set(result.keys()) == {"available", "reason", "recommendation"}


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  TEST: parse_eh_output                                                   ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


class TestParseEHOutput:
    """Test the VCF + JSON parser against mock ExpansionHunter output."""

    def test_parses_repeat_count(
        self, mock_eh_vcf: Path, mock_eh_json: Path
    ) -> None:
        result = parse_eh_output(mock_eh_vcf, mock_eh_json)
        assert "error" not in result
        assert result["repeat_count"] == 19

    def test_parses_confidence_interval(
        self, mock_eh_vcf: Path, mock_eh_json: Path
    ) -> None:
        result = parse_eh_output(mock_eh_vcf, mock_eh_json)
        assert result["repeat_count_ci"] == [18, 20]

    def test_parses_read_support(
        self, mock_eh_vcf: Path, mock_eh_json: Path
    ) -> None:
        result = parse_eh_output(mock_eh_vcf, mock_eh_json)
        # 5 spanning + 10 flanking + 30 in-repeat = 45
        assert result["read_support"] == 45

    def test_diploid_uses_shorter_allele(
        self, mock_eh_vcf_diploid: Path, mock_eh_json: Path
    ) -> None:
        """Diploid VCF (19/25) should return the shorter allele (19)."""
        result = parse_eh_output(mock_eh_vcf_diploid, mock_eh_json)
        assert result["repeat_count"] == 19
        assert 19 in result.get("all_alleles", [])
        assert 25 in result.get("all_alleles", [])

    def test_missing_vcf_file(self, tmp_path: Path, mock_eh_json: Path) -> None:
        """Missing VCF file returns an error dict."""
        fake_vcf = tmp_path / "nonexistent.vcf"
        result = parse_eh_output(fake_vcf, mock_eh_json)
        # Should still succeed via JSON fallback since JSON has repeat_count.
        # But if VCF is unreadable and JSON has data, we still get a result.
        assert result.get("repeat_count") == 19 or "error" in result

    def test_missing_json_file(self, mock_eh_vcf: Path, tmp_path: Path) -> None:
        """Missing JSON file — VCF data should still produce a partial result."""
        fake_json = tmp_path / "nonexistent.json"
        result = parse_eh_output(mock_eh_vcf, fake_json)
        # VCF had the repeat count, so we should get it even without JSON.
        assert result.get("repeat_count") == 19

    def test_empty_vcf_falls_back_to_json(
        self, tmp_path: Path, mock_eh_json: Path
    ) -> None:
        """VCF with no AR record → parser falls through to JSON."""
        empty_vcf = tmp_path / "empty.vcf"
        empty_vcf.write_text(
            "##fileformat=VCFv4.1\n"
            "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
        )
        result = parse_eh_output(empty_vcf, mock_eh_json)
        assert result["repeat_count"] == 19


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  TEST: run_expansion_hunter — mocked subprocess                          ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


class TestRunExpansionHunterMocked:
    """Test run_expansion_hunter with the binary mocked out."""

    def _setup_bam_and_ref(self, tmp_path: Path) -> tuple[Path, Path]:
        """Create dummy BAM, BAI, FASTA, and FAI files."""
        bam = tmp_path / "sample.bam"
        bam.write_bytes(b"fake bam content")
        bai = tmp_path / "sample.bam.bai"
        bai.write_bytes(b"fake bai content")

        fasta = tmp_path / "hg38.fa"
        fasta.write_text(">chr1\nACGT\n")
        fai = tmp_path / "hg38.fa.fai"
        fai.write_text("chr1\t4\t6\t4\t5\n")

        return bam, fasta

    def _mock_subprocess_success(
        self, tmp_path: Path, output_prefix_holder: list[str]
    ) -> MagicMock:
        """
        Return a mock subprocess.run that writes realistic EH output files
        to the temp directory that run_expansion_hunter will create.
        """

        def _side_effect(cmd: list[str], **kwargs) -> MagicMock:
            # Find the --output-prefix argument.
            prefix_idx = cmd.index("--output-prefix") + 1
            output_prefix = cmd[prefix_idx]
            output_prefix_holder.append(output_prefix)

            # Write mock VCF
            vcf_path = Path(f"{output_prefix}.vcf")
            vcf_path.write_text(
                "##fileformat=VCFv4.1\n"
                "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
                "chrX\t67545316\tAR\t.\t<STR21>\t.\tPASS\t"
                "END=67545385;REPCN=21\n"
            )

            # Write mock JSON
            json_path = Path(f"{output_prefix}.json")
            json_path.write_text(
                json.dumps(
                    {
                        "LocusResults": {
                            "AR": {
                                "AlleleCount": [21],
                                "Variants": {
                                    "AR": {
                                        "ReferenceRegion": "chrX:67545316-67545385",
                                        "RepeatSize": 21,
                                        "RepeatSizeConfidenceInterval": {
                                            "Low": 20,
                                            "High": 22,
                                        },
                                        "ReadSupport": {
                                            "SpanningReads": 8,
                                            "FlankingReads": 12,
                                            "InrepeatReads": 25,
                                        },
                                    }
                                },
                            }
                        }
                    }
                )
            )

            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            mock_result.stderr = ""
            return mock_result

        return _side_effect

    @patch("engine.repeat_callers.expansion_hunter.shutil.which")
    @patch("engine.repeat_callers.expansion_hunter.subprocess.run")
    def test_successful_run(
        self,
        mock_run: MagicMock,
        mock_which: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Full success path with mocked binary."""
        bam, fasta = self._setup_bam_and_ref(tmp_path)

        # Create a fake binary path that "exists".
        fake_bin = tmp_path / "ExpansionHunter"
        fake_bin.write_text("#!/bin/sh\n")
        fake_bin.chmod(0o755)
        mock_which.return_value = str(fake_bin)

        output_prefix_holder: list[str] = []
        mock_run.side_effect = self._mock_subprocess_success(
            tmp_path, output_prefix_holder
        )

        result = run_expansion_hunter(bam, reference_fasta=fasta, sex="female")

        assert result["available"] is True
        assert result["repeat_count"] == 21
        assert result["repeat_count_ci"] == [20, 22]
        assert result["read_support"] == 45  # 8 + 12 + 25

    @patch("engine.repeat_callers.expansion_hunter.shutil.which")
    def test_missing_binary(
        self,
        mock_which: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Missing ExpansionHunter binary → available=False."""
        bam, fasta = self._setup_bam_and_ref(tmp_path)
        mock_which.return_value = None
        # Also ensure the default path doesn't exist.

        result = run_expansion_hunter(bam, reference_fasta=fasta)

        assert result["available"] is False
        assert "not found" in result["reason"].lower()

    def test_missing_bam_index(self, tmp_path: Path) -> None:
        """BAM without a .bai index → available=False."""
        bam = tmp_path / "sample.bam"
        bam.write_bytes(b"fake bam")
        # No .bai file created.

        fasta = tmp_path / "hg38.fa"
        fasta.write_text(">chr1\nACGT\n")
        fai = tmp_path / "hg38.fa.fai"
        fai.write_text("chr1\t4\t6\t4\t5\n")

        # Need to also provide a fake binary.
        fake_bin = tmp_path / "ExpansionHunter"
        fake_bin.write_text("#!/bin/sh\n")
        fake_bin.chmod(0o755)

        with patch(
            "engine.repeat_callers.expansion_hunter.shutil.which",
            return_value=str(fake_bin),
        ):
            result = run_expansion_hunter(bam, reference_fasta=fasta)

        assert result["available"] is False
        assert "index not found" in result["reason"].lower()

    def test_missing_reference_fasta(self, tmp_path: Path) -> None:
        """Missing reference FASTA → available=False."""
        bam, _ = self._setup_bam_and_ref(tmp_path)

        fake_bin = tmp_path / "ExpansionHunter"
        fake_bin.write_text("#!/bin/sh\n")
        fake_bin.chmod(0o755)

        fake_ref = tmp_path / "nonexistent.fa"

        with patch(
            "engine.repeat_callers.expansion_hunter.shutil.which",
            return_value=str(fake_bin),
        ):
            result = run_expansion_hunter(bam, reference_fasta=fake_ref)

        assert result["available"] is False
        assert "reference fasta not found" in result["reason"].lower()

    @patch("engine.repeat_callers.expansion_hunter.shutil.which")
    @patch("engine.repeat_callers.expansion_hunter.subprocess.run")
    def test_nonzero_exit_code(
        self,
        mock_run: MagicMock,
        mock_which: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Non-zero exit from ExpansionHunter → available=False."""
        bam, fasta = self._setup_bam_and_ref(tmp_path)

        fake_bin = tmp_path / "ExpansionHunter"
        fake_bin.write_text("#!/bin/sh\n")
        fake_bin.chmod(0o755)
        mock_which.return_value = str(fake_bin)

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Error: invalid BAM header"
        mock_run.return_value = mock_result

        result = run_expansion_hunter(bam, reference_fasta=fasta)

        assert result["available"] is False
        assert "exited with code 1" in result["reason"]

    @patch("engine.repeat_callers.expansion_hunter.shutil.which")
    @patch("engine.repeat_callers.expansion_hunter.subprocess.run")
    def test_timeout(
        self,
        mock_run: MagicMock,
        mock_which: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Subprocess timeout → available=False."""
        bam, fasta = self._setup_bam_and_ref(tmp_path)

        fake_bin = tmp_path / "ExpansionHunter"
        fake_bin.write_text("#!/bin/sh\n")
        fake_bin.chmod(0o755)
        mock_which.return_value = str(fake_bin)

        import subprocess as sp

        mock_run.side_effect = sp.TimeoutExpired(cmd="ExpansionHunter", timeout=300)

        result = run_expansion_hunter(bam, reference_fasta=fasta)

        assert result["available"] is False
        assert "timed out" in result["reason"].lower()


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  TEST: call_ar_cag_repeat — full integration (mocked binary)             ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


class TestCallARCAGRepeatIntegration:
    """
    Test the full call_ar_cag_repeat() path with a mocked binary,
    verifying the final output dict shape and content.
    """

    @patch("engine.repeat_callers.expansion_hunter.run_expansion_hunter")
    def test_full_success_path(
        self,
        mock_eh: MagicMock,
    ) -> None:
        """Successful call returns the full schema."""
        mock_eh.return_value = {
            "available": True,
            "repeat_count": 19,
            "repeat_count_ci": [18, 20],
            "read_support": 45,
        }

        # Need a bam_path that "exists".
        with patch.object(Path, "exists", return_value=True):
            result = call_ar_cag_repeat(
                bam_path="/fake/sample.bam",
                sex="female",
                ancestry="caucasian",
            )

        assert result["available"] is True
        assert result["repeat_count"] == 19
        assert result["repeat_count_ci"] == [18, 20]
        assert result["read_support"] == 45
        assert result["sensitivity_level"] == "HIGH"
        assert result["flag_level"] == "MEDIUM"
        assert result["detection_method"] == "ExpansionHunter v5 from WGS BAM"

        # Ancestry context
        ctx = result["ancestry_context"]
        assert ctx["reported_ancestry"] == "caucasian"
        assert ctx["population_mean"] == 22
        assert ctx["patient_vs_mean"] == "below"

        # Clinical note
        assert "hypersensitive" in result["clinical_note"].lower()

    @patch("engine.repeat_callers.expansion_hunter.run_expansion_hunter")
    def test_expansion_hunter_failure_propagates(
        self,
        mock_eh: MagicMock,
    ) -> None:
        """When run_expansion_hunter fails, call_ar_cag_repeat propagates."""
        mock_eh.return_value = {
            "available": False,
            "reason": "ExpansionHunter binary not found",
        }

        with patch.object(Path, "exists", return_value=True):
            result = call_ar_cag_repeat(bam_path="/fake/sample.bam")

        assert result["available"] is False
        assert "not found" in result["reason"].lower()

    @patch("engine.repeat_callers.expansion_hunter.run_expansion_hunter")
    def test_pathologic_repeat_flags_critical(
        self,
        mock_eh: MagicMock,
    ) -> None:
        """CAG > 35 from EH → CRITICAL flag + Kennedy disease language."""
        mock_eh.return_value = {
            "available": True,
            "repeat_count": 38,
            "repeat_count_ci": [37, 39],
            "read_support": 30,
        }

        with patch.object(Path, "exists", return_value=True):
            result = call_ar_cag_repeat(
                bam_path="/fake/sample.bam",
                sex="male",
                ancestry="caucasian",
            )

        assert result["available"] is True
        assert result["sensitivity_level"] == "VERY_LOW_PATHOLOGIC"
        assert result["flag_level"] == "CRITICAL"
        assert "HALT" in result["dosing_implication"]
        assert "Kennedy" in result["clinical_note"]
