# SurakshaSaathi-AI · React dashboard

The dashboard provides message analysis, an email-log feed and a searchable pattern library. See the [project README](../README.md) for the complete setup and score interpretation.

```powershell
npm ci
npm run dev -- --host 127.0.0.1
```

Open `http://127.0.0.1:5173` with the Python API running on `http://127.0.0.1:8000`. Override the backend with `VITE_API_URL` in your local `.env`, using the committed `.env.example` as a template.

```powershell
npm run lint
npm run build
```

The runnable source is `src/App.jsx`. The JSX file in `Singularity/` is an archived snapshot, not the frontend entry point.
