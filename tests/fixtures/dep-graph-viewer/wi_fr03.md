# Interface Specification: FR 03

## Dependencies

- `interface_ref`: `fr02`

## Glossary

- **DOT graph**: A plain-text graph description language consumed by Graphviz. Nodes and edges are declared with attributes for labels, colors, and shapes.
- **event log**: The append-only table of regista events. Each event describes a state transition, link creation, or custom field update. The primary data source for the viewer.
- **link**: A typed, directed edge between two work items in regista. Link types include 'depends_on', 'derived_from', 'tested_by', etc.
- **run**: A single execution of the sf2 pipeline identified by a project name and a set of work items. The viewer produces one DOT graph per run.
- **work item**: A unit of work in the regista workflow engine. Has a type, state, id, and custom fields. Represented as a node in the dependency graph.

## FR-03

Given a reconstructed graph, the system filters nodes by work-item type (e.g., 'interface_spec', 'implementation') and edges by link type (e.g., 'depends_on', 'derived_from'). Unfiltered graph is the default.

## AC-DGV-05

Given --filter-type implementation, filter_graph returns only nodes of type 'implementation' and edges between them

## AC-DGV-06

Given --filter-type interface_spec,review, nodes of both types are included; all other types are excluded
