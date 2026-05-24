# Interface Specification: FR 02

## Dependencies

None.

## Glossary

- **DOT graph**: A plain-text graph description language consumed by Graphviz. Nodes and edges are declared with attributes for labels, colors, and shapes.
- **event log**: The append-only table of substrate events. Each event describes a state transition, link creation, or custom field update. The primary data source for the viewer.
- **link**: A typed, directed edge between two work items in substrate. Link types include 'depends_on', 'derived_from', 'tested_by', etc.
- **run**: A single execution of the sf2 pipeline identified by a project name and a set of work items. The viewer produces one DOT graph per run.
- **work item**: A unit of work in the substrate workflow engine. Has a type, state, id, and custom fields. Represented as a node in the dependency graph.

## FR-02

Given an event log stream, the system reconstructs all work items (nodes) and their typed links (edges) for the project. Nodes are identified by work-item id and labeled by module name from custom fields.

## AC-DGV-03

Given a list of events including work-item creation and link creation, build_graph returns a Graph with correct nodes and directed edges

## AC-DGV-04

Given a node with custom_fields containing module_name='foo', the graph node's label is 'foo', not its UUID
