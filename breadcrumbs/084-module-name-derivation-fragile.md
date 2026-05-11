---
number: "084"
title: "_extract_module_name_from_spec derives module names from model-generated spec titles — fragile regex produces mangled names"
severity: high
status: proposed
kind: bug
author: opencode-glm-5.1
date: "2026-05-11"
tags: [dep_resolution, gate, runner, cert-watch, stage-5]
related: ["077", "076", "074"]
---

## Problem

`_extract_module_name_from_spec()` in `dep_resolution.py:25-34` derives module names from the `# Interface Specification:` title line in the spec section. The model freely chooses these titles, and the regex `re.sub(r"[^a-zA-Z0-9_]", "_", title)` produces mangled names when the title contains parenthetical suffixes, hyphens, or other non-alphanumeric characters.

Examples from GR-013:

| Fixture name | Model-chosen title | Derived module name |
|---|---|---|
| certificate_model | Certificate Model (cert-parser) | certificate_model__cert_parser_ |
| cert_chain_library | Certificate Chain Library | certificate_chain_library |
| fr01_dashboard | FR-01 Dashboard | fr_01_dashboard |
| fr02_tls_scan | FR-02 TLS Scanning | fr_02_tls_scanning |

Only `database_layer` ("Database Layer") matched by coincidence.

## Impact

The gate copies dependency `.py` files under the mangled name (e.g., `certificate_model__cert_parser_.py`), but test code imports `from certificate_model import Certificate`. This causes `ImportError` at pytest collection, escalating test_suites to `cannot_proceed`.

In GR-013, this caused 5/8 test_suites to escalate on `test_suite_collect` — all 5 had interfaces that imported from dependency modules with mangled names. The 3 that passed either had no deps or their interfaces didn't import from deps.

## Proposed fix

The canonical module name should come from a source the pipeline controls, not from model-generated content. Options:

**Option A: Use the fixture label.** `populate_work_items.py` strips the `wi_` prefix from filenames (e.g., `wi_certificate_model.md` → `certificate_model`). Store this as a `module_name` custom_field during populate. `_extract_module_name_from_spec` becomes a fallback only.

**Option B: Use the work item label from custom_fields.** The populate script already sets `label` on work items (though currently `None` for GR-013 — this needs fixing). If label is populated, derive the module name from it.

**Option C: Use the artifact path stem.** The locked interface_spec artifact is `artifact.pyi`. Not useful directly, but the work item directory name could encode the module name.

Option A is the cleanest — the fixture filename is the single source of truth for the module name, and populate is the only place that sets it. The dep resolution code reads `custom_fields["module_name"]` instead of parsing the spec title.
