"""
bot.py
──────
Suraksha Saathi — Telegram Bot  (@Suraksha_rakshak_bot)

Features:
  • Language selector on /start  (English / Hindi / Hinglish)
  • Language preference persisted per-user via bot_data
  • All reports, prompts and advice auto-switch to selected language
  • Dataset advice fields (advice_en / advice_hi / advice_hng) used directly
  • Gemini AI generates deep-analysis advice in the chosen language

Commands:
    /start   — welcome + language picker
    /lang    — change language any time
    /check   — check a message
    /stats   — today's detection stats
    /help    — command list

Environment variables:
    TELEGRAM_BOT_TOKEN  — bot token
    GEMINI_API_KEY      — Google AI key
    RISK_THRESHOLD      — optional, default 5
"""

from __future__ import annotations

import os
import csv
import logging
from datetime import date
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters,
)

from context.matcher import find_context_match
from engine import analyze, AnalysisResult

logging.basicConfig(
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("bot")

RISK_THRESHOLD = int(os.getenv("RISK_THRESHOLD", "5"))
LOG_CSV        = Path("guardian_logs.csv")

DANGER_EMOJI = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}

# ── Supported languages ──────────────────────────────────────────────────────
LANGUAGES = {
    "en":  "🇬🇧 English",
    "hi":  "🇮🇳 Hindi",
    "hng": "🤝 Hinglish",
}

# advice field key per language code
ADVICE_KEY = {
    "en":  "advice_en",
    "hi":  "advice_hi",
    "hng": "advice_hng",
}

