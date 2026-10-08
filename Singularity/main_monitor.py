"""
main_monitor.py
───────────────
The Watchman — Layer 1 of the Suraksha Saathi pipeline.

Connects to Gmail via IMAP (SSL), polls for UNSEEN emails every 30 seconds,
and feeds each new message through the full analysis pipeline:

    Gmail IMAP  →  matcher.find_context_match  →  engine.analyze  →  logger + alert

Environment variables required:
    GMAIL_ADDRESS    — your Gmail address
    GMAIL_APP_PASS   — 16-character Gmail App Password (not your Google password)
    GEMINI_API_KEY   — Google AI API key (powers both Stage A and Stage B)
    TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID  (optional — enables Telegram alerts)
    RISK_THRESHOLD   (optional, default 5)

Run:
    python main_monitor.py
"""

from __future__ import annotations

import os
import asyncio
import imaplib
import email
import logging
import csv
import json
from datetime import datetime
from email.header import decode_header
from pathlib import Path
from typing import Optional

from context.matcher import find_context_match
from engine import analyze_async, AnalysisResult

# ── Optional Telegram ────────────────────────────────────────────────────────
try:
    import telegram  # type: ignore
    _TELEGRAM_AVAILABLE = True
except ImportError:
    _TELEGRAM_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("watchman")

# ────────────────────────────────────────────────────────────────────────────
# CONFIG
# ────────────────────────────────────────────────────────────────────────────

IMAP_HOST       = "imap.gmail.com"
POLL_INTERVAL   = 30          # seconds between checks
RISK_THRESHOLD  = int(os.getenv("RISK_THRESHOLD", "5"))
LOG_CSV         = Path("guardian_logs.csv")
LOG_FIELDS      = [
    "timestamp", "sender", "subject",
    "matched_pattern", "category", "similarity_score",
    "risk_score", "danger_level", "scam_type", "flagged",
]


# ────────────────────────────────────────────────────────────────────────────
# EMAIL HELPERS
# ────────────────────────────────────────────────────────────────────────────

def _safe_decode(raw: bytes | str, charset: Optional[str]) -> str:
    """Decode bytes to str, trying charset then utf-8 then latin-1."""
    if isinstance(raw, str):
        return raw
    for enc in [charset, "utf-8", "latin-1"]:
        if enc:
            try:
                return raw.decode(enc)
            except (UnicodeDecodeError, LookupError):
                continue
    return raw.decode("latin-1", errors="replace")


def _decode_header_value(value: str) -> str:
    """Decode encoded email header (handles =?utf-8?b?...?= etc.)."""
    parts = decode_header(value or "")
    decoded = []
    for raw, charset in parts:
        if isinstance(raw, bytes):
            decoded.append(_safe_decode(raw, charset))
        else:
            decoded.append(raw)
    return "".join(decoded)


def _extract_body(msg: email.message.Message) -> str:
    """Walk MIME parts and extract all text/plain content."""
    body_parts: list[str] = []

    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            cd = str(part.get("Content-Disposition", ""))
            if ct == "text/plain" and "attachment" not in cd:
                payload = part.get_payload(decode=True)
                charset  = part.get_content_charset()
                body_parts.append(_safe_decode(payload, charset))
    else:
        payload = msg.get_payload(decode=True)
        charset = msg.get_content_charset()
        if payload:
            body_parts.append(_safe_decode(payload, charset))

    return "\n".join(body_parts).strip()


# ────────────────────────────────────────────────────────────────────────────
# IMAP POLLING
# ────────────────────────────────────────────────────────────────────────────

def _fetch_unseen_emails() -> list[dict]:
    """Connect to Gmail IMAP and return list of unseen email dicts."""
    address  = os.environ["GMAIL_ADDRESS"]
    app_pass = os.environ["GMAIL_APP_PASS"]

    emails: list[dict] = []
    try:
        mail = imaplib.IMAP4_SSL(IMAP_HOST)
        mail.login(address, app_pass)
        mail.select("inbox")

        _, msg_ids = mail.search(None, "UNSEEN")
        for uid in (msg_ids[0].split() if msg_ids[0] else []):
            _, data = mail.fetch(uid, "(RFC822)")
            raw = data[0][1]
            msg = email.message_from_bytes(raw)

            emails.append({
                "uid":     uid.decode(),
                "sender":  _decode_header_value(msg.get("From", "")),
                "subject": _decode_header_value(msg.get("Subject", "(no subject)")),
                "body":    _extract_body(msg),
            })

        mail.logout()
    except Exception as exc:
        logger.error("IMAP error: %s", exc)

    return emails


