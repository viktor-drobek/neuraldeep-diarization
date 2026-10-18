# Test-first verification

No billed endpoint was called during development or verification: no audio was
diarized or transcribed. Publication is separate from these test results.

## Starting point

The repository started from every tracked file of neuraldeep-transcriptions
`9130021` (v1.0.0) except `.github/`, `tests/test_whisper.py` and the
service documentation, with `SERVICE = "diarize"` in the shared helper. The
copied suite failed with `KeyError: 'diarize'` in the helper tests that read the
repository's own service, before any new test was added.

## Red/green sequence

1. Added 16 shared diarization tests to `tests/test_client.py` and a merge case
   to the shared UTF-8 test. All failed: `diarize` was not a known service, and
   `MAX_DIARIZE_MINUTES`, `merge_transcript` and the `merge` command were missing.
2. Taught the shared helper the `diarize` service, from the lower layers up:
   - constants: operation `diarize`, public price ID `audio:diarize`, quota
     endpoint `/audio/diarize/quota`, `diarize` in `SYNCHRONOUS`, and the
     provider limits of 240 minutes and 500 MB;
   - the guard: more than 240 minutes blocks; the quota must say
     `unit: minute`; `used` and `limit` must be non-negative integers (not
     booleans or floats) in both `day` and `month`; `limit - used` must cover
     `--minutes`;
   - validation: `check_segments()` and `finite()` now serve SpeechCore results,
     diarizations and transcripts; `validate_diarization()` checks `duration`,
     `num_speakers`, `minutes_charged` and timed `speaker` segments;
   - `merge_transcript()` labels each timed transcript segment with the speaker
     it overlaps most (ties go to the first speaker to appear, no overlap gives
     `null`) and joins one speaker's consecutive segments into turns;
   - submission: one multipart `file` part to `/v1/audio/diarize`, with no extra
     fields, refused before any network call for a file over 500 MB;
   - `execute()`: `--minutes` is the quota cost; an unrecognized answer after
     the POST stays `reconciliation_required`; `merge` runs before the key is
     resolved and writes a hashed artifact with the SHA-256 of both inputs;
   - the CLI: `--minutes` and `merge` exist only for diarization, and only
     `merge` takes `--diarization` and `--transcript` (exit 2 otherwise).
   The other services behave as before; their shared tests pass unchanged.
3. Added `tests/test_diarization.py` (10 tests) for this repository: service and
   price ID, `check` reading limits, prices and the quota, the CLI `run` and
   `merge`, and the documentation claims. The five documentation tests failed
   until `SKILL.md`, `README.md`, `STARTER_RELAY.md` and `AGENTS.md` were
   written; the five behavior tests passed against the helper from step 2.
4. Renamed the scoped `client` rule from `tests/test_whisper.py` to
   `tests/test_diarization.py` in both Cursor and Claude Code and rewrote its
   service section; `tests/test_agent_rules.py` passed unchanged.

## Mutations

Each of 19 mutations of the new code failed at least one test: no 4-hour cap,
no `unit` check, ignoring `used`, accepting a negative `used`, accepting a
boolean, no file size check, not checking `minutes_charged`, accepting an
`error` field, skipping response validation, ties going to the last speaker,
assigning a speaker without overlap, keeping empty text, letting `--output` be
an input, not validating the transcript, resolving the key before `merge`,
allowing `--minutes` for other services, accepting `start > end`, a quota cost
other than `--minutes`, and the multipart field name `image`.

## Live read-only evidence (2026-10-18)

With the owner's approval, the shared helper (holding the key, never printing
it) made only read-only GETs:

- `GET /v1/limits`: `tier: starter`, `key.billing_mode: subscription`,
  `key.status: ok`.
- `GET https://neuraldeep.ru/api/public/wallet-prices`: one `audio:diarize` row,
  `billing: unit`, `unit_rub: 0.3`, `premium: false`.
- `GET /v1/audio/diarize/quota` (documented in llms-full.txt): `unit` and `tier`
  strings, and `day` and `month` objects with integer `used` and `limit`. There
  is no `remaining` field. The values are account data and are not recorded.
- `python3 -B scripts/client.py check diarize --minutes 1` with the finished
  helper: `ready`, exit 0, buckets `unit`, `day` and `month`.

No `run diarize` was sent. The response shape the helper validates is the one
the provider documents; it has not been observed live.

## Final results

- `env -u NEURALDEEP_API_KEY CODDY_HOME=/nonexistent python3 -X warn_default_encoding -B -m unittest discover -s tests`:
  **93 tests passed** (1 skipped outside a tag build), 0 EncodingWarnings.
- The same suite under `LC_ALL=C PYTHONUTF8=0`: passed.
- `python3 -B scripts/client.py --help`: passed, with no network call.
- Fenced Python examples parsed with `ast.parse`; Bash examples passed `bash -n`.
