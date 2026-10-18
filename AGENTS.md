# Agent guide for neuraldeep-diarization

Instructions for AI coding agents (Codex, Coddy, Claude Code and others) working **inside this
repository**. To *use* the skill, read [SKILL.md](SKILL.md) and [STARTER_RELAY.md](STARTER_RELAY.md).

## What lives here

- `SKILL.md`: the skill manifest and the `/v1/audio/diarize` reference that the agent loads at
  run time.
- `STARTER_RELAY.md`: the spending guard, private state, and the Relay envelope.
- `scripts/client.py`: the only code, a standard-library CLI with `check`, `run`, `resume` and
  `merge`.
- `tests/`: offline unit tests (`test_client.py` shared with the siblings, `test_diarization.py`
  for this repo) and documentation checks (`test_examples.py`).
- `TESTING.md`: the record of test-first changes and the current test count.

## Diarization and its dependency on transcription

Diarization (`POST /v1/audio/diarize`, Nemotron-3-Diarization) is billed per minute of audio,
rounded up, from its own bucket. `GET /v1/audio/diarize/quota` reports `used` and `limit` minutes
per `day` and `month`, verified read-only on 2026-10-18, so `run diarize` is enabled behind the
guard:

- `check diarize --minutes N` and `run diarize` reach the network; `resume` is refused because the
  call is synchronous; `merge` is offline and needs no key.
- `--minutes` is the locally verified audio length rounded up to whole minutes. The helper never
  guesses or parses it, and refuses more than 240 minutes or a file over 500 MB.
- The model returns speaker segments without text. `merge` joins them by time with a transcript
  from `/v1/audio/transcriptions` (neuraldeep-transcriptions, blocked today) or an existing
  SpeechCore job (SpeechCore uploads are blocked too), and writes JSON, WebVTT or SRT;
  `--format rttm` converts the diarization alone. SKILL.md tells agents to confirm a transcript
  exists before paying for a diarization meant for a speaker transcript.
- The POST waits `max(120, 30 * minutes)` seconds for its answer, and `run` checks the output
  path before any request: a paid answer must not replace its input or be lost.
- Never call the endpoint directly with `curl` or an SDK, add retries, or send `response_format`
  or `min_duration`: the helper validates only the JSON answer.
- Keep SKILL.md, README.md and STARTER_RELAY.md limited to what the helper does and what the
  provider documents. `tests/test_diarization.py` checks the key claims.

## The shared helper

`scripts/client.py` is shared by every neuraldeep-* repo
(speechcore, search, ocr, images, transcriptions, diarization) and must stay identical across them
except for the `SERVICE = "..."` line. Port a change to every sibling repo, each through its own
PR. Check a port against a sibling checkout:

```bash
diff <(grep -v '^SERVICE = ' scripts/client.py) <(grep -v '^SERVICE = ' ../neuraldeep-speechcore/scripts/client.py)
```

It must print nothing. Treat other repos' checkouts as read-only unless you were asked to work
there. A shared test belongs in `tests/test_client.py` and patches `SERVICE` itself, so it runs
unchanged in every repo.

## Tests

Tests are offline: HTTP is mocked and no billed endpoint is called. Run them with credentials
blanked so a real key can never be read:

```bash
env -u NEURALDEEP_API_KEY CODDY_HOME=/nonexistent python3 -B -m unittest discover -s tests
```

Before opening a PR, also run the suite under a non-UTF-8 locale and with encoding warnings on:

```bash
env -u NEURALDEEP_API_KEY CODDY_HOME=/nonexistent LC_ALL=C PYTHONUTF8=0 python3 -B -m unittest discover -s tests
```

```bash
env -u NEURALDEEP_API_KEY CODDY_HOME=/nonexistent python3 -X warn_default_encoding -B -m unittest discover -s tests
```

- Work test-first: add the regression test, watch it fail, then fix. Say so in the commit.
- When a guard has several parts, check by mutation that each part has a test that fails
  without it.
- Update the count in TESTING.md "Final results" and add a short note for each change.
- Pass `encoding="utf-8"` to every text read and write, in code and tests.
- CI (`.github/workflows/tests.yml`) runs the suite and `--help` on Python 3.10 and the latest 3.x.

## Safety rules

- Never send audio to the live API while developing or testing. `check` is read-only, but run it
  only when the user asks.
