from __future__ import annotations

import re
from dataclasses import dataclass

from factory.failure_summary import FailureEntry


@dataclass(frozen=True)
class FailureSummary:
    constraints: list[str]
    raw_text: str

    def format_for_prompt(self) -> str:
        return "\n".join(f"- {c}" for c in self.constraints)


def summarize_failures(
    failures: list[FailureEntry],
    max_entries: int = 10,
) -> FailureSummary | None:
    if len(failures) < 2:
        return None

    recent = failures[-max_entries:]
    lines: list[str] = []
    for f in recent:
        parts = [
            f"[attempt {f.attempt_number}]",
            f"role={f.role}",
            f"gate={f.gate_name}",
        ]
        if f.diagnostic:
            diag = f.diagnostic
            if len(diag) > 300:
                diag = diag[:297] + "..."
            parts.append(diag)
        if f.error_message:
            err = f.error_message
            if len(err) > 200:
                err = err[:197] + "..."
            parts.append(err)
        lines.append(" ".join(parts))

    raw_text = "\n".join(lines)
    constraints = _extract_constraints_locally(raw_text)

    return FailureSummary(constraints=constraints, raw_text=raw_text)


def _extract_constraints_locally(failure_text: str) -> list[str]:
    constraints: list[str] = []
    diag_lines = failure_text.split("\n")

    import_refs = set()
    type_mismatches = set()
    missing_symbols = set()
    repeated_errors: dict[str, int] = {}

    for line in diag_lines:
        import_match = re.search(
            r"import\s+(\w+[\w.]*)|from\s+([\w.]+)\s+import",
            line,
        )
        if import_match:
            mod = import_match.group(1) or import_match.group(2)
            if mod and "attempt" not in mod.lower():
                import_refs.add(mod)

        type_match = re.search(
            r"(?:incompatible|cannot assign|Argument\s+\d|return value).*?"
            r"(?:`(\w+)`|\"(\w+)\"|'(\w+)')",
            line,
        )
        if type_match:
            sym = type_match.group(1) or type_match.group(2) or type_match.group(3)
            if sym:
                type_mismatches.add(sym)

        missing_match = re.search(
            r"(?:NameError|AttributeError|has no attribute"
            r"|not defined)[:\s]+(.{3,60})",
            line,
        )
        if missing_match:
            symbol = missing_match.group(1).strip().strip("'\"`")
            if symbol:
                missing_symbols.add(symbol)

    for line in diag_lines:
        core = re.sub(r"\[attempt \d+\]", "", line).strip()
        core = re.sub(r"role=\w+", "", core).strip()
        core = re.sub(r"gate=\w+", "", core).strip()
        if len(core) > 20:
            repeated_errors[core] = repeated_errors.get(core, 0) + 1

    recurring = {k: v for k, v in repeated_errors.items() if v >= 2}

    if import_refs:
        sorted_imports = sorted(import_refs)[:5]
        constraints.append(
            f"Import references seen: {', '.join(sorted_imports)}. "
            "Verify module names match locked dependency names."
        )

    if type_mismatches:
        sorted_types = sorted(type_mismatches)[:5]
        constraints.append(
            f"Type mismatches on: {', '.join(sorted_types)}. "
            "Check return/param types match the .pyi contract."
        )

    if missing_symbols:
        sorted_missing = sorted(missing_symbols)[:5]
        constraints.append(
            f"Missing symbols: {', '.join(sorted_missing)}. "
            "Ensure all referenced names are defined or imported."
        )

    for core, count in sorted(recurring.items(), key=lambda x: -x[1])[:3]:
        shortened = core[:80] + ("..." if len(core) > 80 else "")
        constraints.append(f"Recurring error ({count}x): {shortened}")

    if not constraints:
        constraints.append(
            f"Multiple failures across {len(diag_lines)} attempts. "
            "Review all gate diagnostics carefully before fix."
        )

    return constraints[:5]
