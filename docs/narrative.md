# U4U — Narrative

> **Status:** Draft. Sasank to review and revise clinical framing. Curtis to review mission/product framing.

---

## What we are building

U4U is a personal genomics interpretation platform. It takes a raw genome file — the kind you already have from 23andMe, AncestryDNA, or a clinical sequencing lab — and tells you what is actually in it, in plain English, backed by the latest published science.

Most people who have had a genetic test have a file sitting on their computer that they cannot read. The companies that ran the test gave them a simplified dashboard, told them their ancestry and a handful of traits, and stopped there. The raw data — thousands of variants that could be clinically meaningful — was never explained to them. U4U exists to close that gap.

---

## The problem we are solving

When a clinical lab sequences your genome, they are legally required to report a specific list of findings — the ACMG Secondary Findings gene list (currently 81 genes). If you have a pathogenic variant in one of those genes, they tell you. If you don't, or if your variant is of uncertain significance, or if it's in a gene not on that mandatory list — they say nothing.

That mandatory list is the floor, not the ceiling. The published scientific literature on genomic variants extends well beyond it. Variants of uncertain significance (VUS) may have real data suggesting elevated risk even without formal consensus. Pharmacogenomic variants affect how your body processes dozens of common medications. Carrier status for recessive conditions is directly relevant to family planning.

None of this is being communicated to people. U4U communicates it.

---

## How we are different from 23andMe and existing tools

23andMe tells you whether you have "increased risk" for a small number of FDA-approved conditions, using simplified language and deliberately incomplete results. They are constrained by regulatory approval processes and liability concerns into providing the minimum.

U4U is not a clinical diagnostic service. We do not diagnose, prescribe, or replace physicians. We collate what the scientific literature and clinical databases say about a person's specific variants and present it clearly, with appropriate context, with links to primary sources, and with an honest account of how certain or uncertain each finding is. 

The distinction matters: we are an information platform, not a medical device. We are doing what a well-read, genetics-literate friend would do — explaining what the research says, without pretending the research is the final word.

---

## Who this is for

**Primary user — V1:** Someone who already has a 23andMe or AncestryDNA raw data file and wants to know more than the company told them. They are health-conscious, probably 25–45, have some comfort with technology, and are frustrated that they paid for a test and received limited information. They do not need to understand genomics; they need to understand their results.

**Secondary user — V1:** A person who received a VCF file from a clinical sequencing lab and wants a second layer of interpretation beyond what the lab report said. Often a patient who was told "we found a VUS" and received no useful follow-up explanation.

**Not in scope for V1:** Clinicians ordering tests on behalf of patients. Researchers. People who do not already have a genome file. Direct-to-consumer sequencing (we are an interpretation layer, not a sequencing service).

---

## What we believe about the information we provide

We believe people have the right to understand their own genomic data. The information we display is already in public databases — ClinVar, gnomAD, the ACMG guidelines, the published literature. We are not revealing anything that does not already exist. We are making it accessible.

We are not reckless about this. We are deliberate about the difference between:
- **Known pathogenic:** ClinVar consensus, peer-reviewed, high confidence. We say so clearly.
- **Likely pathogenic / likely benign:** Strong evidence but not definitive. We say that too.
- **VUS (variant of uncertain significance):** The jury is genuinely out. We present the available data honestly — including frequency in the population, functional consequence, and any relevant research — without pretending there is consensus when there isn't. We do not suppress this information. We contextualise it.
- **Carrier status:** Carrying one copy of a recessive variant typically does not cause disease. We explain this clearly and flag it separately so it is not confused with a risk finding.

Every finding that could cause alarm links to its primary source. We are not guessing. We are citing.

---

## What we are not building

- A diagnostic tool that tells people they have a disease
- A replacement for genetic counseling
- A platform that makes clinical recommendations ("take this medication," "have this surgery")
- A research database or clinical trial matching service (not in V1)
- A sequencing service

---

## The name

U4U — "You for You." The data is yours. The interpretation is for you.

---

*This document is maintained by the team. If something in here is wrong, change it — do not work around it.*
