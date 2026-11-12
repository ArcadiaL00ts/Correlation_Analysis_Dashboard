---
name: nasdaq-correlation-troubleshooting
description: Troubleshoot failures in the NASDAQ-100 top-50 correlation dashboard. Use when Codex needs to diagnose universe-resolution failures, fallback ranking problems, provider outages, artifact-generation gaps, broken dashboard loads, or missing metadata and then update codex.md with the durable fix.
---

# NASDAQ Correlation Troubleshooting

Follow this workflow:

1. Read `codex.md` before debugging so persistent guardrails and prior failures are visible.
2. Confirm whether the failure is in universe resolution, ranking fallback, price ingestion, analytics/export generation, or dashboard rendering.
3. Check metadata first to see whether the issue is already captured as a fallback or partial failure.
4. If the official Nasdaq source fails, verify whether the issue is network-related, schema-related, or a stale endpoint.
5. If QQQM holdings fail, confirm whether the download redirected, changed format, or removed ranking columns.
6. If Yahoo Finance fallback fails, capture whether the issue is provider schema drift, auth behavior, or environment dependency.
7. If imports fail before runtime, check for missing packages and broken package state such as a malformed `pyarrow` module that prevents `pandas` from importing.
8. Do not close the issue as fixed unless the missing artifact or broken view is actually restored.
9. Append a dated note to `codex.md` describing the failure mode and the durable guardrail or fix.
