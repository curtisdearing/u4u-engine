# Contributing

The engine is a pure Python function — bytes in, list of dicts out. No servers, no databases, no web frameworks inside `engine/`. PRs that add them will be closed.

## Setup

```bash
pip install -e "./engine[vcf]"
pip install pytest responses
```

## Tests

```bash
pytest tests/ -v
```

All need to pass. If you're adding behavior, test it.

## Opening a PR

One change per PR. The description should explain what changed and why — not list every file you touched. If you're changing behavior that the specs describe, update the spec in the same PR.

`docs/` is the source of truth for intended behavior. If code and spec disagree, fix whichever is wrong and write it down.
