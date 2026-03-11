# Contributing

## The one rule

The engine has zero web framework dependencies. It takes bytes, returns a list of dicts. Keep it that way. If a PR adds FastAPI, Flask, Django, or any server machinery to `engine/`, it will be closed.

---

## Setup

```bash
git clone https://github.com/curtisdearing/u4u-engine.git
cd u4u-engine
pip install -e "./engine[vcf]"          # include pysam for VCF support
pip install pytest responses             # test deps
```

---

## Running tests

```bash
pytest tests/ -v
```

All tests must pass before opening a PR. If you're adding behavior, add a test for it.

---

## How the codebase is organized

```
engine/            The package. This is what gets pip-installed.
engine/pipeline.py The orchestrator. 10 steps in sequence.
engine/annotators/ One file per external data source.
engine/scoring.py  Scoring and tier assignment.
engine/summary.py  Plain-English text generation.
tests/             Mirrors engine/ structure.
docs/              Specs. Read them before changing behavior.
data/              rsID filter files (not committed — generate locally).
```

The specs in `docs/` describe intended behavior. If code and spec disagree, fix whichever is wrong — but write it down.

---

## What's in scope

- Bug fixes in the pipeline, annotators, or scoring
- New annotator fallback paths
- Parser improvements for edge-case genome file formats
- Test coverage for untested branches
- Doc corrections

## What's not in scope (right now)

- Web server, API layer, auth — that's Hampton's domain, separate repo
- Frontend — separate repo
- PRS (polygenic risk scores)
- New gene panel data files — coordinate with Curtis first

---

## Opening a PR

Use the PR template. One change per PR. If you're fixing a bug, link the issue. If you're adding a feature that isn't in `docs/`, update the relevant doc file in the same PR.

The PR description should answer: what changed, and why. "Fixed bug" is not sufficient. "Fixed ClinVar returning `None` when `germline_classification` schema is used instead of `clinical_significance`" is.
