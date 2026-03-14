# Frontend Spec

**Owner:** Tom (build) + Rocky (design)
**Read also:** `docs/project-status.md` (full screen list), `docs/architecture.md` (API contract)

---

## What you're building

Three screens. Upload → Processing → Results.

The results screen is the whole product. A person uploads their genome file, waits ~2 minutes, and gets a plain-English report of what matters and what to do about it. The engine already produces everything — your job is to show it in a way a non-scientist trusts and understands.

---

## The UI direction — not a card grid

23andMe uses card grids. Every health app uses card grids. Don't do that.

This is a **prioritized findings report**, not a social feed. Think about what a genetic counselor would hand someone after an appointment — one clean page, organized by what needs attention first, where the most critical finding is impossible to miss and every result ends with one concrete action. That's the feeling to design toward.

**Layout:** single column, full-width, sectioned by urgency. Not a grid, not tiles. Scannable top-to-bottom like a document.

**Each finding is a row** with a color-coded left border (tier color), gene name, one-line summary, and an action button. Click the row to expand inline detail. Nothing opens a new page, nothing uses a modal.

**Section order:**
1. Summary header — total findings, tier breakdown, filename
2. **Needs Attention** — critical + high findings (shown by default)
3. **For Your Records** — carrier status + medium + low findings (collapsed by default, expandable)
4. Email capture — "get notified when new research publishes on your variants"
5. Download report button

This keeps the most important things at the top and doesn't overwhelm people with everything at once.

---

## Backend — what you're building against

API base URL: TBD (Hampton deploys to K8s — will share when live)

```
POST /analyze
  Body: multipart/form-data { file: <genome file> }
  Returns 202: { "job_id": "uuid", "poll_url": "/jobs/<id>" }

GET /jobs/<job_id>
  Returns:
  {
    "status":   "pending" | "running" | "done" | "failed",
    "progress": { "step": "Annotating rs80357906 (4/81)", "pct": 47 },
    "count":    12,
    "results":  [...],    // null until done
    "error":    null
  }
```

Poll every 3 seconds. Stop when `status` is `"done"` or `"failed"`.

### Result object — one per variant

Every result in the `results` array has exactly these fields. All JSON-safe, pre-sorted by score descending. Don't re-sort client-side.

```json
{
  "variant_id":              "rs80357906",
  "rsid":                    "rs80357906",
  "location":                "17:43094692",
  "genes":                   ["BRCA1"],
  "zygosity":                "heterozygous",

  "consequence":             "missense_variant",
  "clinvar":                 "pathogenic",
  "clinvar_raw":             "Pathogenic",
  "disease_name":            "Hereditary breast ovarian cancer syndrome",
  "condition_key":           "OMIM:604370",

  "gnomad_af":               0.000023,

  "score":                   1000,
  "tier":                    "critical",
  "carrier_note":            null,
  "frequency_derived_label": null,

  "emoji":                   "🔴",
  "headline":                "Pathogenic variant in BRCA1 — known cancer risk",
  "consequence_plain":       "This change disrupts how the BRCA1 protein is made.",
  "rarity_plain":            "Extremely rare — seen in 0.002% of people.",
  "clinvar_plain":           "ClinVar classifies this as Pathogenic, meaning clinical experts have confirmed it causes disease.",
  "action_hint":             "Discuss this finding with a genetic counselor or oncologist.",
  "zygosity_plain":          "You carry one copy of this variant."
}
```

**Tier → visual treatment:**

| `tier` | Left border color | Emoji | Label |
|--------|------------------|-------|-------|
| critical | red | 🔴 | Needs attention |
| high | orange | 🟠 | High priority |
| medium | yellow | 🟡 | Worth knowing |
| low | green | 🟢 | Low priority |
| carrier (any tier where `carrier_note` is set) | blue | 🔵 | Carrier status |

---

## Screen 1 — Upload

Single centered form. Clean, minimal, not medical-looking.

**Elements:**
- File drop zone — `.vcf`, `.vcf.gz`, `.txt` (23andMe), `.csv`. Max 100 MB. Show filename + size on select.
- Privacy statement (display text, not a checkbox): "Your file is processed in memory and immediately discarded. It is never stored. Only variant coordinates leave this system to look up what each variant means."
- Consent checkbox (required before submit): "I understand this is general genomic information, not medical advice."
- Analyze button — disabled until file + checkbox. On click: `POST /analyze`, navigate to processing screen with `job_id`.

**Inline errors (before submit):**
- File > 100 MB
- Wrong file extension
- Empty file

---

## Screen 2 — Processing

Progress page. Don't let people navigate away.

**Elements:**
- Progress bar — `progress.pct` (0 → 100)
- Step label — `progress.step` (e.g. "Annotating rs80357906 (4/81)")
- Static copy: "Genome analysis usually takes 1–3 minutes."
- Browser `beforeunload` warning: "Analysis in progress. Leaving this page will cancel your results."

If `status == "failed"`: show the `error` message and a retry button that returns to upload.

---

## Screen 3 — Results

This is the product.

### Summary header

```
12 findings in 81 clinically actionable genes
genome.vcf

🔴 2 Critical    🟠 3 High    🟡 4 VUS    🔵 2 Carrier    🟢 1 Low

[Download Report]
```

Persistent disclaimer, small text: "This is not medical advice. Discuss significant findings with a healthcare provider."

---

### Needs Attention section (critical + high)

Shown by default. These are the findings that matter.

**Row — collapsed:**
```
[🔴 CRITICAL]  BRCA1    Pathogenic variant in BRCA1 — known cancer risk    [Talk to a specialist →]
```
Left-border color matches tier. Gene name bold. Headline fills center. Action button right-aligned. Clicking anywhere on the row expands inline.