# ── UI strings per language ──────────────────────────────────────────────────
UI = {
    "en": {
        "welcome": (
            "🛡️ *Suraksha Saathi* — Your AI Scam Guard\n\n"
            "Forward me any suspicious message, email or SMS and I will tell you "
            "if it's a scam!\n\n"
            "Commands:\n"
            "  /check `<message>` — analyse a message\n"
            "  /lang — change language\n"
            "  /stats — today's summary\n"
            "  /help — all commands"
        ),
        "choose_lang":    "🌐 Choose your preferred language:",
        "lang_set":       "✅ Language set to *English*. Send me any suspicious message!",
        "analysing":      "⚙️ Analysing… please wait.",
        "no_text":        "Please send me a text message to analyse.",
        "check_usage":    "Usage: /check `<suspicious message>`\n\nOr just forward any message directly!",
        "no_logs":        "No logs yet — no messages have been checked today.",
        "report_title":   "SURAKSHA SAATHI REPORT",
        "danger_label":   "Danger Level",
        "scam_label":     "Scam Type",
        "similarity":     "Similarity Match",
        "tactics":        "Psychological Tactics Detected",
        "analysis":       "Analysis",
        "advice_label":   "💡 Safety Advice",
        "safe_action":    "✅ Safe Action",
        "footer":         "_Report by Suraksha Saathi · Powered by Gemini_",
        "stats_title":    "📊 Today's Stats",
        "stats_analysed": "Messages Analysed",
        "stats_flagged":  "🚨 Flagged",
        "stats_critical": "🔴 Critical",
        "stats_clean":    "✅ Clean",
        "help_text": (
            "*Suraksha Saathi Commands*\n\n"
            "/start — welcome\n"
            "/check `<message>` — analyse a message\n"
            "/lang — change language\n"
            "/stats — today's detection stats\n"
            "/help — this menu\n\n"
            "You can also just *forward any suspicious message* directly!"
        ),
    },
    "hi": {
        "welcome": (
            "🛡️ *सुरक्षा साथी* — आपका AI स्कैम गार्ड\n\n"
            "कोई भी संदिग्ध मैसेज, ईमेल या SMS मुझे भेजें और मैं बताऊंगा "
            "कि यह स्कैम है या नहीं!\n\n"
            "कमांड:\n"
            "  /check `<मैसेज>` — मैसेज जाँचें\n"
            "  /lang — भाषा बदलें\n"
            "  /stats — आज का सारांश\n"
            "  /help — सभी कमांड"
        ),
        "choose_lang":    "🌐 अपनी पसंदीदा भाषा चुनें:",
        "lang_set":       "✅ भाषा *हिंदी* सेट की गई। कोई भी संदिग्ध मैसेज भेजें!",
        "analysing":      "⚙️ जाँच हो रही है… कृपया प्रतीक्षा करें।",
        "no_text":        "कृपया जाँचने के लिए एक टेक्स्ट मैसेज भेजें।",
        "check_usage":    "उपयोग: /check `<संदिग्ध मैसेज>`\n\nया सीधे कोई भी मैसेज फॉरवर्ड करें!",
        "no_logs":        "अभी तक कोई लॉग नहीं — आज कोई मैसेज जाँचा नहीं गया।",
        "report_title":   "सुरक्षा साथी रिपोर्ट",
        "danger_label":   "खतरा स्तर",
        "scam_label":     "स्कैम प्रकार",
        "similarity":     "मिलान स्कोर",
        "tactics":        "पहचाने गए मनोवैज्ञानिक हथकंडे",
        "analysis":       "विश्लेषण",
        "advice_label":   "💡 सुरक्षा सलाह",
        "safe_action":    "✅ अभी क्या करें",
        "footer":         "_रिपोर्ट: सुरक्षा साथी · Gemini द्वारा संचालित_",
        "stats_title":    "📊 आज के आँकड़े",
        "stats_analysed": "जाँचे गए मैसेज",
        "stats_flagged":  "🚨 संदिग्ध",
        "stats_critical": "🔴 अति खतरनाक",
        "stats_clean":    "✅ सुरक्षित",
        "help_text": (
            "*सुरक्षा साथी कमांड*\n\n"
            "/start — स्वागत\n"
            "/check `<मैसेज>` — मैसेज जाँचें\n"
            "/lang — भाषा बदलें\n"
            "/stats — आज के आँकड़े\n"
            "/help — यह मेनू\n\n"
            "आप सीधे कोई भी *संदिग्ध मैसेज फॉरवर्ड* भी कर सकते हैं!"
        ),
    },
    "hng": {
        "welcome": (
            "🛡️ *Suraksha Saathi* — Aapka AI Scam Guard\n\n"
            "Koi bhi suspicious message, email ya SMS bhejiye — main bataunga "
            "scam hai ya nahi, seedhi Hinglish mein!\n\n"
            "Commands:\n"
            "  /check `<message>` — message check karo\n"
            "  /lang — language badlo\n"
            "  /stats — aaj ka summary\n"
            "  /help — saare commands"
        ),
        "choose_lang":    "🌐 Apni pasand ki bhasha chuniye:",
        "lang_set":       "✅ Bhasha *Hinglish* set ho gayi! Koi bhi suspicious message bhejiye!",
        "analysing":      "⚙️ Check ho raha hai… thoda ruko.",
        "no_text":        "Bhai, check karne ke liye koi text message bhejo!",
        "check_usage":    "Aise use karo: /check `<suspicious message>`\n\nYa seedha koi message forward karo!",
        "no_logs":        "Abhi tak koi log nahi — aaj koi message check nahi hua.",
        "report_title":   "SURAKSHA SAATHI REPORT",
        "danger_label":   "Khatara Level",
        "scam_label":     "Scam Type",
        "similarity":     "Match Score",
        "tactics":        "Psychological Tactics Pakde Gaye",
        "analysis":       "Analysis",
        "advice_label":   "💡 Dadi/Nana Style Salah",
        "safe_action":    "✅ Abhi Kya Karein",
        "footer":         "_Report: Suraksha Saathi · Gemini se powered_",
        "stats_title":    "📊 Aaj ke Stats",
        "stats_analysed": "Messages Check Kiye",
        "stats_flagged":  "🚨 Suspicious",
        "stats_critical": "🔴 Bahut Khatarnak",
        "stats_clean":    "✅ Safe",
        "help_text": (
            "*Suraksha Saathi Commands*\n\n"
            "/start — welcome\n"
            "/check `<message>` — message check karo\n"
            "/lang — language badlo\n"
            "/stats — aaj ke stats\n"
            "/help — ye menu\n\n"
            "Seedha koi bhi *suspicious message forward* kar sakte ho!"
        ),
    },
}


# ────────────────────────────────────────────────────────────────────────────
# HELPERS
# ────────────────────────────────────────────────────────────────────────────

def get_lang(ctx: ContextTypes.DEFAULT_TYPE) -> str:
    """Return current language for this user (default: hng). Falls back to hng for unknown codes."""
    lang = ctx.user_data.get("lang", "hng")
    return lang if lang in UI else "hng"


def ui(ctx: ContextTypes.DEFAULT_TYPE, key: str) -> str:
    return UI[get_lang(ctx)][key]


def language_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(label, callback_data=f"lang:{code}")
        for code, label in LANGUAGES.items()
    ]
    return InlineKeyboardMarkup([buttons])


def get_dataset_advice(match: dict, lang: str) -> str:
    """Pull the pre-written advice from the dataset in the right language."""
    key = ADVICE_KEY.get(lang, "advice_hng")
    return match.get(key, match.get("advice_hng", ""))


# ────────────────────────────────────────────────────────────────────────────
# REPORT FORMATTER  (language-aware)
# ────────────────────────────────────────────────────────────────────────────

