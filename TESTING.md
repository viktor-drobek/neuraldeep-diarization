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

## Subtitle and RTTM formats

`merge --format json|vtt|srt|rttm` (default `json`). Seven shared tests were
added first; six failed because `to_webvtt`, `to_srt` and `to_rttm` did not
exist. The seventh, on the flag rules, passed because argparse refused the
unknown flag, and now guards the rules themselves. The merge case of the UTF-8
test now also writes WebVTT. WebVTT uses voice tags and escapes `&`, `<` and
`>`; SRT prefixes the speaker; RTTM is converted locally from the validated
diarization JSON, with no transcript and no `response_format` sent to the
provider. The envelope's artifact provenance carries the input hashes.

## Cross-review fixes

A cross-review by three reviewers (claude opus, coddy gpt-6.1-sol, coddy
gemma-4-31b), with every finding verified offline, led to eight changes. One
test each was added first; seven failed, and the 500 MB cap test passed because
it only adds missing coverage:

1. The diarization POST waited only the 30 s default for an answer that may
   take longer on a long file, and a timeout strands charged minutes as
   `reconciliation_required`. It now waits `diarize_timeout(minutes)` =
   `max(120, 30 * minutes)` seconds, recorded in `timeouts.request_seconds`.
2. `run` sent the billed request before checking `--output`: an output equal to
   `--file` replaced the audio with the answer, and a missing directory lost a
   paid answer. Every service's `run` now blocks both before any request.
3. Speaker labels were not flattened in WebVTT and SRT, so a label with line
   breaks could inject a cue; empty labels gave `<v >`. Labels are flattened
   and an empty one counts as no speaker.
4. The 1 ms minimum cue length was applied before rounding to milliseconds and
   could still give a zero-length cue; it is now applied after.
5. `finite()` raised `OverflowError` on integers too large for a float; it now
   returns false, so such input blocks or needs reconciliation.
6. `merge` followed file order: an unsorted transcript built turns out of order,
   and ties went to the first speaker listed, not the first to speak. Both
   inputs are now sorted by `(start, end)`.
7. Float error broke ties between equal overlaps; overlaps are rounded to the
   microsecond before comparing.
8. The 500 MB cap had no test of its value or of its inclusive boundary.

Each of 11 mutations of these fixes fails a test. Not changed, with reasons in
the review: zero-length transcript segments stay unassigned; `minutes_charged`
is not compared with `--minutes`; the upload is built in memory, as for OCR.

## Second cross-review

A second round by the same three reviewers, on the fixed change and without the
first round's answers, led to six more changes. Each test was written first and
failed, except the read-only and missing directory cases, which already passed:

1. An `--output` that is an existing directory (also `.`) passed the output
   check, so the billed answer was lost after the POST; and a symlink in a
   read-only directory passed because the check used the resolved parent while
   `atomic_write()` writes in the unresolved one. Both now block before any
   request, with the read-only, directory, `.` and symlink cases tested.
2. WebVTT and SRT wrote one cue per speaker turn, so a pause inside a turn put
   text on screen before it was spoken. `label_segments()` now keeps each
   transcript segment, subtitles get one cue per segment at its own time, and
   `merge_transcript()` builds the JSON turns from the same labels.
3. A finite but huge timestamp crashed the subtitle writers with
   `OverflowError`, and deeply nested input JSON crashed `merge` with
   `RecursionError`. Both now end `blocked` with the JSON envelope.
4. Bad input JSON got the generic credentials message, and a UTF-8 byte order
   mark was refused. `merge` now parses bytes and names the bad file.
5. The output check had no test for a read-only directory; it has now, as in 1.
6. `.gitignore` missed the example outputs `speakers.vtt`, `speakers.srt` and
   `diarization.rttm`; a documentation test now checks every example path.

A reviewer's request to drop "speakers are numbered in order of first
appearance" was rejected: the provider documents it, as it does the note that
the first seconds of a turn are sometimes left without a speaker. Each of 7
mutations of these fixes fails a test.

## Third cross-review

A third round, again without the earlier answers, found no way to lose billed
minutes in normal use and led to seven smaller changes. Each test was written
first and failed, except the `--output` equal to `--diarization` case, which
only adds coverage:

1. The docs offered SpeechCore as a transcript source without saying its uploads
   are blocked too, so an agent could pay for a diarization and only then find
   no transcript. SKILL.md now says so, and its workflow starts by confirming a
   timed transcript exists; AGENTS.md and README agree. A documentation test
   checks it.
2. The output directory check tested only write permission; `mkstemp` also
   needs search permission and the directory fsync read permission. It now
   requires all three, with `0o600` and `0o300` directories tested.
3. `merge` accepted UTF-16 and UTF-32 and surrogate bytes, because
   `json.loads(bytes)` detects encodings. It now decodes strict `utf-8-sig`.
4. A missing input, an unwritable output and a lone surrogate escape fell back
   to the advice for billed jobs. Each now blocks with its own message.
5. The run example cost 3 minutes while the answer below it charged 2; the
   example is now the provider's 61 s file at `--minutes 2`.
6. The RTTM file ID is the diarization file name without its extension; the
   docs said "file name".
7. `--output` equal to `--diarization` is now tested for JSON and RTTM.

Each of 8 mutations of these fixes fails a test.

## Fourth cross-review

A fourth round found one medium defect, confirmed by CI, and three small ones:

1. On Python 3.10 to 3.12, `Path.is_dir()` raises `PermissionError` for a path
   inside a directory without search permission, so the output check crashed to
   the generic message and the shared test errored on the 3.10 CI job (3.14
   locally hid it). It now uses `os.path.isdir()`. Verified in Docker with
   `python:3.10-slim` as a non-root user: 2 errors before, green after.
2. In a sticky directory such as `/tmp`, rename cannot replace another user's
   file, so a paid answer could be lost after the POST. `replace_denied()` now
   blocks that before any request; the test fakes another user with a patched
   `geteuid` and also covers the owner, a new file and a non-sticky directory.
3. A diarization file name that is not UTF-8 made `--format rttm` blame the
   content; the RTTM file ID now shows such bytes as U+FFFD.
4. A tie test now has the first speaker last in alphabetical order.

Tests 2 and 3 failed first; 4 only adds coverage. Each of 4 mutations fails a
test.

## Final results

- `env -u NEURALDEEP_API_KEY CODDY_HOME=/nonexistent python3 -X warn_default_encoding -B -m unittest discover -s tests`:
  **121 tests passed** (1 skipped outside a tag build), 0 EncodingWarnings.
- The same suite under `LC_ALL=C PYTHONUTF8=0`: passed.
- The same suite on Python 3.10.22 (`python:3.10-slim` in Docker, non-root, no network): passed.
- `python3 -B scripts/client.py --help`: passed, with no network call.
- Fenced Python examples parsed with `ast.parse`; Bash examples passed `bash -n`.
