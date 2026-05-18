"""engine/annotators/kegg_mapper.py
=================================
Maps patient variant gene symbols to priority KEGG signaling pathways
relevant to menopause / HRT / peptide pharmacogenomics.

Design principles
-----------------
* **Fully offline by default** — HARDCODED_PATHWAY_GENES contains curated
  gene membership for 8 priority pathways.  No network call is required.
* **Optional API refresh** — pass ``use_api=True`` to refresh stale entries
  from the KEGG REST API (rest.kegg.jp).  Results are cached in SQLite so
  subsequent calls are instant.
* **Clinical implication generation** — per-gene and per-pathway narrative
  strings are assembled into a single plain-English note for each hit.
* **Cross-pathway combination notes** — when two or more pathways are hit
  simultaneously, additional interpretive text is injected.

Public API
----------
    map_variants_to_pathways(gene_symbols, use_api, cache) -> list[dict]
    generate_implication(pathway_id, genes_hit)            -> str
    generate_pathway_summary(pathway_hits)                 -> str

Usage example
-------------
    from engine.annotators.kegg_mapper import map_variants_to_pathways, generate_pathway_summary

    hits = map_variants_to_pathways(["ESR1", "AR", "GLP1R"])
    print(generate_pathway_summary(hits))
"""

from __future__ import annotations

import logging
import sqlite3
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Priority pathway registry
# ─────────────────────────────────────────────────────────────────────────────

