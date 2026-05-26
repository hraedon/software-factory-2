---
number: "214"
title: "__import__('re') in subprocess_channel.py — code smell"
severity: low
status: implemented
kind: bug
author: adversarial-review
date: "2026-05-25"
tags: [code-smell, subprocess]
related: []
---

## Problem

`subprocess_channel.py:31` used `__import__("re").compile(...)` instead of a normal `import re` at the top of the file. This was a code smell — likely added hastily to avoid a top-level import for a single-use regex.

## Fix (Session 53)

Added `import re` to the top-level imports and replaced the `__import__` call with `re.compile(...)`.
