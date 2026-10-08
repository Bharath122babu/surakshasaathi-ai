# SurakshaSaathi-AI · Python backend

The complete setup, feature inventory, privacy notes and demo walkthrough live in the [root README](../README.md).

Run from this directory so `.env` and monitor logs resolve consistently:

```powershell
..\.venv\Scripts\python.exe api.py
```

The default local endpoint is `http://127.0.0.1:8000`; API documentation is at `/docs`. Manual analysis is `POST /analyze`. Email-monitor logs are read through `/logs`, `/stats` is a library self-check plus log summary, `/knowledge-base` searches the curated entries, and `/health` reports configuration.

See [the source review](../docs/REVIEW.md) before public hosting or publication.
