# Project Status

---

## MVP scope

VCF upload → annotation engine → interactive dashboard. No genome storage. Email capture for future research updates. Target: 4 weeks.

---

## What works

- Parses VCF / `.vcf.gz` (MVP primary), 23andMe `.txt`, CSV, rsID lists
- 10-step pipeline: validate → parse → quality filter → whitelist → rsID resolution → deduplicate → annotate → score → summarize → sort
- Annotates against ClinVar, gnomAD, Ensembl VEP (retry + fallback)
- Returns plain-English headline, consequence, rarity, action hint per variant
- CI on push via GitHub Actions (Python 3.11 and 3.12)

---

## Repo

```
engine/         core pipeline
  annotators/   ClinVar, gnomAD, VEP, MyVariant modules
  pipeline.py   run_pipeline() entry point
  scoring.py    scoring + tier logic
  summary.py    plain-English text generation
tests/          pipeline tests
data/           rsID filter files
docs/           documentation
.github/        CI, issue templates, PR template
```

---

## What doesn't exist

| Area | Missing | Owner |
|------|---------|-------|
| Web API | Docker build, K8s deployment, public URL | Hampton |
| Database | Postgres instance running (schema exists in `db/schema.sql`) | Hampton |
| Condition library | 81 ACMG SF rows (4 needed immediately: BRCA1, TP53, LDLR, RYR1) | Sasank |
| Frontend | Upload, processing, results screens | Tom (build) + Rocky (design) |
| Infrastructure | Domain registration, DNS, CI/CD auto-deploy | Hampton + Curtis |
| Security/legal | Security audit execution, LLC incorporation | Cane + Curtis |

---

## Immediate blockers

| Blocker | Resolves when |
|---------|--------------|
| No URL | Hampton deploys FastAPI + Docker to K8s; Curtis registers domain |
| No condition library | Sasank writes 4 rows (BRCA1, TP53, LDLR, RYR1) |
| No branded email | Jeran sets up Google Workspace |

---

## Team

| Person | Owns | Read first |
|--------|------|-----------|
| Curtis | Engine, docs, product, domain | — |
| Hampton | FastAPI, Postgres, Docker, K8s | `architecture.md`, `pipeline.md`, `integrations.md` |
| Sasank | Condition library, clinical review | `interpretation.md` |
| Tom | Frontend | `architecture.md`, UI spec below |
| Rocky | Visual design | UI spec below, `interpretation.md` |
| Jeran | Marketing, users, brand | roadmap Phase 4 |
| Cane | Security, privacy policy | `integrations.md` (what leaves the system) |

---

## UI spec

### Screen 1 — Upload
- File drop (23andMe `.txt`, `.vcf`, `.vcf.gz`, `.csv`; max 100 MB)
- Consent checkbox required before submit
- Panel selector (collapsed by default): ACMG SF v3.2 always on; pharmacogenomics + carrier screening optional
- Analyze button disabled until file + checkbox

### Screen 2 — Processing
- Progress bar from `progress_callback(step, pct)`
- Warn on navigation away

### Screen 3 — Results
- Header: count + one-line summary
- Filter chips: 🔴 Critical 🟠 High 🟡 VUS 🟢 Low 🔵 Carrier with counts
- Default: Critical + High shown; "For Your Records" section (medium/low/carrier) collapsed

**Layout:** single-column prioritized findings report — NOT a card grid. Findings are expandable rows with a colored left border (tier color). Two sections: "Needs Attention" (critical + high, always visible) and "For Your Records" (medium + low + carrier, collapsed by default). Full spec in `docs/frontend.md`.

**Row collapsed:** tier color border, tier badge, gene name, headline, action button

**Row expanded:** headline, `consequence_plain`, `zygosity_plain`, `rarity_plain`, `clinvar_plain`, `action_hint`, condition-specific guidance from condition library, source links (ClinVar, gnomAD, ACMG)

**Carrier row:** blue left border, "You appear to be a carrier," `carrier_note`, condition name

**VUS row:** yellow left border, "uncertain significance" language, `consequence_plain`, `rarity_plain`, `frequency_derived_label`

**Disclaimer (persistent):** "This is not medical advice. Discuss significant findings with a healthcare provider."

**Downloadable report:** button to export findings as PDF or structured summary.

**Email capture (on results page):** "Get notified when new research publishes on your variants" — captures email for V2 research feed. No genome stored, no account required in V1.

### Error states

| State | Behavior |
|-------|----------|
| File too large / unsupported format | Inline error before submit |
| Invalid VCF header | Error screen after submit |
| All variants filtered | Results page with explanation |
| Zero ACMG findings | Message, not blank |
| Network error | Error screen with retry |
| Partial results | Show succeeded, note how many failed |

---

## Not in V1

User accounts, saved results, email delivery, pharmacogenomics, research tracking, PRS, mobile, API access for external developers.

Roadmap: `docs/roadmap.md`

---

## Next steps

1. **Sasank** — share the condition library CSV (even 4 rows) in Slack or Drive so Rocky can design against real disease names and Tom can use real `action_guidance` text instead of placeholder copy
2. **Hampton** — share the K8s cluster's external IP or hostname so Curtis can register the domain and point DNS before the API is deployed; these can happen in parallel
3. **Tom + Rocky** — read `docs/frontend.md` for the full UI spec (expandable rows, not cards); Rocky designs collapsed + expanded states for one Critical finding and one Carrier finding before Tom writes any code
