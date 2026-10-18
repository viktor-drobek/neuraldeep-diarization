---
description: Shared helper layering and fail-closed invariants
paths:
  - "scripts/**/*.py"
  - "tests/test_client.py"
  - "tests/test_diarization.py"
---

# Shared helper

`scripts/client.py` is the only code. It is shared by every neuraldeep-* repository and must stay
identical across them except for the `SERVICE = "..."` line. Port a change to each sibling through
its own PR and compare the helpers with the `diff` command in `AGENTS.md`.

## Layered implementation order

After the failing test, implement from lower dependencies upward:

1. Constants, parsing and validation helpers.
2. Credential resolution and approved-origin HTTP transport.
3. Fail-closed guard checks and quota observations.
4. Durable state and artifact handling.
5. Provider job URLs, submission, polling and result validation.
6. `execute()` and CLI wiring.

Lower layers must not depend on CLI parsing or provider job state. Never bypass a lower-layer
failure with a special case in a caller.

## Invariants

- Keep the guard fail-closed: unknown schemas, premium operations, unverified quotas and
  ambiguous submissions block.
- Never add POST retries, follow redirects, or a fallback that resubmits.
- Errors stay sanitized (no keys, no provider response bodies), and every failure still prints
  the JSON envelope.
- Pass `encoding="utf-8"` to every text read and write, in code and tests.

## This service

Diarization (`POST /v1/audio/diarize`) is enabled behind the guard: the quota at `/v1/audio/diarize/quota` reports `used` and `limit` minutes per `day` and `month`, and the helper requires `limit - used` to cover the locally verified `--minutes` in both windows. `resume` refuses the synchronous service, and any unrecognized answer after the POST is `reconciliation_required`, never a retry. `merge` is offline: it validates both inputs, orders them by time and joins the speaker segments with a timed transcript by overlap, writing JSON, WebVTT or SRT, or RTTM from the diarization alone. The POST read timeout grows with `--minutes`, and `run` checks the output path before any request. A `blocked` result is final: never add an opt-in, a direct API call, a fallback, or an undocumented quota probe.
