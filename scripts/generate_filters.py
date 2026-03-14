#!/usr/bin/env python3
"""
scripts/generate_filters.py
============================
Fetch all Pathogenic / Likely Pathogenic ClinVar variants for the 81 ACMG
Secondary Findings v3.2 genes and write their rsIDs to data/acmg81_rsids.txt.

Usage
-----
    # First time (or to refresh):
    NCBI_API_KEY=<your_key> python scripts/generate_filters.py

    # Without a key (rate-limited to 3 req/s — will be slow):
    python scripts/generate_filters.py

    # Override output path:
    python scripts/generate_filters.py --out data/acmg81_rsids.txt

Requirements
------------
    pip install requests          # already in engine[vcf] extras

Why rsID-based filtering?
-------------------------
The pipeline filters at step 4 by checking whether a variant's rsID appears
in the whitelist.  This catches all *known* pathogenic variants indexed in
ClinVar.  Novel / private variants (no rsID) bypass the filter — acceptable
for ACMG SF, which is limited to well-characterised actionable conditions.

For VCF analysis where you want to catch ALL high-impact variants in ACMG
genes (not just known pathogenic ones), set FILTERS="" in .env to run
unfiltered, or add a coordinate-based gene filter in a future engine version.

ACMG SF v3.2 — 81 genes (PMID 36737814)
-----------------------------------------
Organised by condition category, as per the 2023 ACMG recommendation.
"""

import argparse
import os
import sys
import time
from typing import Optional

try:
    import requests
except ImportError:
    sys.exit("requests not installed — run: pip install requests")


# ── ACMG SF v3.2 — 81 gene symbols ───────────────────────────────────────────

ACMG_SF_GENES = [
    # Hereditary breast / ovarian cancer
    "BRCA1", "BRCA2", "PALB2", "ATM", "CHEK2",
    # Lynch syndrome / colorectal cancer
    "MLH1", "MSH2", "MSH6", "PMS2", "EPCAM",
    # Familial adenomatous polyposis
    "APC", "MUTYH",
    # Li-Fraumeni syndrome
    "TP53",
    # Peutz-Jeghers
    "STK11",
    # PTEN hamartoma
    "PTEN",
    # Hereditary diffuse gastric cancer
    "CDH1",
    # Juvenile polyposis / hereditary hemorrhagic telangiectasia
    "BMPR1A", "SMAD4",
    # Cowden / Bannayan-Riley-Ruvalcaba
    # (PTEN above)
    # Von Hippel-Lindau
    "VHL",
    # Multiple endocrine neoplasia
    "MEN1", "RET",
    # Hereditary paraganglioma / pheochromocytoma
    "SDHB", "SDHC", "SDHD", "SDHAF2", "MAX", "TMEM127",
    # Retinoblastoma
    "RB1",
    # NF2-related schwannomatosis
    "NF2", "SMARCB1", "LZTR1",
    # Tuberous sclerosis
    "TSC1", "TSC2",
    # WT1 / Wilms tumour
    "WT1",
    # Fumarate hydratase
    "FH",
    # Birt-Hogg-Dubé
    "FLCN",
    # Carney complex
    "PRKAR1A",
    # DICER1
    "DICER1",
    # Mismatch repair / polymerase proofreading
    "MSH3", "NTHL1", "POLE", "POLD1",
    # Hypertrophic cardiomyopathy
    "MYBPC3", "MYH7", "TNNT2", "TNNI3", "TPM1",
    "MYL3", "ACTC1", "PRKAG2", "MYL2",
    # Fabry disease
    "GLA",
    # Dilated cardiomyopathy / arrhythmogenic
    "LMNA", "PKP2", "DSP", "DSC2", "TMEM43", "DSG2",
    # Long QT syndrome / Brugada  (KCNE1 removed from SF v3.2 — now QT-susceptibility only)
    "SCN5A", "KCNQ1", "KCNH2", "KCNE2",
    # Catecholaminergic polymorphic VT
    "RYR2", "CASQ2",
    # Marfan / aortopathy
    "FBN1", "FBN2", "TGFBR1", "TGFBR2", "SMAD3",
    "ACTA2", "MYH11", "COL3A1",
    # Familial hypercholesterolaemia
    "LDLR", "APOB", "PCSK9",
    # Transthyretin amyloidosis
    "TTR",
    # Malignant hyperthermia
    "RYR1", "CACNA1S",
    # Wilson disease
    "ATP7B",
    # Hereditary haemochromatosis
    "HFE",
    # Ornithine transcarbamylase deficiency
    "OTC",
]

