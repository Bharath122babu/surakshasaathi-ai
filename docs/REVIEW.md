# Source review · SurakshaSaathi-AI

Reviewed from `SurakshaSaathi_AI_GitHub_Final.zip`, 9 October 2026.

## What was read

All executable source files in the ZIP: the FastAPI routes, Gemini engine, matcher, 40-entry library, compatibility shim, Gmail monitor, Telegram bot, Streamlit interface, React dashboard, frontend configuration, environment template, and existing documentation. Lockfiles were checked for package context; image assets were not treated as instructions. The legacy JSX snapshot exactly matched the runnable React source in the supplied archive.

## Changes in the prepared package

| Finding in the original | Change |
| --- | --- |
| Hardcoded bot credential overrode the environment | Removed it; bot reads `TELEGRAM_BOT_TOKEN` only |
| Root ignore rule hid `.env.example` | Added an exception; both templates can be committed |
| Logs contained message metadata | Runtime CSV/JSONL files excluded from the release archive and Git |
| TF-IDF score multiplied by 3.8 and given a 0.15 floor | Return raw cosine similarity; use one corpus IDF basis for reference and query |
| ASCII-only tokenization discarded Hindi input | Retain Unicode word tokens; language quality is still unevaluated |
| Embedding score remapped upward | Return bounded raw cosine similarity |
| Library shortcut ignored requested flag threshold and used Hinglish advice | Honour the threshold and requested advice language |
| Model and library outputs looked interchangeable | Return `analysis_source` and label it in the dashboard |
| `+37` inflated the detection count | Report actual flagged log entries |
| Streamlit showed a fixed `98.4%` accuracy | Removed the invented figure and marked detection accuracy unevaluated |
| Self-retrieval labelled as accuracy | Relabelled it as a library self-check |
| FastAPI accepted every web origin and bound all interfaces by default | Localhost binding and configurable frontend origins |
| Vite template CSS imposed a centred 1126px root on a sidebar app | Replaced that baseline and added mobile sidebar behaviour |
| Frontend dependencies had 10 reported vulnerabilities | Applied compatible package updates; npm audit reports zero |
| Language settings were flag-only buttons | Visible language names and accessible labels |
| Duplicate dashboard snapshot obscured the runnable source | Removed the duplicate; preserve the original in the supplied ZIP |
| Streamlit accessed a nonexistent `hinglish_hook` key | Fall back to the actual advice field |
| Streamlit language selection was not passed to the engine | Pass the chosen language |
| README instructions and model names differed from the code | Accurate paths, configuration table, demo sequence and limitations |

These are release-preparation corrections, not a claim that the prototype is production-ready.

## Remaining work

1. **Token rotation.** Revoke the token in the original ZIP through BotFather before using the bot again. The original archive is preserved and still contains it; do not publish that archive. The reviewed source and archive contain no embedded token.
2. **Attribution.** At Bharath's request, no teammate names or tags are included. The README highlights his team-lead/backend role without claiming sole authorship of the complete project.
3. **Independent evaluation.** The library has 40 scam references and no representative benign set. Self-retrieval cannot measure real detection, false positives or language performance.
4. **Corpus quality.** Several advice strings contain absolute institutional/domain claims. Review them against authoritative sources and soften unsupported assertions before using the product with real users. No facts in the corpus were independently validated in this code review.
5. **Cloud model access.** The supplied default identifiers remain configurable. Provider availability, cost, latency and quota were not exercised.
6. **Monitor reliability.** IMAP fetch can mark mail read before successful analysis, lacks durable UID tracking, and uses a blocking fetch in an async loop. Add processing acknowledgements and retry behaviour before relying on it.
7. **Bot behaviour.** Analysis is synchronous inside a bot handler; language settings reset on restart. `/stats` reads email-monitor logs; bot checks are not logged there. Markdown output is not escaped for arbitrary model text.
8. **Local logging.** Concurrent email tasks append to local files without a shared lock; there is no retention policy or user-level isolation. Manual HTTP checks do not populate the email feed.
9. **Public hosting.** No authentication, per-user ownership, rate limiting or abuse controls are implemented. CORS is not authentication. The portfolio case study can be public; this backend should remain a controlled local demo.
10. **Streamlit.** The inherited auto-refresh reruns rapidly rather than using its labelled 10-second interval. Treat React as the main demo and improve the alternate view separately.
11. **Assets and license.** Confirm ownership of the supplied icons/artwork and agree on a repository license with the team before publication.

## Validation scope

| Check | Result |
| --- | --- |
| Offline Python regression suite | 9 tests pass, including all 40 reference self-matches |
| Frontend ESLint | Pass |
| Frontend production build | Pass, Vite 8.3.4 |
| Frontend dependency audit | 0 reported vulnerabilities at review time |
| Exact-library HTTP demo | Similarity 1.0; response source `knowledge_base`; no model call |
| Browser demo | Analysis, library search/expansion, empty monitor feed and mobile layout pass; no page errors |
| Portfolio | Lint/build pass; 5 browser checks pass across desktop/mobile, accessibility, motion, recovery and direct case-study links |

The screenshot was captured from the reviewed source using a synthetic reference entry. No requests were made to Gemini, Gmail or Telegram and no messages were sent. The Streamlit and Telegram integrations were read and syntax-checked, but not run end to end. An audit result is a point-in-time dependency check, not a production security assessment.
