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

## Fifth cross-review

A fifth round found one medium and four low edge cases:

1. Any `OSError` from `lstat` counted as "nothing to replace", so an output
   name longer than the file system allows passed every check and the paid
   answer was lost after the POST. Only `FileNotFoundError` is ignored now;
   anything else blocks with "Artifact path is not usable".
2. A speaker label with a lone surrogate escape made `--format rttm` fall back
   to the advice for billed jobs; it now blocks with "Input text is not valid
   Unicode", like the other formats.
3. A validated paid answer with a lone surrogate escape could not be encoded
   for saving; the diarization artifact is now written with ASCII escapes.
4. The diarization shape check of `--format rttm` had no test; it has now.
5. The same-file checks of `run` and `merge` compared resolved paths only, so a
   hard link or a case alias on a case-insensitive file system could replace an
   input. `same_file()` adds `os.path.samefile()`; tested with hard links.

Tests 1, 2, 3 and 5 failed first; 4 is part of the RTTM test. Each of 5
mutations fails a test, on Python 3.14 and 3.10.

## Sixth cross-review

A sixth round found four low items:

1. `--state` and `--output` differing only in case passed on a case-insensitive
   file system, because the state did not exist when they were compared; the
   answer then replaced the state and was lost. `same_file()` now also runs
   once the state exists, before any request. The test simulates a
   case-insensitive `os.path.samefile()`.
2. Some file systems (vfat, exFAT, SMB) refuse a name only on create, so a
   lookup could not find it. A new output name is now created with `O_EXCL` and
   removed again before the preflight; the test simulates an `EINVAL` create
   and checks that a usable probe leaves no file.
3. Consecutive unassigned segments were joined into one `speaker: null` turn;
   they now stay separate turns.
4. SKILL.md said "turn" where WebVTT and SRT now write one cue per segment.

All four tests failed first. Each of 4 mutations fails a test, on Python 3.14
and 3.10.

## Seventh cross-review

A seventh round found one low item: with `--file x --state x` and no `x` yet,
`new_state()` created `x` and the helper then uploaded its own state JSON to the
billed endpoint. Once the state exists, `run` now blocks an input file that is
the state file, also through a case alias, before any request. A blanket "the
input must exist" check before the state would have changed transcription's
blocked `run`, which still leaves a state file. The test, for diarize and OCR,
failed first, and its mutation fails it, on Python 3.14 and 3.10.

## Eighth cross-review

An eighth round found two low items:

1. The U+FFFD repair added for non-UTF-8 file names also ran on speaker labels,
   so `--format rttm` merged distinct labels with lone low surrogates (such as
   `\udce9` and `\udcea`) into one speaker, where the other formats block. The
   repair now applies to the file ID only; such labels block with "Input text
   is not valid Unicode". The test failed first.
2. The input-is-the-state test used one path string for both, so comparing the
   strings instead of `same_file()` still passed; it now also covers a dangling
   symlink to the future state file.

Each of 3 mutations fails a test, on Python 3.14 and 3.10.

## Ninth cross-review: streamed uploads

The ninth round found that the POST timeout also bounded the whole upload:
over TLS the in-memory body went out in one `sendall` under one deadline, so a
large file on a slow link always ended `reconciliation_required` without the
provider ever receiving it. The owner asked for chunked sending with resume
where the API supports it, and for each API's size limit.

- **Provider support.** `llms-full.txt` (re-read 2026-10-18, unchanged)
  documents no chunked or resumable upload for any endpoint, and the SpeechCore
  section says to upload large files whole. So nothing can be continued after
  a break; by the owner's decision a broken upload is never resent.
- **Streaming.** `multipart()` now returns an `UploadBody` that `http.client`
  reads in 8 KB blocks, with a normal `Content-Length` (no chunked transfer
  encoding), so the server sees the same request. Each block is one socket
  timeout window, and no copy of the file sits in memory. Exactly the size
  checked before the request is sent; a file that shrinks meanwhile raises.
