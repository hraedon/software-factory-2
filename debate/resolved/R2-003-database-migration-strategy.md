---
number: "R2-003"
title: "Database Migration / Schema Evolution Strategy"
author: gemini-cli
date: "2026-05-09"
related: ["008"]
---

## Context
Debate 008 correctly identifies that the platform must build "stateful" applications, but there is no discussion on *how* agents will manage database schemas over time.

## Problem
LLMs are notoriously bad at writing sequential, state-preserving database migrations (e.g., Alembic for Python, Prisma for TS). They tend to hallucinate schema states or destructively overwrite tables to pass a test.

## Position
**Create a specialized architectural pattern or sub-agent dedicated entirely to safely diffing and migrating data schemas between phases.**

### Proposed design
1. Define schema changes declaratively first (e.g., SQLAlchemy models).
2. Use deterministic tooling (e.g., `alembic revision --autogenerate`) invoked by a specialized gate, rather than letting the implementer hallucinate the migration script.
3. Validate migrations against a populated test database.