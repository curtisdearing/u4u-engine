"""
engine/repeat_callers/expansion_hunter.py
==========================================
STR (Short Tandem Repeat) calling module for the PeptidIQ V3 pipeline.

Wraps Illumina's ExpansionHunter binary to call the Androgen Receptor (AR)
CAG repeat from WGS/WES BAM files aligned to hg38.  The AR CAG repeat length
directly governs androgen receptor transactivation efficiency and is the
primary pharmacogenomic input for testosterone dosing in menopause/HRT
protocols.

Pipeline integration
--------------------
This module is called as Step 8b in the V3 pipeline.  The main entry point
is ``call_ar_cag_repeat()``, which:

1.  Validates BAM availability (graceful degradation for VCF-only input).
2.  Runs ExpansionHunter via subprocess.
3.  Parses the output VCF + JSON.
4.  Applies clinical interpretation logic with ancestry-adjusted reference
    ranges.
5.  Returns a fully self-contained dict ready for merge into the V3 JSON
    output under ``cag_repeat_data``.

Public interface
----------------
    call_ar_cag_repeat(bam_path, sex, ancestry)  -> dict
    run_expansion_hunter(bam_path, reference_fasta, sex) -> dict
    parse_eh_output(vcf_path, json_path) -> dict
    interpret_cag_repeat(repeat_count, sex, ancestry) -> dict
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EXPANSION_HUNTER_BIN: str = "/usr/local/bin/ExpansionHunter"
DEFAULT_REFERENCE_FASTA: str = "/data/references/hg38.fa"

#: ExpansionHunter variant catalog entry for the AR (CAG)n repeat on hg38.
#: chrX:67545316-67545385 spans the polymorphic CAG tract in AR exon 1.
AR_CAG_REPEAT_SPEC: str = json.dumps(
    {
        "LocusId": "AR",
        "LocusStructure": "(CAG)*",
        "ReferenceRegion": "chrX:67545316-67545385",
        "VariantType": "Repeat",
        "OfftargetRegions": [],
    },
    indent=2,
)

#: Ancestry-specific population mean CAG repeat lengths and interpretive
#: notes.  Sources: Ackerman et al. 2012, Kittles et al. 2001, multiple
#: GWAS replication cohorts.
ANCESTRY_REFERENCE: dict[str, dict[str, Any]] = {
    "african": {
        "mean": 20,
        "note": "Below population mean = elevated AR activity",
    },
    "afro-caribbean": {
        "mean": 20,
        "note": "Below population mean = elevated AR activity",
    },
    "caucasian": {
        "mean": 22,
        "note": "",
    },
    "hispanic": {
        "mean": 23,
        "note": "",
    },
    "asian": {
        "mean": 24,
        "note": "",
    },
    "unknown": {
        "mean": 22,
        "note": "Defaulting to Caucasian reference. Ancestry unconfirmed.",
    },
}

#: Clinical interpretation breakpoints.
#: Each tuple: (upper_bound_exclusive, sensitivity_level, dosing_text, flag_level)
_CAG_BREAKPOINTS: list[tuple[int, str, str, str]] = [
    (
        18,
        "VERY_HIGH",
        "Use lowest effective testosterone dose. High adverse event risk. "
        "Monthly CBC monitoring.",
        "CRITICAL",
    ),
    (
        23,
        "HIGH",
        "Start at lower quartile of standard range. Quarterly monitoring.",
        "MEDIUM",
    ),
    (
        27,
        "NORMAL",
        "Standard dosing protocol. Textbook HRT initiation.",
        "INFO",
    ),
    (
        32,
        "REDUCED",
        "Start at upper quartile. Expect slower response. "
        "3-month escalation window.",
        "MEDIUM",
    ),
    (
        36,
        "LOW",
        "High-dose testosterone may be required. Document rationale. "
        "Consider pellet therapy.",
        "HIGH",
    ),
]

_CAG_PATHOLOGIC: tuple[str, str, str] = (
    "VERY_LOW_PATHOLOGIC",
    "HALT androgen-based protocols. Kennedy disease spectrum. "
    "Mandatory neurology referral.",
    "CRITICAL",
)

#: Clinical note templates keyed by sensitivity_level.
_CLINICAL_NOTES: dict[str, str] = {
    "VERY_HIGH": (
        "Very short AR CAG repeat. Androgen receptor is extremely "
        "hypersensitive. Significant risk of androgenic adverse events at "
        "standard doses. Minimum effective dose approach mandatory."
    ),
    "HIGH": (
        "Short AR CAG repeat. Androgen receptor is hypersensitive. "
        "Minimum effective dose approach recommended for all "
        "androgen-pathway therapies."
    ),
    "NORMAL": (
        "AR CAG repeat within normal range. Standard androgen receptor "
        "sensitivity expected. Routine dosing protocol appropriate."
    ),
    "REDUCED": (
        "Long AR CAG repeat. Reduced androgen receptor sensitivity. "
        "Higher testosterone concentrations may be required to achieve "
        "standard clinical effect. Plan for dose escalation."
    ),
    "LOW": (
        "Very long AR CAG repeat. Markedly reduced androgen receptor "
        "sensitivity. High-dose androgen therapy likely required. "
        "Document clinical rationale and monitor closely."
    ),
    "VERY_LOW_PATHOLOGIC": (
        "AR CAG repeat in Kennedy disease (SBMA) range (> 35). "
        "Androgen-based therapy is CONTRAINDICATED. The expanded "
        "polyglutamine tract causes toxic protein aggregation under "
        "androgen stimulation. Immediate neurology referral required."
    ),
}


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def call_ar_cag_repeat(
    bam_path: str | Path | None,
    sex: str = "female",
    ancestry: str = "unknown",
) -> dict[str, Any]:
    """
    Main entry point for the pipeline (Step 8b).

    Attempts to call the AR CAG repeat from a BAM file.  If BAM input is
    not available, returns a graceful-degradation dict instead of raising.

    Parameters
    ----------
    bam_path : str | Path | None
        Path to an hg38-aligned BAM or CRAM file.  ``None`` when the
        pipeline was invoked with VCF-only input.
    sex : str
        Biological sex for ExpansionHunter (``"male"`` or ``"female"``).
    ancestry : str
        Self-reported ancestry for reference range adjustment.

    Returns
    -------
    dict
        A self-contained result dict ready for insertion into the V3 JSON
        output under ``cag_repeat_data``.
    """
    # ------------------------------------------------------------------
    # Guard: BAM not provided
    # ------------------------------------------------------------------
    if bam_path is None:
        logger.info("BAM path is None — skipping AR CAG repeat calling.")
        return {
            "available": False,
            "reason": (
                "BAM/CRAM input required for STR calling. "
                "VCF-only input cannot determine CAG repeat length."
            ),
            "recommendation": (
                "For AR CAG repeat analysis, provide a WGS or WES "
                "BAM file aligned to hg38."
            ),
        }

    bam_path = Path(bam_path)

    if not bam_path.exists():
        logger.warning("BAM path does not exist: %s", bam_path)
        return {
            "available": False,
            "reason": f"BAM file not found: {bam_path}",
            "recommendation": (
                "For AR CAG repeat analysis, provide a WGS or WES "
                "BAM file aligned to hg38."
            ),
        }

    # ------------------------------------------------------------------
    # Run ExpansionHunter
    # ------------------------------------------------------------------
    eh_result = run_expansion_hunter(bam_path, sex=sex)

    if not eh_result.get("available"):
        return eh_result

    repeat_count: int = eh_result["repeat_count"]
    repeat_count_ci: list[int] = eh_result.get("repeat_count_ci", [repeat_count, repeat_count])
    read_support: int = eh_result.get("read_support", 0)

    # ------------------------------------------------------------------
    # Clinical interpretation
    # ------------------------------------------------------------------
    interpretation = interpret_cag_repeat(
        repeat_count=repeat_count,
        sex=sex,
        ancestry=ancestry,
    )

    return {
        "available": True,
        "repeat_count": repeat_count,
        "repeat_count_ci": repeat_count_ci,
        "read_support": read_support,
        "sensitivity_level": interpretation["sensitivity_level"],
        "dosing_implication": interpretation["dosing_implication"],
        "flag_level": interpretation["flag_level"],
        "ancestry_context": interpretation["ancestry_context"],
        "detection_method": "ExpansionHunter v5 from WGS BAM",
        "clinical_note": interpretation["clinical_note"],
    }


def run_expansion_hunter(
    bam_path: str | Path,
    reference_fasta: str | Path = DEFAULT_REFERENCE_FASTA,
    sex: str = "female",
) -> dict[str, Any]:
    """
    Execute the ExpansionHunter binary and parse its output.

    Parameters
    ----------
    bam_path : str | Path
        Path to the hg38-aligned BAM or CRAM file.
    reference_fasta : str | Path
        Path to the hg38 reference FASTA (must have a ``.fai`` index).
    sex : str
        ``"male"`` or ``"female"``.

    Returns
    -------
    dict
        On success: ``{"available": True, "repeat_count": int,
        "repeat_count_ci": [int, int], "read_support": int}``.
        On failure: ``{"available": False, "reason": str}``.
    """
    bam_path = Path(bam_path)
    reference_fasta = Path(reference_fasta)

    # ------------------------------------------------------------------
    # Pre-flight validation
    # ------------------------------------------------------------------

    # Binary exists?
    eh_bin = shutil.which("ExpansionHunter") or EXPANSION_HUNTER_BIN
    if not Path(eh_bin).exists():
        msg = (
            f"ExpansionHunter binary not found at {EXPANSION_HUNTER_BIN} "
            f"and not on PATH."
        )
        logger.error(msg)
        return {"available": False, "reason": msg}

    # BAM exists?
    if not bam_path.exists():
        msg = f"BAM file not found: {bam_path}"
        logger.error(msg)
        return {"available": False, "reason": msg}

    # BAM index exists?  Convention: .bam.bai or .bai alongside the .bam.
    bai_candidates = [
        bam_path.with_suffix(bam_path.suffix + ".bai"),  # foo.bam.bai
        bam_path.with_suffix(".bai"),                     # foo.bai
    ]
    if not any(p.exists() for p in bai_candidates):
        msg = (
            f"BAM index not found. Expected one of: "
            f"{', '.join(str(p) for p in bai_candidates)}"
        )
        logger.error(msg)
        return {"available": False, "reason": msg}

    # Reference FASTA exists?
    if not reference_fasta.exists():
        msg = f"Reference FASTA not found: {reference_fasta}"
        logger.error(msg)
        return {"available": False, "reason": msg}

    # Reference FASTA index exists?
    fai_path = reference_fasta.with_suffix(reference_fasta.suffix + ".fai")
    if not fai_path.exists():
        msg = f"Reference FASTA index not found: {fai_path}"
        logger.error(msg)
        return {"available": False, "reason": msg}

    # ------------------------------------------------------------------
    # Build variant catalog and run
    # ------------------------------------------------------------------
    tmpdir: Path | None = None
    try:
        tmpdir = Path(tempfile.mkdtemp(prefix="eh_ar_cag_"))
        catalog_path = tmpdir / "ar_cag_catalog.json"
        output_prefix = tmpdir / "ar_cag_result"

        # Write the variant catalog as an array of one entry.
        catalog_data = [json.loads(AR_CAG_REPEAT_SPEC)]
        catalog_path.write_text(json.dumps(catalog_data, indent=2))

        cmd = [
            str(eh_bin),
            "--reads", str(bam_path),
            "--reference", str(reference_fasta),
            "--variant-catalog", str(catalog_path),
            "--output-prefix", str(output_prefix),
            "--sex", sex.lower(),
        ]

        logger.info("Running ExpansionHunter: %s", " ".join(cmd))

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5-minute timeout
        )

        if proc.returncode != 0:
            stderr_tail = (proc.stderr or "")[-500:]
            msg = (
                f"ExpansionHunter exited with code {proc.returncode}. "
                f"stderr: {stderr_tail}"
            )
            logger.error(msg)
            return {"available": False, "reason": msg}

        # ------------------------------------------------------------------
        # Parse output files
        # ------------------------------------------------------------------
        vcf_path = Path(f"{output_prefix}.vcf")
        json_path = Path(f"{output_prefix}.json")

        if not vcf_path.exists():
            msg = f"ExpansionHunter VCF output not found: {vcf_path}"
            logger.error(msg)
            return {"available": False, "reason": msg}

        if not json_path.exists():
            msg = f"ExpansionHunter JSON output not found: {json_path}"
            logger.error(msg)
            return {"available": False, "reason": msg}

        parsed = parse_eh_output(vcf_path, json_path)

        if "error" in parsed:
            return {"available": False, "reason": parsed["error"]}

        return {
            "available": True,
            "repeat_count": parsed["repeat_count"],
            "repeat_count_ci": parsed.get(
                "repeat_count_ci",
                [parsed["repeat_count"], parsed["repeat_count"]],
            ),
            "read_support": parsed.get("read_support", 0),
        }

    except subprocess.TimeoutExpired:
        msg = "ExpansionHunter timed out after 300 seconds."
        logger.error(msg)
        return {"available": False, "reason": msg}

    except FileNotFoundError:
        msg = (
            f"ExpansionHunter binary not executable or not found at {eh_bin}."
        )
        logger.error(msg)
        return {"available": False, "reason": msg}

    except Exception as exc:  # noqa: BLE001
        msg = f"Unexpected error running ExpansionHunter: {exc}"
        logger.exception(msg)
        return {"available": False, "reason": msg}

    finally:
        # Clean up the temporary directory
        if tmpdir is not None and tmpdir.exists():
            try:
                shutil.rmtree(tmpdir)
            except OSError as exc:
                logger.warning("Failed to clean up temp dir %s: %s", tmpdir, exc)


def parse_eh_output(
    vcf_path: Path,
    json_path: Path,
) -> dict[str, Any]:
    """
    Parse ExpansionHunter VCF and JSON output files for the AR locus.

    Parameters
    ----------
    vcf_path : Path
        Path to the ExpansionHunter ``.vcf`` output.
    json_path : Path
        Path to the ExpansionHunter ``.json`` output.

    Returns
    -------
    dict
        Parsed repeat data or ``{"error": "..."}`` on parse failure.
    """
    result: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Parse the VCF output
    # ------------------------------------------------------------------
    try:
        vcf_text = vcf_path.read_text()
    except OSError as exc:
        return {"error": f"Cannot read VCF output: {exc}"}

    ar_record_found = False
    for line in vcf_text.splitlines():
        if line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) < 8:
            continue

        # Match the AR locus by checking the ID column or INFO field.
        chrom = fields[0]
        record_id = fields[2]
        info = fields[7]

        if record_id == "AR" or "AR" in record_id.split(";"):
            ar_record_found = True

            # Extract REPCN from INFO field.
            # ExpansionHunter encodes repeat counts as REPCN=<count> or
            # REPCN=<a1>/<a2> for diploid calls.
            repcn_match = re.search(r"REPCN=([0-9/.]+)", info)
            if repcn_match:
                repcn_raw = repcn_match.group(1)
                # For haploid (chrX in male) or single allele: "19"
                # For diploid: "19/22"
                allele_counts = [
                    int(x) for x in repcn_raw.replace("/", ",").split(",")
                    if x.isdigit()
                ]
                if allele_counts:
                    # Use the shorter (more clinically relevant) allele for
                    # AR sensitivity — shorter CAG = more active receptor.
                    result["repeat_count"] = min(allele_counts)
                    result["all_alleles"] = allele_counts
            break

    if not ar_record_found:
        # Fall through to JSON parser — some EH versions don't write
        # the REPCN field in VCF for all variant types.
        logger.warning("AR locus not found in VCF output; trying JSON.")

    # ------------------------------------------------------------------
    # Parse the JSON output (always — for CI and read support)
    # ------------------------------------------------------------------
    try:
        json_data = json.loads(json_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        if "repeat_count" in result:
            # We got the count from VCF, so partial success is fine.
            logger.warning("Could not parse EH JSON output: %s", exc)
            return result
        return {"error": f"Cannot parse ExpansionHunter JSON output: {exc}"}

    # Navigate the EH JSON structure.  Top level has "LocusResults" → "AR".
    locus_results = json_data.get("LocusResults", {})
    ar_locus = locus_results.get("AR", {})

    if not ar_locus:
        if "repeat_count" in result:
            return result
        return {"error": "AR locus not found in ExpansionHunter JSON output."}

    # Extract variant-level data.  The "Variants" dict is keyed by
    # variant ID (usually "AR" for a single-repeat locus).
    variants = ar_locus.get("Variants", {})
    ar_variant = variants.get("AR", {})

    # RepeatSize — authoritative repeat count from the JSON.
    if "ReferenceRegion" in ar_variant or "RepeatSize" in ar_variant:
        repeat_size = ar_variant.get("RepeatSize")
        if repeat_size is not None:
            result["repeat_count"] = int(repeat_size)

    # Confidence interval
    ci = ar_variant.get("RepeatSizeConfidenceInterval", {})
    if isinstance(ci, dict):
        ci_low = ci.get("Low") or ci.get("low")
        ci_high = ci.get("High") or ci.get("high")
        if ci_low is not None and ci_high is not None:
            result["repeat_count_ci"] = [int(ci_low), int(ci_high)]

    # Read support
    read_support_data = ar_variant.get("ReadSupport", {})
    if isinstance(read_support_data, dict):
        # Sum spanning + flanking + in-repeat reads for total support.
        total = sum(
            read_support_data.get(k, 0)
            for k in ("SpanningReads", "FlankingReads", "InrepeatReads")
        )
        result["read_support"] = total
    elif isinstance(read_support_data, (int, float)):
        result["read_support"] = int(read_support_data)

    # Allele counts from JSON (may differ from VCF for diploid calls)
    allele_count = ar_locus.get("AlleleCount")
    if allele_count is not None and "all_alleles" not in result:
        if isinstance(allele_count, list):
            result["all_alleles"] = [int(x) for x in allele_count]
        elif isinstance(allele_count, (int, float)):
            result["all_alleles"] = [int(allele_count)]

    if "repeat_count" not in result:
        return {
            "error": (
                "Could not determine AR CAG repeat count from "
                "ExpansionHunter output."
            ),
        }

    return result


def interpret_cag_repeat(
    repeat_count: int,
    sex: str = "female",
    ancestry: str = "unknown",
) -> dict[str, Any]:
    """
    Apply clinical interpretation to an AR CAG repeat count.

    Parameters
    ----------
    repeat_count : int
        Number of CAG repeats (shorter allele if diploid).
    sex : str
        Biological sex (``"male"`` or ``"female"``).
    ancestry : str
        Self-reported ancestry for population-mean adjustment.

    Returns
    -------
    dict
        Interpretation dict with ``sensitivity_level``,
        ``dosing_implication``, ``flag_level``, ``ancestry_context``,
        and ``clinical_note``.
    """
    # ------------------------------------------------------------------
    # Sensitivity classification
    # ------------------------------------------------------------------
    sensitivity_level: str = _CAG_PATHOLOGIC[0]
    dosing_implication: str = _CAG_PATHOLOGIC[1]
    flag_level: str = _CAG_PATHOLOGIC[2]

    for upper_bound, level, dosing, flag in _CAG_BREAKPOINTS:
        if repeat_count < upper_bound:
            sensitivity_level = level
            dosing_implication = dosing
            flag_level = flag
            break

    # ------------------------------------------------------------------
    # Ancestry-adjusted reference range
    # ------------------------------------------------------------------
    ancestry_key = ancestry.lower().strip()
    ref = ANCESTRY_REFERENCE.get(ancestry_key, ANCESTRY_REFERENCE["unknown"])
    pop_mean: int = ref["mean"]
    ancestry_note: str = ref["note"]

    if repeat_count < pop_mean:
        vs_mean = "below"
        direction_text = "elevated AR activity confirmed"
    elif repeat_count > pop_mean:
        vs_mean = "above"
        direction_text = "reduced AR sensitivity"
    else:
        vs_mean = "at"
        direction_text = "typical AR sensitivity for this population"

    # Build a readable ancestry label.
    ancestry_display = ancestry_key.replace("-", " ").title()
    if ancestry_key == "unknown":
        ancestry_display = "Unknown (Caucasian default)"

    interpretation_text = (
        f"Patient value ({repeat_count}) is {vs_mean} "
        f"{ancestry_display.split(' (')[0]} population mean ({pop_mean}) "
        f"— {direction_text}."
    )

    if ancestry_note:
        interpretation_text = f"{interpretation_text} {ancestry_note}"

    ancestry_context = {
        "reported_ancestry": ancestry_key,
        "population_mean": pop_mean,
        "patient_vs_mean": vs_mean,
        "interpretation": interpretation_text,
    }

    # ------------------------------------------------------------------
    # Clinical note
    # ------------------------------------------------------------------
    clinical_note = _CLINICAL_NOTES.get(sensitivity_level, "")

    return {
        "sensitivity_level": sensitivity_level,
        "dosing_implication": dosing_implication,
        "flag_level": flag_level,
        "ancestry_context": ancestry_context,
        "clinical_note": clinical_note,
    }
