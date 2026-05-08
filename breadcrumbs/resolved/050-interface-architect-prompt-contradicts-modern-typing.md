---
number: "050"
title: "interface_architect.md worked example uses deprecated typing — contradicts implementer rules and lint gate"
severity: medium
status: resolved
kind: bug
author: adversarial-review
date: "2026-05-08"
tags: [prompts, stage-2, stage-4, gate]
related: ["039"]
---

## Problem

`interface_architect.md:77` in the worked example:

```python
from typing import Union
...
Result = Union[Range, Error]
```

The implementer prompt (`implementer.md:33-36`) now explicitly forbids this:

> - Use `X | Y` for unions, `X | None` for optionals. Never use `typing.Union`, `typing.Optional`.

The ruff lint gate rejects `Union`/`Optional` usage. The interface_architect prompt teaches models to emit contracts in a style that the lint gate will reject when the implementer tries to fill them in. If the model copies the worked example's pattern, the interface will pass the interface_spec gate (no ruff gate on .pyi files) but the downstream implementation will fail impl_lint.

The interface_architect prompt should model the correct patterns for the full pipeline, not just its own stage boundaries.

## Fix

Update the worked example in `interface_architect.md` to use `Range | Error` instead of `Union[Range, Error]`. Audit for any other deprecated typing patterns in the example.
