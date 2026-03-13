# Interpretation

---

## Tiers

| Tier | Emoji | Score | Trigger |
|------|-------|-------|---------|
| Critical | 🔴 | 1000 | `clinvar = "pathogenic"` |
| High | 🟠 | ≥ 100 | Likely pathogenic or high-impact consequence without benign signal |
| Medium / VUS | 🟡 | ≥ 30 | VUS or moderate consequence without clinical classification |
| Low | 🟢 | < 30 | Benign, likely benign, or gnomAD AF ≥ 5% |
| Carrier | 🔵 | any (halved) | Heterozygous in a recessive gene |

Low-tier findings hidden by default. Users can toggle on.

---

## Consumer categories

| Category | V1 |
|----------|----|
| Hereditary Conditions — pathogenic + likely pathogenic | Yes |
| Uncertain Findings — VUS with population + functional data | Yes |
| Carrier Status — heterozygous in recessive genes | Yes |
| Medication Response — CYP2C19, CYP2D6, VKORC1, etc. | No (V2) |
| Wellness Insights — trait associations | No (V2) |

---

## ACMG floor

Every variant in the ACMG SF v3.2 gene list (81 genes) must appear in results regardless of score. A pathogenic ACMG SF variant missing from output is a product failure.

Reference: https://www.gimjournal.org/article/S1098-3600(22)00887-2/fulltext

---

## VUS policy

VUS findings are surfaced, not hidden. Card shows: population frequency, functional consequence, any published classification context.

Default language: "This variant is classified as having uncertain significance (VUS). The scientific community has not reached consensus on whether this variant affects health."

`[SASANK REVIEW: revise this language]`

---

## Carrier policy

Default card text: "As a carrier of a recessive variant, you typically will not be affected. This may be relevant for family planning."

`[SASANK REVIEW: list genes needing condition-specific carrier language — CFTR, HBB, GJB2, HEXA]`

---

## Condition library

Keyed by `condition_key` (OMIM preferred, MedGen fallback, ClinVar UID last resort). The API layer looks up `condition_key` from each engine result in Postgres and merges the curated fields into the response.

**Status: schema done, content missing.**

**How content gets built:**
- Curtis auto-generates base rows from ClinVar/OMIM bulk data (structured fields: `condition_key`, `condition_display_name`, `gene_symbols`, `inheritance_pattern`, `acmg_sf`)
- Sasank reviews and writes the consumer-facing text fields: `plain_description`, `action_guidance`, `vus_notes`, `carrier_note_override`

Sasank is the clinical communication layer, not the data entry layer.

### Schema

| Column | Who fills it | Description |
|--------|-------------|-------------|
| `condition_key` | Curtis (auto) | OMIM ID, MedGen ID, or ClinVar disease ID |
| `condition_display_name` | Curtis (auto) | Clean UI name |
| `gene_symbols` | Curtis (auto) | Associated genes, comma-separated |
| `inheritance_pattern` | Curtis (auto) | Autosomal dominant / recessive / X-linked / Mitochondrial |
| `acmg_sf` | Curtis (auto) | On ACMG SF v3.2 list? (boolean) |
| `plain_description` | **Sasank** | 2-3 sentences for a non-scientist |
| `action_guidance` | **Sasank** | One concrete next step |
| `vus_notes` | **Sasank** | Gene-specific VUS language |
| `carrier_note_override` | **Sasank** | Override default carrier text where needed (CFTR, HBB, GJB2, HEXA, etc.) |
| `prevalence` | Curtis (auto) | Approximate population prevalence |
| `last_reviewed` | Sasank | Date of last clinical review |

Priority: all 81 ACMG SF genes before launch. Start with BRCA1, TP53, LDLR, RYR1.

---

## Next steps

1. **Curtis** — auto-generate the base condition library CSV from ClinVar/OMIM for all 81 ACMG SF genes (structured fields only); share with Sasank so he has a pre-filled sheet to write into, not a blank one
2. **Sasank** — write `plain_description` and `action_guidance` for BRCA1, TP53, LDLR, RYR1; focus on clarity and not scaring people — a user who reads this should understand what it means and have one concrete thing to do next
3. **Sasank** — write the VUS and carrier interpretation guidelines as a short markdown doc (can live in `docs/interpretation.md` or a new `docs/clinical-voice.md`): how should findings be framed, what language avoids panic, how do we handle "the jury is out" findings
