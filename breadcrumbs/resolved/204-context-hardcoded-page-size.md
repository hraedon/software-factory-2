---
number: "204"
title: "context.py hardcodes page_size=200 with no pagination"
severity: low
status: proposed
kind: improvement
author: self-audit
date: "2026-05-22"
tags: [runner]
related: []
---

## Problem

`context.py:487,505` hardcode `page_size=200` when querying locked implementations and interface specs. For projects with more than 200 items, silently misses the rest. Should use `config.query_page_size` and paginate.

## Fix

Use the configurable page size from `FactoryConfig`. Add cursor-based pagination if project sizes grow beyond a single page.