- Never add, print, or commit credentials, state files, audio, diarizations or transcripts.
- Keep the guard fail-closed: unknown schemas, premium operations, unverified quotas and
  ambiguous submissions must block. Never add POST retries, redirects, or a fallback that resubmits.
- Errors must stay sanitized (no keys, no provider response bodies), and every failure must still
  print the JSON envelope.

## Delivery workflow

Work RED-GREEN-REFACTOR: start a feature with a test that describes the observable result and a
bug fix with a regression test, watch it fail for the intended reason, make the smallest change
that passes, and refactor only with the suite green. Then run the full offline matrix above.

Inside `scripts/client.py`, implement from lower dependencies upward: constants and parsing,
credentials and approved-origin transport, the fail-closed guard, durable state and artifacts,
provider jobs and polling, then `execute()` and the CLI. Lower layers must not depend on CLI
parsing or provider job state.

Update `README.md`, `SKILL.md`, `STARTER_RELAY.md` and `TESTING.md` in the same change when
behavior, CLI output, safety assumptions or documented shapes change.

## Rules Sync

This file is the common policy for every agent, and `CLAUDE.md` is a symlink to it. Scoped detail
lives in native rules with identical bodies:

| Rule | Scope | Cursor | Claude Code |
|---|---|---|---|
| `workflow` | always on | `.cursor/rules/workflow.mdc` | `.claude/rules/workflow.md` |
| `client` | `scripts/**/*.py`, `tests/test_client.py`, `tests/test_diarization.py` | `.cursor/rules/client.mdc` | `.claude/rules/client.md` |
| `documentation` | `README.md`, `SKILL.md`, `STARTER_RELAY.md`, `TESTING.md`, `tests/test_examples.py` | `.cursor/rules/documentation.mdc` | `.claude/rules/documentation.md` |

- Cursor reads `.cursor/rules/`; Claude Code reads `CLAUDE.md` and `.claude/rules/`.
- Codex reads this file, and the project hook in `.codex/hooks.json` with
  `.codex/hooks/attach_rules.py` attaches the Cursor rules: always-on rules at session start,
  scoped rules before an edit to a matching file. Run `/hooks` in Codex once per clone and again
  after changing either hook file. The hook is a fail-open convenience, not a security boundary;
  the safety rules here, the helper and the tests still enforce them.
- Never copy rule bodies under `.codex` or create `.codex/rules.md`.
- Change a rule and its counterpart together. `tests/test_agent_rules.py` checks the pairing, the
  scopes and the hook; it and `.codex/hooks/` are identical across the neuraldeep-* repositories.

## Releases

A release is a `vX.Y.Z` tag on `main` with a GitHub release. `metadata.version` in the `SKILL.md`
frontmatter is the version Coddy shows and uses to decide whether an installed copy is older, so
it must equal the tag without the `v`:

1. In a PR, bump `metadata.version` (semantic versioning) and note the change in `TESTING.md`.
2. After the PR is merged and CI is green, tag the merge commit and publish the release, for
   example `gh release create v1.0.0 --target main --title v1.0.0 --notes-file NOTES.md`.
3. CI runs on the tag push; `tests/test_release.py` fails the build if the tag and
   `metadata.version` differ. It is identical across the neuraldeep-* repositories.

## Git and PRs

- Work on a branch and open a PR; do not push to `main`. Merging is the repository owner's call.
- Do not add AI attribution to commits or PRs: no `Co-Authored-By` trailer for an AI model and no
  "Generated with" line.
- Do not rewrite or force-push shared history without the owner's explicit approval.

## Codex

- Codex reads this file automatically. Its default sandbox blocks network access and writes
  outside the workspace, which is all the offline tests need.
- A live `check` needs the network and reads the key from `~/.coddy`, outside the workspace. Ask
  the user before requesting broader sandbox access; never widen it to send audio.

## Coddy

- Coddy loads this file from the workspace on its own; nothing needs configuring.
- The skill reads the key from `${CODDY_HOME:-~/.coddy}/providers/neuraldeep/neuraldeep-auth.json`
  (field `api_key`), then falls back to `NEURALDEEP_API_KEY`. Sign in with
  `coddy providers login neuraldeep`; never ask the user to paste a key into the chat.
- Run skill commands from the skill directory, and keep state files in a private directory
  outside the checkout.
