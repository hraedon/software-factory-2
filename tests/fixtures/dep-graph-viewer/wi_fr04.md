# Interface Specification: FR 04

## Dependencies

- `interface_ref`: `fr03`

## Glossary

- **DOT graph**: A plain-text graph description language consumed by Graphviz. Nodes and edges are declared with attributes for labels, colors, and shapes.
- **event log**: The append-only table of substrate events. Each event describes a state transition, link creation, or custom field update. The primary data source for the viewer.
- **link**: A typed, directed edge between two work items in substrate. Link types include 'depends_on', 'derived_from', 'tested_by', etc.
- **run**: A single execution of the sf2 pipeline identified by a project name and a set of work items. The viewer produces one DOT graph per run.
- **work item**: A unit of work in the substrate workflow engine. Has a type, state, id, and custom fields. Represented as a node in the dependency graph.

## FR-04

Given a filtered graph, the system emits valid DOT syntax to stdout or an optional output file. Nodes include labels (module name) and colors (by state). Edges include labels (link type) and styles (by link type).

## AC-DGV-07

Given a graph with one node in state 'locked' and one 'depends_on' edge, emit_dot produces syntactically valid DOT with a green node and a solid edge

## AC-DGV-08

Given a graph with 100 nodes, emit_dot completes in under 1 second and produces output that graphviz dot -Tpng accepts without error

## AC-DGV-09

Given an empty graph, emit_dot produces a minimal DOT graph declaration with a comment 'No work items found'