assert len(ACMG_SF_GENES) == 81, f"Expected 81 genes, got {len(ACMG_SF_GENES)}"

# ── ClinVar / NCBI helpers ────────────────────────────────────────────────────

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
BATCH_SIZE   = 500   # IDs per efetch call
SLEEP_NO_KEY = 0.34  # ~3 req/s without API key
SLEEP_WITH_KEY = 0.11  # ~10 req/s with API key


def _sleep(api_key: Optional[str]):
    time.sleep(SLEEP_WITH_KEY if api_key else SLEEP_NO_KEY)


def search_clinvar_gene(gene: str, api_key: Optional[str]) -> list[int]:
    """
    Return all ClinVar variation IDs for Pathogenic / Likely Pathogenic
    variants in *gene*.
    """
    query = (
        f"{gene}[gene] AND "
        '("Pathogenic"[ClinSigSimple] OR "Likely Pathogenic"[ClinSigSimple])'
    )
    params = {
        "db":       "clinvar",
        "term":     query,
        "retmax":   10000,
        "retmode":  "json",
        "tool":     "u4u-generate-filters",
        "email":    "u4u@40minutebioscience.com",
    }
    if api_key:
        params["api_key"] = api_key

    resp = requests.get(f"{EUTILS_BASE}/esearch.fcgi", params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    ids  = [int(x) for x in data.get("esearchresult", {}).get("idlist", [])]
    _sleep(api_key)
    return ids


def fetch_rsids_for_ids(var_ids: list[int], api_key: Optional[str]) -> set[str]:
    """
    Fetch ClinVar XML summaries in batches and extract rsIDs.
    """
    rsids: set[str] = set()
    for i in range(0, len(var_ids), BATCH_SIZE):
        chunk = var_ids[i : i + BATCH_SIZE]
        params = {
            "db":      "clinvar",
            "id":      ",".join(str(x) for x in chunk),
            "rettype": "variation",
            "retmode": "json",
            "tool":    "u4u-generate-filters",
            "email":   "u4u@40minutebioscience.com",
        }
        if api_key:
            params["api_key"] = api_key

        resp = requests.get(f"{EUTILS_BASE}/esummary.fcgi", params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        result_set = data.get("result", {})
        for uid, record in result_set.items():
            if uid == "uids":
                continue
            rsid = record.get("rsid") or record.get("rs")
            if rsid and str(rsid).startswith("rs"):
                rsids.add(rsid.strip())
            elif isinstance(rsid, int) and rsid > 0:
                rsids.add(f"rs{rsid}")

        _sleep(api_key)

    return rsids


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default="data/acmg81_rsids.txt",
                        help="Output path (default: data/acmg81_rsids.txt)")
    parser.add_argument("--api-key", default=os.getenv("NCBI_API_KEY"),
                        help="NCBI API key (or set NCBI_API_KEY env var)")
    args = parser.parse_args()

    api_key = args.api_key or None
    if not api_key:
        print("⚠️  No NCBI_API_KEY — rate limited to 3 req/s.  Will be slow.")
        print("   Register free at https://www.ncbi.nlm.nih.gov/account/")

    os.makedirs(os.path.dirname(args.out) if os.path.dirname(args.out) else ".", exist_ok=True)

    all_rsids: set[str] = set()

    for i, gene in enumerate(ACMG_SF_GENES, 1):
        print(f"[{i:02d}/{len(ACMG_SF_GENES)}] {gene} ...", end=" ", flush=True)
        try:
            var_ids = search_clinvar_gene(gene, api_key)
            if not var_ids:
                print("0 variants")
                continue
            rsids = fetch_rsids_for_ids(var_ids, api_key)
            all_rsids.update(rsids)
            print(f"{len(rsids)} rsIDs  (total: {len(all_rsids)})")
        except requests.RequestException as exc:
            print(f"ERROR: {exc}")

    # Write output
    with open(args.out, "w") as f:
        f.write(
            "# ACMG Secondary Findings v3.2 — Pathogenic / Likely Pathogenic rsIDs\n"
            "# Generated by scripts/generate_filters.py\n"
            "# Source: NCBI ClinVar via eUtils API\n"
            "# Refresh periodically to pick up new ClinVar submissions.\n"
        )
        for rsid in sorted(all_rsids):
            f.write(rsid + "\n")

    print(f"\n✅ Wrote {len(all_rsids)} rsIDs → {args.out}")


if __name__ == "__main__":
    main()
