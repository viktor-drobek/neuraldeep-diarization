import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("client", ROOT / "scripts" / "client.py")
client = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(client)


def limits():
    return {"tier": "starter", "key": {"status": "ok", "billing_mode": "subscription"},
            "decision": {"can_request": True}}


def prices(premium=False):
    return {"prices": [{"model": "audio:diarize", "billing": "unit", "unit_rub": 0.3, "premium": premium}]}


def quota(day_used=0):
    # Shape observed read-only on 2026-10-18; the values are synthetic.
    return {"unit": "minute", "tier": "starter", "day": {"used": day_used, "limit": 300},
            "month": {"used": 0, "limit": 3000}}


def diarization():
    return {"duration": 61.0, "num_speakers": 2, "minutes_charged": 2,
            "segments": [{"speaker": "SPEAKER_0", "start": 1.1, "end": 5.75},
                         {"speaker": "SPEAKER_1", "start": 17.28, "end": 21.26}]}


def run_cli(argv):
    with patch.object(sys, "argv", ["client.py", *argv]), patch("sys.stdout", new_callable=io.StringIO) as out:
        code = client.main()
    return code, json.loads(out.getvalue())


def skill():
    return (ROOT / "SKILL.md").read_text(encoding="utf-8")


class DiarizationTests(unittest.TestCase):
    def test_repo_service_and_public_price_id(self):
        self.assertEqual(client.SERVICE, "diarize")
        self.assertEqual(client.OPERATIONS["diarize"], ("diarize",))
        self.assertEqual(client.price_id("diarize", "diarize"), "audio:diarize")
        self.assertIn("diarize", client.SYNCHRONOUS)

    def test_check_reads_limits_prices_and_quota_and_reports_ready(self):
        with patch.object(client, "resolve_key", return_value="fixture"), \
                patch.object(client, "request", side_effect=[limits(), prices(), quota()]) as req:
            code, result = run_cli(["check", "diarize", "--minutes", "3"])
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["service"], "diarize")
        self.assertEqual(result["quota_observed"]["units_required"], 3)
        self.assertEqual(result["quota_observed"]["buckets"]["day"], {"used": 0, "limit": 300})
        self.assertEqual([c.args[:2] for c in req.call_args_list],
                         [("GET", client.HUB + "/limits"), ("GET", client.PRICES),
                          ("GET", client.HUB + "/audio/diarize/quota")])

    def test_check_blocks_without_minutes_or_when_the_day_is_spent(self):
        for argv, day_used in ((["check"], 0), (["check", "--minutes", "5"], 298)):
            with self.subTest(argv=argv), patch.object(client, "resolve_key", return_value="fixture"), \
                    patch.object(client, "request", side_effect=[limits(), prices(), quota(day_used)]):
                code, result = run_cli(argv)
            self.assertEqual((code, result["status"]), (1, "blocked"))

    def test_run_submits_once_and_saves_the_diarization(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(client, "resolve_key", return_value="fixture"):
            audio, state, output = Path(tmp) / "meeting.wav", Path(tmp) / "state.json", Path(tmp) / "diarization.json"
            audio.write_bytes(b"RIFF fixture")
            responses = [limits(), prices(), quota(), diarization()]
            with patch.object(client, "request", side_effect=responses) as req:
                code, result = run_cli(["run", "diarize", "--file", str(audio), "--minutes", "2",
                                        "--state", str(state), "--output", str(output)])
            saved = json.loads(state.read_text(encoding="utf-8"))
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), diarization())
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(saved["status"], "completed")
        self.assertEqual(saved["quota_observed"]["units_required"], 2)
        self.assertEqual([c.args[0] for c in req.call_args_list], ["GET", "GET", "GET", "POST"])

    def test_merge_builds_a_speaker_transcript_from_a_transcription(self):
        transcript = {"segments": [{"start": 1.0, "end": 5.0, "text": " Привет."},
                                   {"start": 17.5, "end": 21.0, "text": " Hello."}]}
        with tempfile.TemporaryDirectory() as tmp, patch.object(client, "request") as req:
            d, t, out = Path(tmp) / "diarization.json", Path(tmp) / "transcript.json", Path(tmp) / "speakers.json"
            d.write_text(json.dumps(diarization()), encoding="utf-8")
            t.write_text(json.dumps(transcript, ensure_ascii=False), encoding="utf-8")
            code, result = run_cli(["merge", "--diarization", str(d), "--transcript", str(t), "--output", str(out)])
            merged = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual((code, result["status"]), (0, "completed"))
        self.assertEqual([(turn["speaker"], turn["text"]) for turn in merged["turns"]],
                         [("SPEAKER_0", "Привет."), ("SPEAKER_1", "Hello.")])
        req.assert_not_called()

    def test_documentation_names_the_endpoint_quota_and_merge(self):
        text = skill()
        self.assertIn("name: neuraldeep-diarization\n", text)
        for needle in ("POST /v1/audio/diarize", "GET /v1/audio/diarize/quota", "audio:diarize", "0.3",
                       "python3 scripts/client.py check diarize --minutes", "python3 scripts/client.py run diarize",
                       "python3 scripts/client.py merge", "/v1/audio/transcriptions", "neuraldeep-transcriptions",
                       "neuraldeep-speechcore", "500 MB", "4 hours", "8 speakers", "`limit - used`",
                       "--format vtt", "--format srt", "--format rttm", "<v SPEAKER_0>", "max(120, 30 * minutes)"):
            self.assertIn(needle, text)
        relay = (ROOT / "STARTER_RELAY.md").read_text(encoding="utf-8")
        self.assertRegex(relay, r"\| Diarization \| `/v1/audio/diarize/quota`: `unit: minute`, `tier`, `day` and `month`")
        for needle in ("WebVTT, SRT or RTTM", "Artifact directory is missing or not writable"):
            self.assertIn(needle, relay)
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("/v1/audio/diarize", readme)
        self.assertIn("WebVTT, SRT or RTTM", readme)

    def test_skill_declares_its_transcription_dependency(self):
        head = skill().split("---", 2)[1]
        self.assertIn("    depends_on:\n      - neuraldeep-transcriptions\n", head)
        self.assertIn("      - /audio/diarize\n", head)

    def test_skill_does_not_advertise_what_the_helper_does_not_send(self):
        text = skill()
        for claim in ("--rttm", "--min-duration", "--response-format", "recognises speech", "recognizes speech"):
            self.assertNotIn(claim, text)
        self.assertIn("The helper sends only the audio file", text)

    def test_agents_guide_covers_codex_coddy_and_the_shared_helper(self):
        guide = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        for needle in ("## Codex", "## Coddy", "/v1/audio/diarize", "do not push to `main`",
                       "no `Co-Authored-By` trailer", "diff <(grep -v '^SERVICE = ' scripts/client.py)",
                       "speechcore, search, ocr, images, transcriptions, diarization"):
            self.assertIn(needle, guide)

    def test_skill_says_blocked_is_final_and_forbids_bypass(self):
        text = skill()
        section = text.split("## When the helper says `blocked`", 1)
        self.assertEqual(len(section), 2, "missing blocked section")
        head, rules = section[0], section[1].split("\n## ", 1)[0]
        self.assertLess(len(head.split("\n# ", 1)[1]), 1500, "blocked section must come early")
        for needle in ("final answer", "neuraldeep-auth.json", "NEURALDEEP_API_KEY",
                       "POST /v1/audio/diarize", "by hand", "supervisor", "undocumented", "reconciliation_required"):
            self.assertIn(needle, rules)
        self.assertIn("never bypass", text.split("---", 2)[1])


if __name__ == "__main__":
    unittest.main()
