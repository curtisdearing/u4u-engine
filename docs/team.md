# U4U — Team and Ownership

> **Status:** Active. Update this when roles or assignments change.

---

## The rule

One repo. One `docs/` folder. All decisions live in these markdown files. If it's not written here, it hasn't been decided.

When you build something, you build it against the spec documents in this folder. If the spec is wrong, you fix the spec — you do not silently deviate from it.

---

## Team

| Person | Role | Owns |
|--------|------|------|
| **Curtis** | Product Lead / Engine | Engine (`engine/`), all docs in `docs/`, repo structure, condition library integration |
| **Sasank** | Scientific Advisor | `docs/interpretation-spec.md`, condition library spreadsheet (OMIM IDs, plain descriptions, action guidance) |
| **Hampton** | Backend / Infra / DevOps | API server, Celery workers, Docker, CI/CD, database, auth (Authelia), security hardening |
| **Tom** | Frontend Dev | React app — upload page, processing page, results page |
| **Rocky** | Frontend Design | Results card mockup, visual design system |
| **Jeran** | Marketing / Growth | Community outreach, early users, brand, Google Workspace |
| **Cane** | Security / Compliance | Pre-launch security audit, Nmap scan, privacy policy, consent gate |

---

## What each person reads first

| Person | Read this |
|--------|-----------|
| Curtis | Everything — you wrote it |
| Sasank | `docs/narrative.md`, `docs/interpretation-spec.md` — then write your sections |
| Hampton | `docs/engine-spec.md` (API section), `docs/data-sources.md`, engine `README.md` |
| Tom | `docs/product-spec.md` — every screen, every state |
| Rocky | `docs/product-spec.md` (results card sections), `docs/interpretation-spec.md` (tiers and VUS section) |
| Jeran | `docs/narrative.md` |
| Cane | `docs/data-sources.md` (what user data leaves the system), `docs/product-spec.md` (consent checkbox) |

---

## Critical path

This is the sequence nothing can skip. Everything else runs in parallel.

```
Sasank writes condition library (ACMG81 genes)
    ↓
Rocky designs results card (needs condition content to design against)
    ↓
Tom implements results page (needs Rocky's design)
    ↓
Soft launch to first users
```

Hampton's infra work, Jeran's outreach, and Cane's security audit all run in parallel and do not block this chain.

---

## How to contribute to the repo

**If you are Sasank:**
- Pull the repo
- Navigate to `docs/`
- Edit `interpretation-spec.md` — find sections marked `[SASANK REVIEW]` and fill them in
- Create and populate the condition library spreadsheet (schema in `docs/interpretation-spec.md`)
- Do not touch any `.py` files unless you have discussed it with Curtis first

**If you are Tom:**
- Build against `docs/product-spec.md`
- The API response shape is documented in `docs/engine-spec.md` (Output section)
- Use mock data that matches the field names exactly — the real API will return the same shape
- If the spec is ambiguous, ask Curtis to clarify the spec before building

**If you are Hampton:**
- The engine is imported as `from engine import run_pipeline`
- Workers call `run_pipeline(file_bytes, filename, filters=[...])` and get back `list[dict]`
- The engine README has FastAPI and Celery wrapping examples
- `NCBI_API_KEY` env var raises ClinVar rate limit — set it in production

**If you are Rocky:**
- Design the results card against `docs/product-spec.md`
- The five tier states are: 🔴 Critical, 🟠 High, 🟡 Medium/VUS, 🟢 Low, 🔵 Carrier
- VUS cards and Carrier cards have distinct layouts — see product-spec for specifics
- Sasank's condition library text is what goes in the "plain description" section — design around that length

---

## Open decisions (needs resolution)

| Decision | Status | Owner |
|----------|--------|-------|
| Beyond ACMG SF scope for V1 — what genes? | ❌ Unresolved | Sasank |
| VUS exact display language | ❌ Draft in interpretation-spec | Sasank |
| Carrier language for specific genes (CFTR, HBB, etc.) | ❌ Unresolved | Sasank |
| Nucleate demo exact date | ❌ Unresolved | Curtis |
| Subscription pricing | ❌ Not now | Curtis |
| Public brand name | ❌ Not now | Jeran |
| Pharmacogenomics in V1? | ❌ Not in scope — confirm | Curtis + Sasank |

---

## Not in scope for V1

- User accounts / saved results
- Email delivery of reports
- PRS (polygenic risk scores)
- Multi-omic data
- Clinician-facing features
- Mobile app
- API access for third-party developers
- Pharmacogenomics (infrastructure exists; content not ready)
- Direct-to-consumer sequencing

---

*Anyone can edit this file. Keep it accurate.*
