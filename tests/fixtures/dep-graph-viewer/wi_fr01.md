# Interface Specification: FR 01

## Dependencies

None.

## Glossary

- **DOT graph**: A plain-text graph description language consumed by Graphviz. Nodes and edges are declared with attributes for labels, colors, and shapes.
- **event log**: The append-only table of substrate events. Each event describes a state transition, link creation, or custom field update. The primary data source for the viewer.
- **link**: A typed, directed edge between two work items in substrate. Link types include 'depends_on', 'derived_from', 'tested_by', etc.
- **run**: A single execution of the sf2 pipeline identified by a project name and a set of work items. The viewer produces one DOT graph per run.
- **work item**: A unit of work in the substrate workflow engine. Has a type, state, id, and custom fields. Represented as a node in the dependency graph.

## FR-01

Given a PostgreSQL DSN and a project name, the system connects to the substrate database and reads the event log for that project. Connection failures produce a structured error.

## AC-DGV-01

Given a valid DSN, read_event_log returns a list of Event objects for the specified project, ordered by event timestamp ascending

## AC-DGV-02

Given a DSN with unreachable host, read_event_log raises ConnectionError with message containing 'could not connect'
