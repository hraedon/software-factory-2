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

## AC-DGV-01

Given a valid DSN, read_event_log returns a list of Event objects for the specified project, ordered by event timestamp ascending

## AC-DGV-02

Given a DSN with unreachable host, read_event_log raises ConnectionError with message containing 'could not connect'

## AC-DGV-03

Given a list of events including work-item creation and link creation, build_graph returns a Graph with correct nodes and directed edges

## AC-DGV-04

Given a node with custom_fields containing module_name='foo', the graph node's label is 'foo', not its UUID

## AC-DGV-05

Given --filter-type implementation, filter_graph returns only nodes of type 'implementation' and edges between them

## AC-DGV-06

Given --filter-type interface_spec,review, nodes of both types are included; all other types are excluded

## AC-DGV-07

Given a graph with one node in state 'locked' and one 'depends_on' edge, emit_dot produces syntactically valid DOT with a green node and a solid edge

## AC-DGV-08

Given a graph with 100 nodes, emit_dot completes in under 1 second and produces output that graphviz dot -Tpng accepts without error

## AC-DGV-09

Given an empty graph, emit_dot produces a minimal DOT graph declaration with a comment 'No work items found'

## Business Rules

1. Isolated nodes (no edges) are included.
2. All edges are directed (`->`).
3. Node colors: locked=green, in_progress=yellow, new=gray, cannot_proceed=red.
4. Edge styles: depends_on=solid, derived_from=dashed, tested_by=dotted.
5. Project not found exits with code 2.