**Row — expanded (inline below):**
- `consequence_plain`
- `zygosity_plain`
- `rarity_plain`
- `clinvar_plain`
- `action_hint` — most prominent element in the expanded state, styled as a CTA
- Source links (small, below): ClinVar, gnomAD, gene card

**Carrier row variant:**
- Blue left border, 🔵 badge
- Collapsed: "CFTR — You appear to be a carrier for cystic fibrosis"
- Expanded: `carrier_note` text + `action_hint`

**VUS row variant:**
- Yellow left border, 🟡 badge
- Collapsed: "GENE — Variant of uncertain significance"
- Expanded: `consequence_plain`, `rarity_plain`, `frequency_derived_label` if set, plus: "Not enough evidence to classify this variant as harmful or harmless."

---

### For Your Records section (medium + low + carrier)

Collapsed by default. Same row format, lower visual weight. Toggle to reveal.

---

### Zero findings state

```
No findings in the 81 ACMG actionable genes.
This is common — most people don't have known pathogenic variants in these genes.
It does not mean your genome has no variants worth knowing about.
```

Don't leave a blank page.

---

### Email capture

At the bottom of results:

> "Get notified when new research publishes on your variants."
> [email input] [Subscribe]
> "We don't store your genome. We only keep your email."

For MVP: just capture it. No complex backend needed.

---

### Download report

`window.print()` with a print stylesheet. MVP only. Contents: header, tier breakdown, findings table (gene | tier | headline | action), disclaimer.

---

## Insight categories (V2, not MVP)

When Sasank completes the condition library with `category` fields, findings can be grouped into Disease predisposition, Carrier status, Drug response, Traits. Don't build category tabs for MVP. Show everything in one prioritized list. Add tabs in V2.

---

## Component breakdown for Tom

Build in this order:

```
1. /upload
   <UploadZone />         file select + validation + privacy statement
   <ConsentGate />        checkbox
   <AnalyzeButton />      POST /analyze → navigate to /processing/:jobId

2. /processing/:jobId
   <PollingLoop />        GET /jobs/:id every 3s — critical path, build this first
   <ProgressBar />        progress.pct + step text
   <NavigationGuard />    beforeunload warning

3. /results/:jobId
   <SummaryHeader />      count + tier badges + filename + disclaimer
   <FindingsSection />    "Needs Attention" — critical + high rows
   <FindingRow />         collapsed + expanded states
     <TierBadge />        color + emoji + label
     <ActionButton />     action_hint as CTA
     <SourceLinks />      ClinVar / gnomAD / gene card
     <CarrierRow />       blue variant
     <VUSRow />           yellow + uncertainty language
   <RecordsSection />     medium + low + carrier, collapsed default
   <ZeroFindings />       empty state
   <EmailCapture />       subscribe form
   <DownloadReport />     window.print()

4. /shared
   <Disclaimer />         persistent footer
   <ErrorScreen />        failed jobs + network errors
```

Tom: don't wait on Rocky to start. Build `<PollingLoop />` and `<FindingRow />` data layer against the JSON schema above. Rocky's designs slot in on top.

---

## What Rocky designs first (in order)

1. **Single finding row — collapsed + expanded** — this is the core component, get this right first
2. **Needs Attention section** with 2–3 real findings
3. **Upload screen** — drop zone + consent + privacy statement
4. **Summary header + tier badges**
5. **Carrier row + VUS row** — variants of the main row
6. **Processing screen**
7. **Print stylesheet** for report — last

**Design against real content — not Lorem Ipsum:**

Finding 1:
```
tier:        critical
gene:        BRCA1
headline:    Pathogenic variant in BRCA1 — known cancer risk
action:      Discuss this finding with a genetic counselor or oncologist.
consequence: This change disrupts how the BRCA1 protein is made.
rarity:      Extremely rare — seen in 0.002% of people.
clinvar:     ClinVar classifies this as Pathogenic — clinical experts have confirmed it causes disease.
zygosity:    You carry one copy of this variant.
```

Finding 2:
```
tier:        carrier (blue)
gene:        CFTR
headline:    You appear to be a carrier for cystic fibrosis
carrier:     Carrying one copy of this variant typically does not cause the condition,
             but may be relevant for family planning.
action:      Mention this to your doctor if you're planning a family.
```

The design goal: a non-scientist reads one row and understands what it means and what to do. That's the bar.

---

## Tech decisions already made — don't revisit

- No user accounts in V1. Results live at `/results/:jobId` — URL is the session.
- No genome storage. File processed in memory, discarded immediately. Say this on the upload screen.
- VCF is the primary format. 23andMe `.txt` also supported.
- Results pre-sorted by score. Don't sort client-side.
- Category tabs (disease/carrier/drug/traits) are V2.
- Condition library text from Sasank not in API yet. Use `action_hint` as placeholder in expanded rows. No frontend change needed when it's added — comes through the API.

---

## Where to find things

| What | Location |
|------|----------|
| This spec | `docs/frontend.md` — GitHub |
| API endpoints + full result schema | `docs/architecture.md` — GitHub |
| All result fields documented | `engine/__init__.py` lines 28–68 — GitHub |
| Scoring + tier logic | `docs/pipeline.md` — GitHub |
| Clinical language guide | `docs/interpretation.md` — GitHub |
| Roadmap + phase owners | `docs/roadmap.md` — GitHub |
| Notion website page | U4U Notion → Website subpage |
| GitHub repo | https://github.com/Florida-Man-Bioscience/u4u-engine |
