"""
engine.py
─────────
The Advisor — Layer 3 of the Suraksha Saathi pipeline.

Migrated to google-genai SDK (replaces deprecated google-generativeai).


"""

from __future__ import annotations

import os
import json
import logging
import asyncio
import functools
from dataclasses import dataclass, asdict, field
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

from google import genai
from google.genai import types as genai_types

logger = logging.getLogger(__name__)

_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite-preview")


# ── Result schema ─────────────────────────────────────────────────────────────

@dataclass
class AnalysisResult:
    matched_pattern:        str       = ""
    matched_category:       str       = ""
    matched_severity:       str       = ""
    similarity_score:       float     = 0.0
    gemini_risk_score:      int       = 0
    gemini_summary:         str       = ""
    gemini_danger_level:    str       = "LOW"
    scam_type:              str       = ""
    psychological_tactics:  list[str] = field(default_factory=list)
    reasoning:              str       = ""
    danger_level:           str       = "LOW"
    hinglish_advice:        str       = ""
    safe_action:            str       = ""
    contextual_accuracy:    float     = 0.0
    flagged:                bool      = False
    error:                  str       = ""
    analysis_source:        str       = "unavailable"

    def to_dict(self) -> dict:
        return asdict(self)

    def to_log_row(self) -> dict:
        return {
            "matched_pattern":  self.matched_pattern,
            "category":         self.matched_category,
            "similarity_score": f"{self.similarity_score:.0%}",
            "risk_score":       self.gemini_risk_score,
            "danger_level":     self.danger_level,
            "scam_type":        self.scam_type,
            "flagged":          self.flagged,
        }


# ── Shared client helper ──────────────────────────────────────────────────────

def _get_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set.")
    return genai.Client(api_key=api_key)


def _call_gemini(system: str, user_msg: str) -> str:
    """Single helper that calls Gemini and returns raw text."""
    client = _get_client()
    response = client.models.generate_content(
        model=_GEMINI_MODEL,
        contents=user_msg,
        config=genai_types.GenerateContentConfig(
            system_instruction=system,
        ),
    )
    return response.text.strip()


def _parse_json(raw: str) -> dict:
    clean = raw.strip()
    if clean.startswith("```"):
        clean = clean.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return json.loads(clean)


# ── Stage A — Fast Risk Score ─────────────────────────────────────────────────

_STAGE_A_SYSTEM = """\
You are a cybersecurity risk scorer for Suraksha Saathi,
protecting non-technical Indian users from UPI scams and phishing.

Given a suspicious message and its closest historical scam match,
return ONLY valid JSON (no markdown, no extra text):
{
  "risk_score": <int 0-10>,
  "danger_level": "<CRITICAL|HIGH|MEDIUM|LOW>",
  "summary": "<one Hinglish sentence summarising the threat>"
}"""


def _gemini_score(email_text: str, match: dict, score: float) -> dict:
    prompt = (
        f"EMAIL:\n\"{email_text}\"\n\n"
        f"CLOSEST MATCH (similarity {score:.0%}):\n"
        f"Pattern: {match['pattern']}\n"
        f"Logic: {match['logic']}"
    )
    raw = _call_gemini(_STAGE_A_SYSTEM, prompt)
    return _parse_json(raw)


# ── Stage B — Deep Psychological Reasoning ────────────────────────────────────

_STAGE_B_SYSTEM = """\
You are the Senior Security Analyst for "Suraksha Saathi,"
an AI-powered cybersecurity agent protecting non-technical Indian users from
UPI scams, phishing, and digital fraud.

Your role is the DEEP REASONING LAYER in a multi-agent pipeline:
  • A TF-IDF / embedding engine found the closest historical scam pattern.
  • A first Gemini call (Stage A) may already have issued a fast risk score.
  • You perform PSYCHOLOGICAL INTENT ANALYSIS — not keyword matching.

Analyse the TARGET EMAIL against the CONTEXT MATCH. Identify:
  1. Artificial urgency (time pressure, countdown, "immediate action")
  2. Authority impersonation (govt, bank, police, military)
  3. Request-Money vs Receive-Money confusion (classic UPI trick)
  4. Fear amplification (arrest, disconnection, account block)
  5. Isolation tactic ("don't tell anyone", "stay on the call")
  6. Advance fee pattern (pay small to get big)

Return ONLY valid JSON — no markdown, no preamble:
{
  "contextual_match_accuracy": <float 0.0-1.0>,
  "scam_type": "<short category name>",
  "psychological_tactics": ["<tactic1>", "<tactic2>", "<tactic3>"],
  "reasoning": "<2-3 sentences: HOW this mirrors the matched pattern>",
  "danger_level": "<CRITICAL|HIGH|MEDIUM|LOW>",
  "hinglish_advice": "<2-3 warm protective sentences in REQUESTED LANGUAGE>",
  "safe_action": "<one concrete action the user should take RIGHT NOW>"
}"""