- **Limits.** `UPLOAD_LIMITS = {"diarize": 500 MB}` holds only documented limits;
  OCR, Images, SpeechCore and transcription document none, so none is assumed.
  The cap is checked on the same size that is streamed.

Five tests were added first and failed (the body was bytes, and
`UPLOAD_LIMITS` did not exist); the shared multipart tests now read the body
with `drain()`. Each of 6 mutations fails a test. A local TLS server reading
slowly (`SO_RCVBUF` 64 KB, 50 ms per read) took a 6 MB upload with a 2 s
timeout: the old in-memory body failed after 2.0 s with about 640 KB received;
the streamed body delivered all 6 MB in 38.7 s and got `HTTP 200`, on Python
3.14 and on 3.10 in Docker. The client's send buffer was set to 64 KB in that
script so the kernel could not hide unsent megabytes.

## Tenth cross-review

The tenth round found a regression from streaming and a documentation error:

1. `multipart()` only stat'ed the input and the file was first opened while
   sending, so a mode-000 file, another user's 0600 file, a directory or a FIFO
   passed every local check and failed after the preflight, as a false
   `reconciliation_required`. Before streaming such a run blocked early.
   `multipart()` now opens the input with `O_NONBLOCK` (a FIFO would wait for a
   writer), takes the size from `fstat()` on the open file and refuses anything
   but a regular file, so the checked size and the sent bytes come from one
   file. `execute()` closes a body that was opened but never sent.
2. The docs said 64 KB blocks, but `http.client` reads 8 KB blocks; the docs say
   8 KB now, and a documentation test refuses "64 KB".

The unreadable, directory and FIFO tests (for diarize and OCR) and the
documentation test failed first; the close test guards the new open file. Each
of 4 mutations fails a test (a blocking open hangs the FIFO test), on Python
3.14 and 3.10.

## Eleventh cross-review

Two reviewers found nothing and the third one low item: the upload descriptor
kept `O_NONBLOCK` after the regular-file check, and some FUSE or network file
systems honour it on reads, which the helper would take for a shrinking file
after the POST started. `multipart()` now clears it with `os.set_blocking()`
before reading. SKILL.md also says that ties go to the speaker who spoke first
in the recording and that an `--output` equal to the `--state` blocks. Both
tests failed first; removing `set_blocking` fails the new one. By the owner's
decision no further review round was run.

## Per-skill keys from Coddy's environment

By the owner's request each skill now asks for its own key. `resolve_keys()`
reads this skill's `NEURALDEEP_DIARIZATION_API_KEY`, then the shared
`NEURALDEEP_API_KEY`; each from the environment first, then from
`${CODDY_HOME}/.env`, which the helper parses itself with the rules of Coddy's
loader (`internal/config/dotenv.go`: `export`, quotes, double-quote escapes,
inline comments, the first assignment wins), so a key added there works without
restarting Coddy. The first source with a usable key wins. A value may hold
several keys separated by commas; `choose_key()` runs the free preflight for
each in order and uses the first that passes, and the quota observation records
the key's variable and number, never its value, so `resume` uses the key that
submitted the job and blocks, leaving the state untouched, when that key is no
longer configured. The Coddy provider file `neuraldeep-auth.json` is no longer
read. The other services read `NEURALDEEP_SEARCH_API_KEY`,
`NEURALDEEP_OCR_API_KEY`, `NEURALDEEP_IMAGES_API_KEY`,
`NEURALDEEP_SPEECHCORE_API_KEY` and `NEURALDEEP_TRANSCRIPTIONS_API_KEY`.

Six tests were added first and failed: the source order and fallback, the
`.env` parser against the cases of Coddy's own test, the key choice for `check`
and `run`, and resume with the recorded key. Every helper test now patches
`resolve_keys`. Each of 10 mutations fails a test (shared before own, no
fallback, `.env` before the environment, no `.env`, last assignment wins, `null`
kept, only the first key tried, resume ignoring the record, no key record, an
inline comment kept). `check` with no key prints `blocked` and names the
variable and the file. No live call was made: the helper no longer reads the
provider file that the earlier live checks used.

## Explained API errors

