# Dependency Graph Viewer — Specification

## Overview

A CLI tool that reads a regista event log for a given project, builds a dependency graph of work items, and emits a DOT file for Graphviz rendering.

## Functional Requirements

### FR-01: Event Log Reader
Given a PostgreSQL DSN and project name, connect and read the event log. Failures produce structured errors.

### FR-02: Graph Builder
Reconstruct work items (nodes) and typed links (edges) from the event log. Nodes are labeled by module name.

### FR-03: Graph Filter
Filter nodes by work-item type and edges by link type. Default is unfiltered.

### FR-04: DOT Emitter
Emit valid DOT syntax to stdout or a file. Nodes are colored by state, edges styled by link type.

## Data Types

- `Node`: `{id, label, type, state}`
- `Edge`: `{source, target, type, style}`
- `Graph`: `{nodes: list[Node], edges: list[Edge]}`

## Acceptance Criteria

- **AC-DGV-01** [FR-01]: Valid DSN returns events ordered by timestamp.
- **AC-DGV-02** [FR-01]: Unreachable host raises `ConnectionError`.
- **AC-DGV-03** [FR-02]: Correct nodes and directed edges from events.
- **AC-DGV-04** [FR-02]: `module_name` in custom_fields becomes node label.
- **AC-DGV-05** [FR-03]: `--filter-type implementation` shows only implementation nodes.
- **AC-DGV-06** [FR-03]: Multiple `--filter-type` values are OR'd.
- **AC-DGV-07** [FR-04]: Locked state node is green; depends_on edge is solid.
- **AC-DGV-08** [FR-04]: 100-node graph renders in <1s and passes `dot -Tpng`.
- **AC-DGV-09** [FR-04]: Empty graph produces minimal DOT with "No work items found" comment.

## Business Rules

1. Isolated nodes (no edges) are included.
2. All edges are directed (`->`).
3. Node colors: locked=green, in_progress=yellow, new=gray, cannot_proceed=red.
4. Edge styles: depends_on=solid, derived_from=dashed, tested_by=dotted.
5. Project not found exits with code 2.