_LANG_INSTRUCTION = {
    "en":  "Respond in ENGLISH. Write advice and reasoning in clear, friendly English.",
    "hi":  "हिंदी में जवाब दें। सलाह और विश्लेषण सरल हिंदी में लिखें।",
    "hng": "Hinglish mein jawab dena (Roman script). Advice dadi/nana style mein, village metaphors ke saath.",
}


def _gemini_reason(
    email_text: str,
    match: dict,
    score: float,
    stage_a_result: Optional[dict] = None,
    language: str = "hng",
) -> dict:
    system = _STAGE_B_SYSTEM + "\n\nLANGUAGE INSTRUCTION: " + _LANG_INSTRUCTION.get(language, _LANG_INSTRUCTION["hng"])

    stage_a_context = ""
    if stage_a_result:
        stage_a_context = (
            f"\nSTAGE A FAST SCORE:\n"
            f"Risk Score : {stage_a_result.get('risk_score', '?')}/10\n"
            f"Danger     : {stage_a_result.get('danger_level', '?')}\n"
            f"Summary    : {stage_a_result.get('summary', '')}\n"
        )

    user_msg = (
        f"TARGET EMAIL:\n\"{email_text}\"\n\n"
        f"CONTEXT MATCH FROM DATABASE (similarity {score:.0%}):\n"
        f"Pattern  : {match['pattern']}\n"
        f"Sample   : \"{match['content']}\"\n"
        f"Logic    : {match['logic']}\n"
        f"Category : {match['category']}\n"
        f"Severity : {match['severity']}\n"
        f"{stage_a_context}\n"
        "Perform your deep contextual analysis now."
    )

    raw = _call_gemini(system, user_msg)
    return _parse_json(raw)


# ── Public API ────────────────────────────────────────────────────────────────

def analyze(
    email_text: str,
    match: dict,
    similarity_score: float,
    risk_threshold: int = 5,
    language: str = "hng",
) -> AnalysisResult:
    result = AnalysisResult(
        matched_pattern=match["pattern"],
        matched_category=match["category"],
        matched_severity=match["severity"],
        similarity_score=similarity_score,
    )

    if not os.environ.get("GEMINI_API_KEY"):
        result.error = "GEMINI_API_KEY not set — analysis skipped."
        result.danger_level = match["severity"]
        return result

    # Stage A
    stage_a_result: Optional[dict] = None
    try:
        stage_a_result = _gemini_score(email_text, match, similarity_score)
        result.gemini_risk_score   = int(stage_a_result.get("risk_score", 0))
        result.gemini_summary      = stage_a_result.get("summary", "")
        result.gemini_danger_level = stage_a_result.get("danger_level", "LOW")
        result.analysis_source = "partial"
        logger.info("Stage A complete — risk %d/10", result.gemini_risk_score)
    except Exception as exc:
        logger.warning("Stage A failed: %s", exc)

    # Stage B
    try:
        stage_b = _gemini_reason(email_text, match, similarity_score, stage_a_result, language)
        result.contextual_accuracy   = float(stage_b.get("contextual_match_accuracy", 0))
        result.scam_type             = stage_b.get("scam_type", "")
        result.psychological_tactics = stage_b.get("psychological_tactics", [])
        result.reasoning             = stage_b.get("reasoning", "")
        result.danger_level          = stage_b.get("danger_level", "LOW")
        result.hinglish_advice       = stage_b.get("hinglish_advice", "")
        result.safe_action           = stage_b.get("safe_action", "")
        result.analysis_source       = "gemini"
        logger.info("Stage B complete — danger: %s", result.danger_level)
    except Exception as exc:
        result.error = f"Stage B failed: {exc}"
        logger.error(result.error)
        result.danger_level = result.gemini_danger_level or match["severity"]

    # Flagging
    danger_rank = {"CRITICAL": 10, "HIGH": 8, "MEDIUM": 5, "LOW": 2}
    effective_score = max(result.gemini_risk_score, danger_rank.get(result.danger_level, 0))
    result.flagged = effective_score > risk_threshold

    return result


async def analyze_async(
    email_text: str,
    match: dict,
    similarity_score: float,
    risk_threshold: int = 5,
    language: str = "hng",
) -> AnalysisResult:
    """Async wrapper — runs blocking analyze() in a thread pool."""
    loop = asyncio.get_event_loop()
    fn = functools.partial(analyze, email_text, match, similarity_score, risk_threshold, language)
    return await loop.run_in_executor(None, fn)


# ── CLI test ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    from context.matcher import find_context_match

    msg = " ".join(sys.argv[1:]) or (
        "Your SBI account KYC has expired. "
        "Click http://sbi-update.xyz to avoid account block within 24 hours."
    )
    print(f"\nAnalysing: {msg[:80]}…\n")
    m, s = find_context_match(msg)
    r = analyze(msg, m, s)
    print(json.dumps(r.to_dict(), indent=2, ensure_ascii=False))
