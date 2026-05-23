#!/usr/bin/env python3
"""Phase-agnostic pipeline report.

Formerly report.py — hardcoded Phase-1 categories and workflow_version=1.
Now delegates to ``review_surface.generate_review_report()``, which is
workflow-version-agnostic and produces REVIEW.md + review.json for any
completed or in-progress pipeline.

Usage::

    python report.py --config .factory/golden-runs/gr-NNN-config.yaml
"""
from __future__ import annotations

import argparse
import warnings

from factory.config import FactoryConfig, load_config
from factory.review_surface import generate_review_report, render_review_markdown


def main():
    warnings.warn(
        "report.py is superseded by `factory review_surface` / `telemetry`. "
        "This CLI is preserved for backward compatibility.",
        DeprecationWarning,
        stacklevel=2,
    )

    parser = argparse.ArgumentParser(description="Software Factory v2 — Pipeline report")
    parser.add_argument("--config", type=str, required=True, help="Path to FactoryConfig YAML")
    args = parser.parse_args()

    config = load_config(args.config)
    report = generate_review_report(config)
    md = render_review_markdown(report)

    # Print the same report that review_surface.write_review_report would produce
    print(md)


if __name__ == "__main__":
    main()