An HTTP error used to read only `HTTP <code>; no automatic retry`. The helper now
adds a fixed hint from `ERROR_HINTS`, the statuses the provider documents
(`llms-full.txt`: 400, 401, 408, 429, 500, 502 in "Лимиты и коды ошибок", 422 and
503 in the SpeechCore upload errors), plus `Retry-After` when it is whole seconds
(at most six digits) and `X-Window` when it is `session` or `week`; any other
header value is dropped. The provider's response body and reason text are still
never shown. Every SKILL.md has an "Error handling" table of these statuses, with
what each means at preflight (`blocked`), on submission
(`reconciliation_required`) and while polling (`poll_error`); a shared test checks
that the table lists every code of `ERROR_HINTS`. The three tests failed first;
each of 5 mutations fails one.

## Twelfth cross-review

Three low items. `read_dotenv()` read the file as strict UTF-8, so one stray
byte (a cp1251 comment) hid every key in it; Coddy reads it line by line as
bytes. It now decodes with replacement, and a test with a cp1251 comment next to
a key failed first. SKILL.md said more than 240 minutes is refused before any
request; that check runs after the free GETs, before the billed request, and the
text says so now. A cap test left two upload files open (`ResourceWarning`); it
closes them, and the suite now runs clean under `-W always::ResourceWarning`.
The Error handling tables say the key may be in the environment or `~/.coddy/.env`,
and the diarization SKILL.md no longer mentions `resume`, which it refuses.

## Thirteenth cross-review

Two low items. The 401 row of the Error handling table told the agent to check
the key in `~/.coddy/.env`, against the rule never to read that file; it now
asks the user to check it, and the shared documentation test requires "never
read the file yourself". `run` accepted an existing `--output` that is a FIFO, a
socket or a device (also behind a symlink): after the paid POST, `atomic_write()`
replaced that node with a regular file, which breaks `/dev/null` for everyone
when run as root. It now blocks before any request with "Artifact path is not a
regular file"; a dangling symlink is still replaced like a missing file. Both
tests failed first; each of 3 mutations fails one.

## Paying from the wallet

By the owner's request a key in wallet mode can now pay, but only with the
user's approval. A live read-only `GET /v1/limits` (2026-10-19, the owner's key)
showed `key.billing_mode: wallet`, `wallet.balance_rub` and a per-key
`key.cap` (`spend_cap_rub`, `spent_rub`, `cap_blocked`; not in the provider's
documentation). The provider documents that exactly one scheme is active and
that the wallet pays every operation at the public price list.

- `preflight()` reads the billing mode; for a wallet key `wallet_quote()` skips
  the subscription quota and estimates units x the price row's `unit_rub` or
  `rub_per_min`, rounded up to whole kopecks, and blocks when the estimate
  exceeds the wallet balance or the key's spending cap, or when `cap_blocked`.
- `choose_key()` prefers a subscription key; a wallet key is used only when none
  fits and only up to `--wallet-limit`, the roubles the user approved. Without
  it, `check` and `run` end `wallet_approval_required` (nothing sent) with the
  estimate, the balance and the exact command to run after a yes.
- SpeechCore and transcription stay disabled from the wallet too.
- The subscription guard now names the failing condition (billing mode, key
  status or tier) instead of one combined message.
- SKILL.md has a "Paying from the wallet" section telling the agent to show the
  warning and wait for an explicit yes; AGENTS.md forbids passing
  `--wallet-limit` without the user's approval; STARTER_RELAY.md lists the new
  status.

Nine tests failed first (the flag test passed only because argparse refused the
unknown flag); each of 10 mutations fails a test. A live read-only
`check diarize --minutes 2` with the owner's wallet key returned
`wallet_approval_required`: about 0.60 RUB (2 x 0.3 RUB for `audio:diarize`). No
billed request was sent.

## Wallet-paid transcription and SpeechCore uploads

