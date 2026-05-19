from __future__ import annotations

import ast


def structural_signature(pyi_content: str) -> list[str]:
    """Extract normalized structural elements from .pyi content for comparison.

    Returns a sorted list of canonical strings capturing:
    - function names, parameter types, and return types
    - class names
    - enum member names and values
    - type aliases (module-level assignments with annotations)
    - AC references from docstrings

    Whitespace, import ordering, and prose docstring content are excluded.
    """
    tree = ast.parse(pyi_content)
    elements: set[str] = set()

    def _type_str(node: ast.expr | None) -> str:
        if node is None:
            return ""
        return ast.unparse(node)

    def _extract_ac_refs(node) -> list[str]:
        doc = ast.get_docstring(node, clean=False)
        if not doc:
            return []
        refs: list[str] = []
        for word in doc.replace(",", " ").split():
            if word.startswith("AC-") or word.startswith("TS-"):
                refs.append(word.rstrip("."))
        return refs

    def _visit_module_level(stmts: list[ast.stmt]):
        for node in stmts:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                _collect_function(node)
            elif isinstance(node, ast.ClassDef):
                _collect_class(node)
            elif isinstance(node, ast.AnnAssign):
                target = node.target
                if isinstance(target, ast.Name):
                    elements.add(f"type_alias:{target.id}={_type_str(node.annotation)}")
            elif isinstance(node, ast.Assign) and len(node.targets) == 1:
                target = node.targets[0]
                if isinstance(target, ast.Name) and isinstance(node.value, ast.Subscript):
                    elements.add(f"type_alias:{target.id}={ast.unparse(node.value)}")

    def _collect_function(node: ast.FunctionDef | ast.AsyncFunctionDef):
        params = []
        for arg in node.args.args + node.args.posonlyargs:
            params.append(f"{arg.arg}:{_type_str(arg.annotation)}")
        if node.args.vararg:
            params.append(f"*{node.args.vararg.arg}:{_type_str(node.args.vararg.annotation)}")
        if node.args.kwonlyargs:
            for kwa in node.args.kwonlyargs:
                params.append(f"{kwa.arg}:{_type_str(kwa.annotation)}")
        if node.args.kwarg:
            params.append(f"**{node.args.kwarg.arg}:{_type_str(node.args.kwarg.annotation)}")
        ret = _type_str(node.returns)
        elements.add(f"fn:{node.name}({', '.join(params)}) -> {ret}")
        for ref in _extract_ac_refs(node):
            elements.add(f"ac_ref:{node.name}:{ref}")

    def _collect_class(node: ast.ClassDef):
        elements.add(f"class:{node.name}")
        for ref in _extract_ac_refs(node):
            elements.add(f"ac_ref:{node.name}:{ref}")
        for body_node in node.body:
            if isinstance(body_node, ast.Assign):
                for target in body_node.targets:
                    if isinstance(target, ast.Name):
                        val = ast.unparse(body_node.value) if body_node.value else ""
                        elements.add(f"enum_member:{node.name}.{target.id}={val}")

    _visit_module_level(tree.body)
    return sorted(elements)


def extract_exports(pyi_content: str) -> set[str]:
    """Extract top-level public names from .pyi content.

    Returns a flat set of exported names (classes, functions, type aliases).
    Enum members collapse to their parent class name.
    """
    tree = ast.parse(pyi_content)
    names: set[str] = set()

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
        elif isinstance(node, ast.ClassDef):
            names.add(node.name)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                names.add(node.target.id)
        elif isinstance(node, ast.Assign) and len(node.targets) == 1:
            if isinstance(node.targets[0], ast.Name):
                names.add(node.targets[0].id)
    return names


def structurally_equivalent_pyi(a: str, b: str) -> bool:
    """Return True if two .pyi contents are structurally equivalent.

    Compares function signatures, class names, enum members, type aliases, and AC
    references. Ignores formatting, whitespace, import ordering, and docstring prose.
    """
    try:
        sig_a = structural_signature(a)
        sig_b = structural_signature(b)
        return sig_a == sig_b
    except SyntaxError:
        return False
