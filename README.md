# 👥 neuraldeep-diarization

Speaker diarization on the NeuralDeep Hub (`POST /v1/audio/diarize`,
Nemotron-3-Diarization, up to 8 speakers): who spoke when, as timed speaker
segments without text. The guarded helper checks the live diarization minute
quota before it submits, saves the validated JSON, and merges it offline with a
timed transcript from `/v1/audio/transcriptions` (the
[neuraldeep-transcriptions](https://github.com/viktor-drobek/neuraldeep-transcriptions)
skill) or an existing SpeechCore job into a transcript split by speaker,
written as JSON, WebVTT, SRT or RTTM. A new transcript needs a wallet key and the user's approval of its cost, so
check a transcript exists before paying for a diarization meant for one.

A [Coddy](https://coddy.dev) / AI-agent skill for the **NeuralDeep Hub API**.
Model page: <https://hub.neuraldeep.ru/models/nemotron-3-diarization>.

## Author

**Viktor Drobek**

## Install

```bash
# via the skillsbd catalog
npx skillsbd add viktor-drobek/neuraldeep-diarization/neuraldeep-diarization

# or directly from this repo
npx skillsbd add https://github.com/viktor-drobek/neuraldeep-diarization --skill neuraldeep-diarization
```

## Requirements

- A NeuralDeep API key (`sk-...`) in this skill's own variable `NEURALDEEP_DIARIZATION_API_KEY` (several
  keys may be separated by commas), or the shared `NEURALDEEP_API_KEY`, set in the
  environment or in `${CODDY_HOME:-~/.coddy}/.env`:

  ```bash
  echo 'NEURALDEEP_DIARIZATION_API_KEY=sk-...' >> ~/.coddy/.env
  ```
- Python 3.10+ (standard library only).
- Get a key at <https://neuraldeep.ru> (Hub).

## Usage

See [`SKILL.md`](./SKILL.md) for the preflight, diarization and merge commands,
the endpoint reference, and the cost and safety rules.

## Starter guard and Relay handoff

See [STARTER_RELAY.md](./STARTER_RELAY.md) for the guard, private state, and the
optional artifact-based Relay envelope. The helper checks the live
`GET /v1/audio/diarize/quota` minutes (`limit - used` per day and month) rather
than hard-coding limits. Diarization is synchronous, so nothing can be resumed:
an uncertain submission needs reconciliation, never a retry.

Run offline tests: `python3 -B -m unittest discover -s tests`.

## License

[MIT](./LICENSE)