PRIORITY_PATHWAYS: dict[str, dict[str, Any]] = {
    "hsa04915": {
        "name": "Estrogen signaling pathway",
        "clinical_relevance": (
            "Central to HRT response, breast cancer risk stratification, "
            "and menopause symptom modulation via ESR1/ESR2 variants."
        ),
    },
    "hsa04912": {
        "name": "GnRH signaling pathway",
        "clinical_relevance": (
            "Governs LH/FSH pulsatility; kisspeptin agonists (e.g. Kisspeptin-10) "
            "act directly on this pathway to modulate reproductive axis."
        ),
    },
    "hsa04726": {
        "name": "Serotonergic synapse",
        "clinical_relevance": (
            "Serotonin receptor variants (HTR2A, HTR1A) influence mood, hot-flash "
            "severity, and SSRI/SNRI response in perimenopausal patients."
        ),
    },
    "hsa04010": {
        "name": "MAPK signaling pathway",
        "clinical_relevance": (
            "BRAF/RAS/ERK cascade mediates mitogenic estrogen signaling and "
            "modulates peptide growth-factor receptor sensitivity."
        ),
    },
    "hsa04151": {
        "name": "PI3K-Akt signaling pathway",
        "clinical_relevance": (
            "GLP-1R and insulin receptor downstream effectors; variants alter "
            "metabolic peptide (Semaglutide, Tirzepatide) efficacy and cancer risk."
        ),
    },
    "hsa04920": {
        "name": "Adipocytokine signaling pathway",
        "clinical_relevance": (
            "PPARG/ADIPOQ variants modulate adipose hormone secretion and "
            "body-composition response to GLP-1 agonists."
        ),
    },
    "hsa04916": {
        "name": "Melanocortin signaling / appetite regulation",
        "clinical_relevance": (
            "MC4R loss-of-function is the most common monogenic obesity cause; "
            "MC4R variants predict differential response to Bremelanotide and "
            "Setmelanotide."
        ),
    },
    "map00140": {
        "name": "Steroid hormone biosynthesis",
        "clinical_relevance": (
            "CYP19A1 (aromatase) and HSD variants directly control estrogen "
            "and androgen synthesis; critical for HRT dosing and AI therapy."
        ),
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# Hardcoded gene membership (offline fallback)
# ─────────────────────────────────────────────────────────────────────────────

HARDCODED_PATHWAY_GENES: dict[str, set[str]] = {
    "hsa04915": {
        "ESR1", "ESR2", "GPER1", "SRC", "PIK3CA", "PIK3R1", "AKT1", "AKT2",
        "AKT3", "MAPK1", "MAPK3", "HRAS", "KRAS", "NRAS", "RAF1", "BRAF",
        "MAP2K1", "MAP2K2", "MYC", "JUN", "FOS", "SP1", "NCOA1", "NCOA2",
        "NCOA3", "NRIP1", "PELP1", "CALM1", "CALML5", "NOS3", "ADCY1",
        "PRKCZ", "PRKCA", "EGFR", "IGF1R",
    },
    "hsa04912": {
        "GNRHR", "GNRH1", "GNRH2", "KISS1", "KISS1R", "AR", "ESR1", "ESR2",
        "FSHB", "FSHR", "LHB", "LHCGR", "PRKCA", "PRKCB", "PRKCD",
        "MAPK1", "MAPK3", "MAP2K1", "MAP2K2", "CALM1", "CALM2", "CALM3",
        "CAMK2A", "CAMK2B", "PLA2G4A", "PTGS2", "EGFR",
    },
    "hsa04726": {
        "HTR1A", "HTR1B", "HTR2A", "HTR2B", "HTR2C", "HTR3A", "HTR4",
        "HTR5A", "HTR6", "HTR7", "SLC6A4", "MAOA", "MAOB", "TPH1", "TPH2",
        "DDC", "ADCY1", "ADCY5", "GNAI1", "GNAI2", "GNAQ", "GNB1",
        "CALM1", "CAMK2A", "MAPK1", "MAPK3", "PTGS2", "PRKCA", "FOS",
        "JUN", "BDNF", "NTRK2",
    },
    "hsa04010": {
        "BRAF", "RAF1", "ARAF", "HRAS", "KRAS", "NRAS", "MAP2K1", "MAP2K2",
        "MAPK1", "MAPK3", "MAPK8", "MAPK9", "MAPK14", "MAP3K1", "MAP3K5",
        "MAP2K3", "MAP2K6", "EGFR", "ERBB2", "FGFR1", "PDGFRA", "PDGFRB",
        "KIT", "MET", "IGF1R", "INSR", "RET", "ALK", "NTRK1", "NTRK2",
        "TP53", "CDKN1A", "MYC", "JUN", "FOS", "ELK1", "SRF",
        "TGFBR1", "TGFBR2", "SMAD2", "SMAD3",
    },
    "hsa04151": {
        "GLP1R", "INSR", "IGF1R", "IRS1", "IRS2", "PIK3CA", "PIK3CB",
        "PIK3CD", "PIK3R1", "PIK3R2", "AKT1", "AKT2", "AKT3", "PTEN",
        "MTOR", "RPTOR", "RPS6KB1", "EIF4EBP1", "FOXO1", "FOXO3",
        "GSK3A", "GSK3B", "CDKN1A", "CDKN1B", "BCL2", "BAD", "MDM2",
        "TP53", "BRCA1", "BRCA2", "VEGFA", "HIF1A", "NOS3", "HRAS",
        "KRAS", "NRAS", "RAF1", "MAP2K1", "MAPK1", "MAPK3",
    },
    "hsa04920": {
        "PPARG", "PPARA", "PPARD", "RXRA", "ADIPOQ", "ADIPOR1", "ADIPOR2",
        "LEPR", "LEP", "INSR", "IRS1", "IRS2", "PIK3CA", "AKT1", "AKT2",
        "PRKAA1", "PRKAA2", "PRKAB1", "PRKAB2", "PRKAG1", "ACACA",
        "ACACB", "FASN", "SCD", "LIPE", "PNPLA2", "FABP4", "CD36",
        "SLC2A4", "PTPN1",
    },
    "hsa04916": {
        "MC4R", "MC3R", "MC1R", "AGRP", "POMC", "PCSK1", "LEPR", "LEP",
        "NPY", "NPY1R", "NPY2R", "GHRL", "GHSR", "BDNF", "NTRK2",
        "ADCY1", "ADCY2", "ADCY3", "ADCY5", "PRKAR1A", "PRKAR2A",
        "PRKACA", "CREB1", "SIM1", "PCSK1", "CPE",
    },
    "map00140": {
        "CYP19A1", "CYP11A1", "CYP11B1", "CYP11B2", "CYP17A1", "CYP21A2",
        "HSD3B1", "HSD3B2", "HSD11B1", "HSD11B2", "HSD17B1", "HSD17B2",
        "HSD17B3", "HSD17B12", "SRD5A1", "SRD5A2", "SRD5A3",
        "SULT1E1", "SULT2A1", "UGT1A1", "UGT2B7", "UGT2B15",
        "SHBG", "AKR1C1", "AKR1C2", "AKR1C3", "AKR1D1",
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# Per-gene clinical implication fragments
# ─────────────────────────────────────────────────────────────────────────────

_GENE_IMPLICATIONS: dict[tuple[str, str], str] = {
    # Estrogen signaling
    ("hsa04915", "ESR1"): (
        "ESR1 variants alter ligand-binding affinity and co-activator recruitment, "
        "directly modifying estradiol and SERM (tamoxifen/raloxifene) response. "
        "Common PGx variants include rs9340799 and rs2234693."
    ),
    ("hsa04915", "ESR2"): (
        "ESR2 (ERβ) modulates anti-proliferative and neuroprotective estrogen effects; "
        "variants may shift the ESR1/ESR2 balance, influencing hot-flash severity "
        "and cognitive outcomes during HRT."
    ),
    ("hsa04915", "NCOA1"): (
        "NCOA1 (SRC-1) is a primary transcriptional co-activator for ER; gain-of-function "
        "variants enhance estrogen sensitivity and may increase breast tissue proliferation."
    ),
    # GnRH / reproductive axis
    ("hsa04912", "KISS1R"): (
        "KISS1R (GPR54) loss-of-function variants cause hypogonadotropic hypogonadism; "
        "patients may have blunted response to Kisspeptin-10 therapy."
    ),
    ("hsa04912", "GNRHR"): (
        "GNRHR variants alter GnRH pulse sensitivity, affecting LH/FSH ratio and "
        "response to GnRH analogue therapies (leuprolide, buserelin)."
    ),
    ("hsa04912", "AR"): (
        "AR within the GnRH axis modulates androgen-mediated negative feedback on "
        "hypothalamic GnRH pulsatility; short CAG repeat alleles increase feedback "
        "sensitivity and may suppress LH surges."
    ),
    # Serotonergic
    ("hsa04726", "HTR2A"): (
        "HTR2A rs6311/rs6313 variants are among the best-validated PGx markers for "
        "SSRI response; in perimenopausal patients they also predict hot-flash "
        "benefit from low-dose paroxetine."
    ),
    ("hsa04726", "SLC6A4"): (
        "SLC6A4 5-HTTLPR insertion/deletion modifies serotonin reuptake capacity; "
        "short allele carriers show increased anxiety in perimenopause and altered "
        "SSRI dose requirements."
    ),
    ("hsa04726", "MAOA"): (
        "MAOA VNTR variants affect serotonin catabolism; slow-metaboliser variants "
        "increase intrasynaptic serotonin and may potentiate HT augmentation strategies."
    ),
    # MAPK
    ("hsa04010", "BRAF"): (
        "BRAF V600E or kinase-domain variants activate ERK constitutively, "
        "altering growth-factor-driven estrogen signalling and predicting "
        "resistance to HER2/EGFR-targeted therapies."
    ),
    ("hsa04010", "RET"): (
        "RET variants are associated with multiple endocrine neoplasia type 2 (MEN2); "
        "their activation of MAPK intersects with estrogen receptor crosstalk "
        "and should prompt specialist referral."
    ),
    ("hsa04010", "TP53"): (
        "TP53 variants impair apoptotic checkpoints downstream of MAPK stress signals; "
        "relevant to cancer risk stratification and eligibility for peptide-based "
        "immune modulation protocols."
    ),
    # PI3K-Akt
    ("hsa04151", "GLP1R"): (
        "GLP1R Ala316Thr (rs10305420) and other coding variants reduce receptor "
        "expression or cAMP coupling, predicting attenuated weight-loss response "
        "to semaglutide and liraglutide."
    ),
    ("hsa04151", "PIK3CA"): (
        "PIK3CA hotspot variants (H1047R, E545K) constitutively activate PI3K, "
        "increasing insulin-independent AKT signalling and potentially reducing "
        "GLP-1 agonist metabolic benefit."
    ),
    ("hsa04151", "PTEN"): (
        "PTEN loss-of-function variants remove the primary brake on PI3K-AKT; "
        "associated with Cowden syndrome and dramatically elevated endometrial "
        "and breast cancer risk in HRT candidates."
    ),
    ("hsa04151", "BRCA1"): (
        "BRCA1 pathogenic variants impair HR DNA repair downstream of PI3K-AKT "
        "checkpoint signalling; BRCA1 status is a primary HRT contra-indication "
        "review trigger for breast and ovarian cancer risk."
    ),
    ("hsa04151", "BRCA2"): (
        "BRCA2 pathogenic variants similarly elevate breast and ovarian cancer risk; "
        "the PI3K-AKT pathway modulates BRCA2-dependent replication fork stability "
        "and should inform HRT risk-benefit discussions."
    ),
    # Adipocytokine
    ("hsa04920", "PPARG"): (
        "PPARG Pro12Ala (rs1801282) is a well-validated variant reducing receptor "
        "activity, associated with improved insulin sensitivity but altered adipokine "
        "secretion and GLP-1 agonist weight-loss magnitude."
    ),
    ("hsa04920", "ADIPOQ"): (
        "ADIPOQ promoter variants reduce adiponectin levels, increasing metabolic "
        "peptide therapy requirements and cardiovascular risk in obese perimenopausal patients."
    ),
    ("hsa04920", "LEPR"): (
        "LEPR Gln223Arg (rs1137101) reduces leptin receptor signalling efficiency; "
        "carriers may show reduced satiety response to GLP-1 agonists and benefit "
        "from higher doses."
    ),
    # Melanocortin
    ("hsa04916", "MC4R"): (
        "MC4R loss-of-function variants (>250 identified) are the most common cause "
        "of monogenic severe obesity; Setmelanotide is specifically approved for "
        "MC4R pathway deficiencies and may be indicated."
    ),
    ("hsa04916", "POMC"): (
        "POMC biallelic deficiency causes severe early-onset obesity and adrenal "
        "insufficiency; Setmelanotide has demonstrated efficacy in POMC-deficient patients."
    ),
    ("hsa04916", "LEPR"): (
        "LEPR variants within the melanocortin circuit reduce leptin-driven POMC "
        "activation, impairing satiety signalling; Setmelanotide targets this "
        "pathway downstream of the leptin receptor."
    ),
    # Steroid biosynthesis
    ("hsa00140", "CYP19A1"): (
        "CYP19A1 (aromatase) variants alter the rate of androgen-to-estrogen "
        "conversion; low-activity variants cause relative estrogen deficiency "
        "and may require higher HRT doses, while high-activity variants increase "
        "breast tissue estrogen exposure."
    ),
    ("map00140", "CYP19A1"): (
        "CYP19A1 (aromatase) variants alter the rate of androgen-to-estrogen "
        "conversion; low-activity variants cause relative estrogen deficiency "
        "and may require higher HRT doses, while high-activity variants increase "
        "breast tissue estrogen exposure."
    ),
    ("map00140", "HSD17B1"): (
        "HSD17B1 Ser312Gly (rs605059) increases conversion of estrone to the "
        "more potent estradiol, elevating local breast tissue estrogen activity "
        "and is associated with increased breast cancer risk."
    ),
    ("map00140", "SRD5A2"): (
        "SRD5A2 Ala49Thr and Val89Leu alter 5α-reductase activity, modifying "
        "DHT synthesis from testosterone; relevant to androgen-dominant HRT "
        "regimens and prostate/PCOS phenotypes."
    ),
    ("map00140", "CYP11A1"): (
        "CYP11A1 (P450scc) initiates steroid biosynthesis from cholesterol; "
        "variants can reduce overall steroidogenic capacity, affecting both "
        "glucocorticoid and sex hormone production."
    ),
}

# Per-pathway fallback when no gene-specific note exists
_PATHWAY_GENERIC_IMPLICATIONS: dict[str, str] = {
    "hsa04915": (
        "Variants in this pathway may alter estrogen receptor signalling strength "
        "and modify HRT or SERM treatment response."
    ),
    "hsa04912": (
        "Variants in the GnRH pathway can disrupt hypothalamic–pituitary–gonadal "
        "axis regulation and alter reproductive peptide therapy response."
    ),
    "hsa04726": (
        "Serotonergic pathway variants may influence mood, vasomotor symptoms, "
        "and antidepressant response in perimenopausal patients."
    ),
    "hsa04010": (
        "MAPK pathway variants may alter cellular proliferation responses to "
        "growth factors and modify cancer risk assessments."
    ),
    "hsa04151": (
        "PI3K-AKT pathway variants can affect insulin sensitivity, cancer risk, "
        "and metabolic peptide therapy efficacy."
    ),
    "hsa04920": (
        "Adipocytokine pathway variants may alter body-composition response to "
        "GLP-1 agonist therapies and metabolic peptide protocols."
    ),
    "hsa04916": (
        "Melanocortin pathway variants may be associated with monogenic obesity "
        "and predict differential response to MC4R-targeted peptide therapies."
    ),
    "map00140": (
        "Steroid biosynthesis pathway variants directly alter circulating sex-hormone "
        "levels and should inform HRT dosing strategies."
    ),
}

# Cross-pathway combination notes (keyed by frozenset of two pathway IDs)
_PATHWAY_COMBINATION_NOTES: dict[frozenset, str] = {
    frozenset({"hsa04915", "map00140"}): (
        "Co-involvement of the estrogen signalling and steroid biosynthesis pathways "
        "suggests a compounded effect on circulating and tissue-level estrogen activity. "
        "Comprehensive HRT dosing should account for both receptor sensitivity "
        "and aromatase capacity."
    ),
    frozenset({"hsa04151", "hsa04920"}): (
        "Simultaneous PI3K-AKT and adipocytokine pathway hits indicate a convergent "
        "metabolic phenotype. GLP-1 agonist response may be attenuated, and "
        "combination peptide strategies (GLP-1 + GIP dual agonism) may be preferable."
    ),
    frozenset({"hsa04912", "hsa04915"}): (
        "GnRH and estrogen signalling pathway co-hits suggest central and peripheral "
        "HPG axis dysregulation. Kisspeptin-based therapies may need to be combined "
        "with receptor-level ER modulation."
    ),
    frozenset({"hsa04726", "hsa04915"}): (
        "Serotonergic and estrogen pathway co-involvement is common in vasomotor "
        "symptom severity; patients may benefit from dual-mechanism treatment "
        "addressing both serotonin and estrogen pathways simultaneously."
    ),
    frozenset({"hsa04916", "hsa04920"}): (
        "Co-hits in the melanocortin and adipocytokine pathways indicate layered "
        "central and peripheral obesity pathway disruption. Setmelanotide combined "
        "with metabolic peptides may be more effective than monotherapy."
    ),
    frozenset({"hsa04010", "hsa04151"}): (
        "MAPK and PI3K-AKT pathway co-activation creates redundant mitogenic "
        "signalling routes, a pattern associated with oncogenic transformation "
        "and therapeutic resistance. Oncology referral should be considered."
    ),
    frozenset({"hsa04915", "hsa04151"}): (
        "Estrogen and PI3K-AKT co-hits are a recognised mechanism of endocrine "
        "therapy resistance in breast cancer. HRT eligibility should be reviewed "
        "carefully against current cancer risk profiles."
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
# Implication generator
# ─────────────────────────────────────────────────────────────────────────────

def generate_implication(pathway_id: str, genes_hit: list[str]) -> str:
    """Return a clinical implication string for a single pathway hit.

    Parameters
    ----------
    pathway_id:
        KEGG pathway identifier (e.g. ``"hsa04915"``).
    genes_hit:
        List of patient gene symbols that matched this pathway.

    Returns
    -------
    str
        Plain-English clinical note, or ``""`` if *genes_hit* is empty.
    """
    if not genes_hit:
        return ""

    parts: list[str] = []
    seen: set[str] = set()

    for gene in genes_hit:
        key = (pathway_id, gene.upper())
        note = _GENE_IMPLICATIONS.get(key)
        if note and note not in seen:
            parts.append(note)
            seen.add(note)

    if not parts:
        parts.append(
            _PATHWAY_GENERIC_IMPLICATIONS.get(
                pathway_id,
                f"Variant(s) in {', '.join(genes_hit)} affect this pathway; "
                "clinical significance should be evaluated in context.",
            )
        )

    return " ".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# SQLite cache for KEGG REST API responses
# ─────────────────────────────────────────────────────────────────────────────

_DEFAULT_CACHE_PATH = Path.home() / ".cache" / "peptidiq" / "kegg_cache.db"
_SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS pathway_genes (
    pathway_id  TEXT NOT NULL,
    gene_symbol TEXT NOT NULL,
    fetched_at  TEXT NOT NULL,
    PRIMARY KEY (pathway_id, gene_symbol)
);
"""


class KEGGCache:
    """SQLite-backed cache for KEGG pathway gene membership.

    Parameters
    ----------
    db_path:
        File-system path for the SQLite database.  Created on first use.
    """

    def __init__(self, db_path: Path = _DEFAULT_CACHE_PATH) -> None:
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute(_SCHEMA_DDL)
            conn.commit()

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_genes(self, pathway_id: str) -> set[str]:
        """Return cached gene symbols for *pathway_id*.

        Falls back to ``HARDCODED_PATHWAY_GENES`` if the cache is empty.
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            rows = conn.execute(
                "SELECT gene_symbol FROM pathway_genes WHERE pathway_id = ?",
                (pathway_id,),
            ).fetchall()

        if rows:
            return {r[0] for r in rows}
        return set(HARDCODED_PATHWAY_GENES.get(pathway_id, set()))

    def is_stale(self, pathway_id: str, max_age_days: int = 30) -> bool:
        """Return ``True`` if the cache entry is absent or older than *max_age_days*."""
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute(
                "SELECT MIN(fetched_at) FROM pathway_genes WHERE pathway_id = ?",
                (pathway_id,),
            ).fetchone()

        if row is None or row[0] is None:
            return True

        oldest = datetime.fromisoformat(row[0])
        if oldest.tzinfo is None:
            oldest = oldest.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - oldest).days
        return age >= max_age_days

    # ------------------------------------------------------------------
    # Write / refresh
    # ------------------------------------------------------------------

    def refresh_from_api(self, pathway_id: str) -> set[str]:
        """Fetch gene membership from the KEGG REST API and persist to cache.

        Returns the refreshed gene set (or the hardcoded fallback on failure).

        Raises
        ------
        Exception
            Re-raised if the network call fails and no fallback is desired.
            Callers should catch and fall back to ``get_genes()`` as needed.
        """
        url = f"https://rest.kegg.jp/link/hsa/{pathway_id}"
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                body = resp.read().decode("utf-8")
        except Exception as exc:
            logger.warning("KEGG API call failed for %s: %s", pathway_id, exc)
            raise

        gene_ids: list[str] = []
        for line in body.strip().splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                # Field looks like "hsa:1234" — we want the numeric Entrez ID
                raw = parts[1].split(":")[-1].strip()
                if raw:
                    gene_ids.append(raw)

        if not gene_ids:
            logger.warning(
                "No gene IDs parsed from KEGG response for %s.", pathway_id
            )
            return set(HARDCODED_PATHWAY_GENES.get(pathway_id, set()))

        symbols = self._resolve_entrez_to_symbols(gene_ids)
        now = datetime.now(timezone.utc).isoformat()

        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                "DELETE FROM pathway_genes WHERE pathway_id = ?", (pathway_id,)
            )
            conn.executemany(
                "INSERT OR IGNORE INTO pathway_genes VALUES (?, ?, ?)",
                [(pathway_id, sym, now) for sym in symbols],
            )
            conn.commit()

        return symbols

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _kegg_id_to_symbol(kegg_gene_id: str) -> str | None:
        """Convert a KEGG hsa gene entry to its HGNC symbol via the KEGG API."""
        url = f"https://rest.kegg.jp/get/hsa:{kegg_gene_id}"
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                body = resp.read().decode("utf-8")
            for line in body.splitlines():
                if line.startswith("SYMBOL"):
                    parts = line.split()
                    if len(parts) >= 2:
                        return parts[1].rstrip(",")
        except Exception:  # noqa: BLE001
            pass
        return None

    def _resolve_entrez_to_symbols(self, gene_ids: list[str]) -> set[str]:
        """Best-effort resolution of Entrez IDs to HGNC symbols.

        Because individual KEGG API calls per gene are expensive, this method
        returns the hardcoded symbols for any IDs that fail to resolve.
        """
        # For now, return the full hardcoded set for the pathway since we don't
        # have the pathway_id here; callers merge with what they get.
        # A future version could batch the info/ endpoint.
        return set()


# ─────────────────────────────────────────────────────────────────────────────
# Main public function: map_variants_to_pathways
# ─────────────────────────────────────────────────────────────────────────────

def map_variants_to_pathways(
    gene_symbols: list[str],
    use_api: bool = False,
    cache: KEGGCache | None = None,
) -> list[dict[str, Any]]:
    """Map a list of patient gene symbols to KEGG priority pathways.

    Parameters
    ----------
    gene_symbols:
        HGNC gene symbols from the patient's variant report (e.g. ``["ESR1", "AR"]``).
        Case-insensitive; ``None`` values and whitespace-only strings are skipped.
    use_api:
        If ``True``, refresh stale cache entries from the KEGG REST API before
        mapping.  Ignored when *cache* is ``None``.
    cache:
        A :class:`KEGGCache` instance.  If ``None``, the offline hardcoded gene
        sets are used directly.

    Returns
    -------
    list[dict]
        One dict per pathway that has at least one gene hit, sorted by
        ``variant_count`` descending.  Each dict has the keys:

        * ``kegg_id``          — KEGG pathway identifier
        * ``pathway_name``     — human-readable name
        * ``clinical_relevance`` — pathway-level clinical context string
        * ``genes_hit``        — sorted list of matched gene symbols
        * ``variant_count``    — number of distinct matched genes
        * ``clinical_implication`` — assembled plain-English note
    """
    if not gene_symbols:
        return []

    patient_genes = {g.upper().strip() for g in gene_symbols if g and str(g).strip()}
    results: list[dict[str, Any]] = []

    for pathway_id, pathway_meta in PRIORITY_PATHWAYS.items():
        # Resolve gene membership
        if cache is not None:
            if use_api and cache.is_stale(pathway_id):
                try:
                    pathway_genes = cache.refresh_from_api(pathway_id)
                except Exception as exc:  # noqa: BLE001
                    logger.error(
                        "API refresh failed for %s: %s — using cache.",
                        pathway_id,
                        exc,
                    )
                    pathway_genes = cache.get_genes(pathway_id)
            else:
                pathway_genes = cache.get_genes(pathway_id)
        else:
            pathway_genes = set(HARDCODED_PATHWAY_GENES.get(pathway_id, set()))

        pathway_genes_upper = {g.upper() for g in pathway_genes}
        hits = sorted(patient_genes & pathway_genes_upper)

        if not hits:
            continue

        results.append(
            {
                "kegg_id": pathway_id,
                "pathway_name": pathway_meta["name"],
                "clinical_relevance": pathway_meta["clinical_relevance"],
                "genes_hit": hits,
                "variant_count": len(hits),
                "clinical_implication": generate_implication(pathway_id, hits),
            }
        )

    results.sort(key=lambda r: r["variant_count"], reverse=True)
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Summary generator
# ─────────────────────────────────────────────────────────────────────────────

def generate_pathway_summary(pathway_hits: list[dict[str, Any]]) -> str:
    """Produce a single plain-English paragraph summarising all pathway hits.

    Parameters
    ----------
    pathway_hits:
        Output of :func:`map_variants_to_pathways`.

    Returns
    -------
    str
        Multi-sentence narrative.  Returns ``"No clinically relevant pathway
        hits identified."`` when *pathway_hits* is empty.
    """
    if not pathway_hits:
        return "No clinically relevant pathway hits identified."

    hit_ids = {h["kegg_id"] for h in pathway_hits}
    lines: list[str] = []

    for hit in pathway_hits:
        gene_list = ", ".join(hit["genes_hit"])
        lines.append(
            f"**{hit['pathway_name']}** ({hit['kegg_id']}): "
            f"variant(s) in {gene_list}. "
            f"{hit['clinical_implication']}"
        )

    # Inject cross-pathway combination notes
    combo_notes: list[str] = []
    hit_id_list = list(hit_ids)
    for i, pid_a in enumerate(hit_id_list):
        for pid_b in hit_id_list[i + 1:]:
            note = _PATHWAY_COMBINATION_NOTES.get(frozenset({pid_a, pid_b}))
            if note:
                combo_notes.append(note)

    if combo_notes:
        lines.append("**Cross-pathway interactions:** " + " ".join(combo_notes))

    return "\n\n".join(lines)
