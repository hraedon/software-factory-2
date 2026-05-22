---
number: "203"
title: "gemini_channel.py hardcodes Node v24.15.0 path — not in FactoryConfig"
severity: medium
status: proposed
kind: improvement
author: self-audit
date: "2026-05-22"
tags: [runner]
related: []
---

## Problem

`gemini_channel.py:14` hardcodes `_NVM_NODE_BIN = Path.home() / ".nvm" / "versions" / "node" / "v24.15.0" / "bin"`. Per AGENTS.md convention, all defaults should live in `FactoryConfig`. This path is machine-specific and will break when Node is upgraded or on machines without NVM.

## Fix

Add `gemini_node_bin` to `FactoryConfig` with the current path as default. Read from config in `GeminiCLIChannel._extra_env()`.
