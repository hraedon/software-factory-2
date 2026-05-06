# Golden Run 001

Placeholder for the first real Claude CC execution.

To populate:
1. Run `factory-run` against a substrate instance with the primary test set
   work-items created.
2. Record each work-item's manifest.json + artifact.pyi + substrate event
   dump into this directory.
3. The `test_golden_run.py` test will validate that MockChannel + MockSubstrate
   replay reproduces the same transitions.

Structure once populated:
```
golden-run-001/
  wi-<id>/
    artifact.pyi
    manifest.json
    events.jsonl
  metadata.json
```