By the owner's request the shared helper now submits to the two services that
were refused outright, but only with a wallet key and the user's approval; a
subscription key stays blocked at the guard, since neither has a verified
remaining-quota endpoint. Transcription posts `file` and `model` to
`POST /v1/audio/transcriptions` and validates the synchronous answer (`text`,
and timed `segments` when present), with the long `max(120, 30 * minutes)`
answer timeout; anything else is `reconciliation_required`. SpeechCore posts
`file` to `POST https://speechcore.neuraldeep.ru/api/upload`, keeps `task_id`
and polls the existing job path. `--minutes` is required for every
minute-billed service (diarize, transcription, SpeechCore). The wallet warning
adds the price row's per-million output-token rate when it has one, because the
provider does not say what it counts. Seven tests failed first; each of 7
mutations fails one. The diarization docs now say a new transcript needs a
wallet key and the user's approval.

## Fourteenth cross-review

Two low items. When no home directory could be determined (`CODDY_HOME` naming
an unknown `~user`, or no `HOME` and no passwd entry), `Path.home()` raised
`RuntimeError` and `check`/`run` printed a traceback instead of the JSON
envelope; `resolve_keys()` now treats that as "no .env" and reports the missing
key as usual. The test failed first, and the original case (Python 3.10 in
Docker as UID 4242 without `HOME`) now prints the blocked envelope. The Codex
section of AGENTS.md said a live `check` reads the key from `~/.coddy`; it now
names the environment and `${CODDY_HOME:-~/.coddy}/.env`.

## Release metadata (v1.0.0)

`metadata.version` stays 1.0.0: this skill has not been released yet, so its
first release is v1.0.0. `tests/test_release.py` passes; the tag check runs on
the `v1.0.0` tag build after the merge.

## Final results

- `env -u NEURALDEEP_API_KEY -u NEURALDEEP_DIARIZATION_API_KEY CODDY_HOME=/nonexistent python3 -X warn_default_encoding -B -m unittest discover -s tests`:
  **161 tests passed** (1 skipped outside a tag build), 0 EncodingWarnings.
- The same suite under `LC_ALL=C PYTHONUTF8=0`: passed; under `-W always::ResourceWarning`: no warning.
- The same suite on Python 3.10.22 (`python:3.10-slim` in Docker, non-root, no network): passed.
- `python3 -B scripts/client.py --help`: passed, with no network call.
- Fenced Python examples parsed with `ast.parse`; Bash examples passed `bash -n`.

## README and agent-rule verification (2026-10-26)

Added the shared README contract and stronger native-rule checks before the documentation and configuration fixes. The initial runs failed on missing README sections and host details, missing fork matching and incomplete new-family workflow guidance. A further failing recovery-guide test caught obsolete claims about wallet transcription and SpeechCore uploads.

The full source suite passed on Python 3.14.4 in normal, C-locale and encoding-warning modes. Each mode ran **171 tests with 1 expected non-tag skip**. No EncodingWarning was emitted. The runner supplied PATH, HOME and TMPDIR in a cleared environment, a nonexistent CODDY_HOME and no NeuralDeep credentials. It invoked these commands from the source root.

```bash
python3 -B -m unittest discover -s tests
LC_ALL=C PYTHONUTF8=0 python3 -B -m unittest discover -s tests
python3 -X warn_default_encoding -B -m unittest discover -s tests
python3 -B scripts/client.py --help
git diff --check
```

The README CLI examples passed argument parsing without operation execution. Fenced Bash examples passed `bash -n`. New-family JSON examples passed the pure planner. All Python files parsed with the Python 3.10 grammar. This is a syntax check, not a local Python 3.10 runtime claim. The source workflow was included in the successful actionlint check of all 16 source and collection workflows.

Tests check the CLAUDE.md symlink, Cursor and Claude rule parity and scopes, Codex session and edit payloads, deduplication, fork resets and fail-open behavior. These are offline adapter checks, not confirmation of native host UI context loading. Interactive Codex `/hooks` approval was not performed. A collection-level native CLI probe was attempted but did not complete.

Guarded helper hashes are unchanged. No live skill API call, paid skill submission, global provider or MCP change, release or PR merge was performed for this documentation verification.