def _format_report(result: AnalysisResult, match: dict, lang: str) -> str:
    t         = UI[lang]
    emoji     = DANGER_EMOJI.get(result.danger_level, "⚪")
    tactics   = " • ".join(result.psychological_tactics) if result.psychological_tactics else "—"
    score_bar = "█" * int(result.similarity_score * 10) + "░" * (10 - int(result.similarity_score * 10))

    # Use dataset advice if AI didn't produce language-specific output
    advice = result.hinglish_advice or get_dataset_advice(match, lang)

    return (
        f"{emoji} *{t['report_title']}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"*{t['danger_label']}:* `{result.danger_level}`\n"
        f"*{t['scam_label']}:*   {result.scam_type or result.matched_pattern}\n\n"
        f"*{t['similarity']}*\n"
        f"`{score_bar}` {result.similarity_score:.0%}\n"
        f"Pattern: _{result.matched_pattern}_\n\n"
        f"*{t['tactics']}*\n"
        f"{tactics}\n\n"
        f"*{t['analysis']}*\n"
        f"{result.reasoning}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{t['advice_label']}\n"
        f"_{advice}_\n\n"
        f"{t['safe_action']}\n"
        f"{result.safe_action}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{t['footer']}"
    )


def _format_error(err: str) -> str:
    return f"⚠️ *Analysis Error*\n\n`{err}`\n\nPlease try again or check the logs."


# ────────────────────────────────────────────────────────────────────────────
# COMMAND HANDLERS
# ────────────────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        ui(ctx, "welcome"),
        parse_mode="Markdown",
        reply_markup=language_keyboard(),
    )


async def cmd_lang(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        ui(ctx, "choose_lang"),
        parse_mode="Markdown",
        reply_markup=language_keyboard(),
    )


async def callback_lang(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Inline keyboard callback — user chose a language."""
    query = update.callback_query
    await query.answer()

    _, code = query.data.split(":")
    ctx.user_data["lang"] = code

    await query.edit_message_text(
        UI[code]["lang_set"],
        parse_mode="Markdown",
    )


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(ui(ctx, "help_text"), parse_mode="Markdown")


async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not LOG_CSV.exists():
        await update.message.reply_text(ui(ctx, "no_logs"))
        return

    t     = UI[get_lang(ctx)]
    today = date.today().strftime("%Y-%m-%d")
    total = flagged = critical = 0

    with LOG_CSV.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("timestamp", "").startswith(today):
                total += 1
                if row.get("flagged") == "True":
                    flagged += 1
                if row.get("danger_level") == "CRITICAL":
                    critical += 1

    await update.message.reply_text(
        f"📊 *{t['stats_title']} — {today}*\n\n"
        f"{t['stats_analysed']} : {total}\n"
        f"{t['stats_flagged']}       : {flagged}\n"
        f"{t['stats_critical']}      : {critical}\n"
        f"{t['stats_clean']}         : {total - flagged}",
        parse_mode="Markdown",
    )


# ────────────────────────────────────────────────────────────────────────────
# CORE ANALYSIS
# ────────────────────────────────────────────────────────────────────────────

async def analyse_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    lang = get_lang(ctx)
    await update.message.reply_text(ui(ctx, "analysing"), parse_mode="Markdown")

    try:
        match, score = find_context_match(text)
        result = analyze(text, match, score, RISK_THRESHOLD, language=lang)

        if result.error and not result.scam_type:
            await update.message.reply_text(_format_error(result.error), parse_mode="Markdown")
        else:
            await update.message.reply_text(
                _format_report(result, match, lang),
                parse_mode="Markdown",
            )
    except Exception as exc:
        logger.exception("Unhandled error during analysis")
        await update.message.reply_text(_format_error(str(exc)), parse_mode="Markdown")


async def cmd_check(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    text = " ".join(ctx.args).strip() if ctx.args else ""
    if not text:
        await update.message.reply_text(ui(ctx, "check_usage"), parse_mode="Markdown")
        return
    await analyse_message(update, ctx, text)


async def handle_forwarded(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text or update.message.caption or ""
    if not text.strip():
        await update.message.reply_text(ui(ctx, "no_text"))
        return
    await analyse_message(update, ctx, text)


# ────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ────────────────────────────────────────────────────────────────────────────

def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN not set.")

    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("lang",   cmd_lang))
    app.add_handler(CommandHandler("help",   cmd_help))
    app.add_handler(CommandHandler("stats",  cmd_stats))
    app.add_handler(CommandHandler("check",  cmd_check))
    app.add_handler(CallbackQueryHandler(callback_lang, pattern=r"^lang:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_forwarded))

    logger.info("🤖 @Suraksha_rakshak_bot started. Waiting for messages…")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
