"""No live API calls, inbox access, or Telegram messages are made by these tests."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Singularity"))
os.environ["GEMINI_API_KEY"] = ""

from fastapi.testclient import TestClient
from context.samples import SCAM_SAMPLES
from context.matcher import _tfidf_match, _tokenize
from engine import _parse_json, analyze
from api import app


class OfflineReviewTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_all_patterns_retrieve_themselves(self):
        self.assertEqual(len(SCAM_SAMPLES), 40)
        for sample in SCAM_SAMPLES:
            with self.subTest(pattern=sample["id"]):
                match, score = _tfidf_match(sample["content"])
                self.assertEqual(match["id"], sample["id"])
                self.assertAlmostEqual(score, 1.0, places=4)

    def test_no_overlap_has_no_manufactured_score(self):
        _, score = _tfidf_match("quasar nebula spectroscopy")
        self.assertEqual(score, 0.0)

    def test_empty_text_is_handled_without_division(self):
        self.assertEqual(_tfidf_match("")[1], 0.0)

    def test_unicode_tokens_are_retained(self):
        self.assertTrue(_tokenize("हिंदी संदेश"))

    def test_library_shortcut_honours_language_and_threshold(self):
        sample = next(s for s in SCAM_SAMPLES if s["severity"] == "CRITICAL")
        with patch("api.analyze_async", side_effect=AssertionError("Unexpected model call")):
            response = self.client.post("/analyze", json={
                "message": sample["content"], "language": "hi", "risk_threshold": 10,
            })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["analysis_source"], "knowledge_base")
        self.assertEqual(data["hinglish_advice"], sample["advice_hi"])
        self.assertFalse(data["flagged"])

    def test_invalid_requests_are_rejected(self):
        for payload in [
            {"message": " "}, {"message": "x" * 5001},
            {"message": "hello", "language": "xx"},
            {"message": "hello", "risk_threshold": 11},
        ]:
            self.assertEqual(self.client.post("/analyze", json=payload).status_code, 400)

    def test_missing_key_is_explicit(self):
        sample = SCAM_SAMPLES[0]
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            result = analyze("unrelated message", sample, 0.1)
        self.assertEqual(result.analysis_source, "unavailable")
        self.assertIn("GEMINI_API_KEY", result.error)

    def test_json_fences_are_parsed_without_stripping_payload(self):
        self.assertEqual(_parse_json('```json\n{"danger_level":"HIGH"}\n```')["danger_level"], "HIGH")

    def test_stats_label_self_check_as_such(self):
        response = self.client.get("/stats")
        self.assertEqual(response.status_code, 200)
        self.assertIn("not detection accuracy", response.json()["accuracy_detail"]["method"])


if __name__ == "__main__":
    unittest.main()