# ────────────────────────────────────────────────────────────────────────────
# LOGGING
# ────────────────────────────────────────────────────────────────────────────

def _init_csv() -> None:
    if not LOG_CSV.exists():
        with LOG_CSV.open("w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=LOG_FIELDS).writeheader()
        logger.info("Created %s", LOG_CSV)


def _log_result(em: dict, result: AnalysisResult) -> None:
    row = {
        "timestamp":       datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sender":          em["sender"][:60],
        "subject":         em["subject"][:80],
        **result.to_log_row(),
    }
    with LOG_CSV.open("a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=LOG_FIELDS).writerow(row)

    # Also dump full JSON result to a rotating JSONL file for the dashboard
    with open("guardian_logs.jsonl", "a", encoding="utf-8") as f:
        record = {"timestamp": row["timestamp"], "email_meta": {
            "sender": em["sender"], "subject": em["subject"]
        }, **result.to_dict()}
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ────────────────────────────────────────────────────────────────────────────
# TELEGRAM ALERTING
# ────────────────────────────────────────────────────────────────────────────

async def _send_telegram_alert(em: dict, result: AnalysisResult) -> None:
    if not _TELEGRAM_AVAILABLE:
        return
    token   = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not (token and chat_id):
        return

    danger_emoji = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}.get(
        result.danger_level, "⚪"
    )

    text = (
        f"{danger_emoji} *SURAKSHA SAATHI ALERT*\n\n"
        f"*From:* {em['sender'][:50]}\n"
        f"*Subject:* {em['subject'][:60]}\n\n"
        f"*Scam Type:* {result.scam_type}\n"
        f"*Danger Level:* {result.danger_level}\n"
        f"*Similarity:* {result.similarity_score:.0%}\n\n"
        f"*🏡 Hinglish Advice:*\n{result.hinglish_advice}\n\n"
        f"*✅ Safe Action:* {result.safe_action}"
    )

    try:
        bot = telegram.Bot(token=token)
        await bot.send_message(
            chat_id=chat_id, text=text, parse_mode="Markdown"
        )
        logger.info("Telegram alert sent.")
    except Exception as exc:
        logger.error("Telegram send failed: %s", exc)


# ────────────────────────────────────────────────────────────────────────────
# MAIN LOOP
# ────────────────────────────────────────────────────────────────────────────

async def process_email(em: dict) -> None:
    """Full pipeline for a single email."""
    body = em["body"]
    if not body.strip():
        logger.info("Skipping empty email from %s", em["sender"])
        return

    logger.info("Processing email — Subject: %s", em["subject"][:60])

    # Layer 2: Similarity Match
    match, score = find_context_match(body)
    logger.info("Match: %s  Score: %.0f%%", match["pattern"], score * 100)

    # Layer 3: AI Analysis
    result = await analyze_async(body, match, score, RISK_THRESHOLD, language="en")

    # Log always
    _log_result(em, result)

    # Alert only if flagged
    if result.flagged:
        logger.warning(
            "🚨 FLAGGED — %s [%s] from %s",
            result.danger_level, result.scam_type, em["sender"]
        )
        await _send_telegram_alert(em, result)
    else:
        logger.info("✅ Clean — danger=%s", result.danger_level)


async def monitor_loop() -> None:
    """Infinite polling loop."""
    _init_csv()
    logger.info("👁️  Watchman started — polling inbox every %ds", POLL_INTERVAL)

    while True:
        emails = _fetch_unseen_emails()
        if emails:
            logger.info("Found %d unseen email(s).", len(emails))
            tasks = [process_email(em) for em in emails]
            await asyncio.gather(*tasks)
        else:
            logger.debug("Inbox clear.")
        await asyncio.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    # Validate required env vars before starting
    missing = [v for v in ("GMAIL_ADDRESS", "GMAIL_APP_PASS", "GEMINI_API_KEY")
               if not os.getenv(v)]
    if missing:
        raise SystemExit(f"Missing environment variables: {', '.join(missing)}")

    asyncio.run(monitor_loop())
