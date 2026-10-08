"""
api.py
──────
FastAPI bridge for Suraksha Saathi v2.1
Exposes the Python engine to the React dashboard via HTTP.

Run:
    python api.py
    # → http://localhost:8000
    # → http://localhost:8000/docs  (auto Swagger UI)

Endpoints:
    POST /analyze        — run full pipeline on a message
    GET  /logs           — guardian_logs.csv as JSON
    GET  /knowledge-base — all scam patterns (filterable)
    GET  /stats          — metrics with REAL accuracy score
    GET  /health         — API + key status
"""

from __future__ import annotations

import os
import csv
import hashlib
import logging
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()   # loads .env from current working directory

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from context.matcher import find_context_match
from context.samples import SCAM_SAMPLES
from engine import analyze_async, AnalysisResult

# Close matches can return the curated entry without Gemini. Similarity is not
# a calibrated probability of fraud; expose the source in the response.
AI_SKIP_THRESHOLD = 0.92

logger = logging.getLogger(__name__)

app = FastAPI(title="Suraksha Saathi API", version="2.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

LOG_CSV = Path("guardian_logs.csv")

# ── In-memory response cache (Fix 3) ─────────────────────────────────────────
# Stores up to 256 recent analysis results keyed by MD5(message|lang|threshold).
# Same message submitted twice → instant response, zero AI cost.
_RESULT_CACHE: dict[str, "AnalysisResult"] = {}
_CACHE_MAX = 256

def _get_cached_result(key: str) -> "AnalysisResult | None":
    return _RESULT_CACHE.get(key)

def _set_cached_result(key: str, result: "AnalysisResult") -> None:
    if len(_RESULT_CACHE) >= _CACHE_MAX:
        # Evict oldest entry (insertion-ordered dict since Python 3.7)
        _RESULT_CACHE.pop(next(iter(_RESULT_CACHE)))
    _RESULT_CACHE[key] = result


# ── Retrieval self-check: computed once at startup ────────────────────────────
# Query each library entry against that same library. This is not an independent
# evaluation of fraud detection and must not be presented as system accuracy.
# If the matcher's top result == that sample's id → correct.

def _compute_kb_accuracy() -> tuple[float, int, int]:
    correct = 0
    total = len(SCAM_SAMPLES)
    for sample in SCAM_SAMPLES:
        try:
            match, _ = find_context_match(sample["content"])
            if match.get("id") == sample["id"]:
                correct += 1
        except Exception:
            pass
    accuracy = correct / total if total else 0.0
    return accuracy, correct, total

_KB_ACCURACY, _KB_CORRECT, _KB_TOTAL = _compute_kb_accuracy()
_KB_ACCURACY_STR = f"{_KB_ACCURACY:.1%}"


# ── Models ───────────────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    message: str
    language: str = "en"       # "en" | "hi" | "hng"
    risk_threshold: int = 5


class AnalyzeResponse(BaseModel):
    matched_pattern: str
    matched_category: str
    matched_severity: str
    similarity_score: float
    gemini_risk_score: int
    gemini_summary: str
    scam_type: str
    psychological_tactics: list[str]
    reasoning: str
    danger_level: str
    hinglish_advice: str
    safe_action: str
    contextual_accuracy: float
    flagged: bool
    error: str
    advice: str
    analysis_source: str


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_message(req: AnalyzeRequest):
    """Run the full 3-layer pipeline on a suspicious message."""

    # Input validation
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
    if len(req.message) > 5000:
        raise HTTPException(status_code=400, detail="Message too long (max 5000 chars).")
    if req.language not in ("en", "hi", "hng"):
        raise HTTPException(status_code=400, detail="language must be 'en', 'hi', or 'hng'.")
    if not (0 <= req.risk_threshold <= 10):
        raise HTTPException(status_code=400, detail="risk_threshold must be 0–10.")

    # Layer 2: matcher
    try:
        match, score = find_context_match(req.message)
    except Exception as exc:
        logger.error("Matcher failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Context matcher error: {exc}")

    if not match:
        raise HTTPException(status_code=500, detail="Matcher returned no result.")

    # ── Fix 2: Skip AI for very high-confidence KB matches ───────────────────
    # If the matcher is already ≥92% confident, the pattern is unambiguous.
    # Build a synthetic result from the KB entry — zero latency, zero API cost.
    if score >= AI_SKIP_THRESHOLD:
        logger.info("AI skip: score %.2f ≥ %.2f, using KB result directly.", score, AI_SKIP_THRESHOLD)
        result = AnalysisResult(
            matched_pattern=match["pattern"],
            matched_category=match["category"],
            matched_severity=match["severity"],
            similarity_score=score,
            gemini_risk_score={"CRITICAL": 10, "HIGH": 8, "MEDIUM": 5, "LOW": 2}.get(match["severity"], 5),
            gemini_summary=f"High-confidence match: {match['pattern']}",
            gemini_danger_level=match["severity"],
            scam_type=match["category"],
            psychological_tactics=[],
            reasoning=f"Direct KB match (similarity {score:.0%}). Pattern: {match['logic']}",
            danger_level=match["severity"],
            hinglish_advice=match.get({"en": "advice_en", "hi": "advice_hi", "hng": "advice_hng"}[req.language], ""),
            safe_action="Do not respond or click any links. Report to Cyber Crime at 1930.",
            contextual_accuracy=score,
            flagged={"CRITICAL": 10, "HIGH": 8, "MEDIUM": 5, "LOW": 2}.get(match["severity"], 5) > req.risk_threshold,
            error="",
            analysis_source="knowledge_base",
        )
    else:
        # Layer 3: Gemini AI (async) — only for ambiguous matches
        # ── Fix 3: LRU cache keyed on (message, language, threshold) ─────────
        cache_key = hashlib.md5(
            f"{req.message}|{req.language}|{req.risk_threshold}".encode()
        ).hexdigest()

        cached = _get_cached_result(cache_key)
        if cached is not None:
            logger.info("Cache hit for key %s", cache_key[:8])
            result = cached
        else:
            try:
                result = await analyze_async(
                    email_text=req.message,
                    match=match,
                    similarity_score=score,
                    risk_threshold=req.risk_threshold,
                    language=req.language,
                )
                _set_cached_result(cache_key, result)
            except Exception as exc:
                logger.error("Engine failed: %s", exc)
                raise HTTPException(status_code=500, detail=f"Analysis engine error: {exc}")

    # Language-aware KB advice
    advice_key = {"en": "advice_en", "hi": "advice_hi", "hng": "advice_hng"}.get(
        req.language, "advice_en"
    )
    advice = match.get(advice_key, match.get("advice_en", ""))

    return AnalyzeResponse(**result.to_dict(), advice=advice)


@app.get("/logs")
async def get_logs(limit: int = 50):
    if not LOG_CSV.exists():
        return {"logs": [], "total": 0}
    try:
        with LOG_CSV.open(encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not read log file: {exc}")
    rows.reverse()
    return {"logs": rows[:limit], "total": len(rows)}


@app.get("/knowledge-base")
async def get_knowledge_base(search: str = ""):
    try:
        patterns = SCAM_SAMPLES
        if search:
            q = search.lower()
            patterns = [
                p for p in patterns
                if q in (p["pattern"] + p["category"] + p.get("content", "")).lower()
            ]
        return {"patterns": patterns, "total": len(patterns)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Knowledge base error: {exc}")


@app.get("/stats")
async def get_stats():
    total = 0
    flagged = 0
    categories: dict[str, int] = {}

    if LOG_CSV.exists():
        try:
            with LOG_CSV.open(encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    total += 1
                    if row.get("flagged", "").lower() == "true":
                        flagged += 1
                    cat = row.get("category", "Unknown")
                    categories[cat] = categories.get(cat, 0) + 1
        except Exception as exc:
            logger.warning("Could not read logs for stats: %s", exc)

    return {
        "total_scanned": total,
        "total_flagged": flagged,
        "kb_patterns": len(SCAM_SAMPLES),
        "accuracy": _KB_ACCURACY_STR,           # legacy field: retrieval self-check only
        "accuracy_detail": {
            "correct": _KB_CORRECT,
            "total": _KB_TOTAL,
            "method": "Retrieval self-check on the same 40 library entries; not detection accuracy",
        },
        "top_categories": sorted(categories.items(), key=lambda x: -x[1])[:5],
    }


@app.get("/health")
async def health():
    log_count = 0
    if LOG_CSV.exists():
        try:
            log_count = sum(1 for _ in LOG_CSV.open()) - 1
        except Exception:
            pass
    return {
        "status": "ok",
        "gemini_key_set": bool(os.getenv("GEMINI_API_KEY")),
        "telegram_set": bool(os.getenv("TELEGRAM_BOT_TOKEN")),
        "log_entries": log_count,
        "kb_accuracy": _KB_ACCURACY_STR,
        "kb_patterns": len(SCAM_SAMPLES),
        "cache_entries": len(_RESULT_CACHE),
        "ai_skip_threshold": AI_SKIP_THRESHOLD,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=True)
