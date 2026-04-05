# AI-Powered Code Review Copilot

Prototype monorepo for a GitHub repository review assistant built with FastAPI and React + Tailwind.

## What it does

- Accepts a public GitHub repository URL
- Clones or downloads the repository contents
- Builds a Python-first structural map with `ast`
- Runs `pylint`, `bandit`, and local heuristics for bugs, security issues, code smells, and performance risks
- Normalizes findings into a structured JSON report with severity, file path, symbol, and line numbers
- Enriches findings with rule-specific suggestions and generated `fix_patch` values, with optional OpenAI refinement when `OPENAI_API_KEY` and `OPENAI_MODEL` are configured
- Applies inline fixes back into the cloned repository for supported findings
- Packages applied fixes into a local patch file or a best-effort pull request flow when GitHub credentials are available
- Displays results in a modern single-page React dashboard

## Backend

```bash
cd backend
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend endpoints:

- `POST /api/analyses`
- `GET /api/analyses/{run_id}`
- `GET /api/analyses/{run_id}/report`
- `POST /api/apply-fix`
- `POST /api/create-pr`
- `GET /api/health`

Environment variables:

- `OPENAI_API_KEY` optional
- `OPENAI_MODEL` optional
- `GITHUB_TOKEN` optional
- `GITHUB_USERNAME` optional
- `GITHUB_API_URL` optional, defaults to `https://api.github.com`
- `ALLOWED_ORIGINS` optional comma-separated CORS origins

## Frontend

```bash
cd frontend
npm install
npm run dev
```

Optional environment variable:

- `VITE_API_BASE_URL` defaults to `http://localhost:8000`

## Notes

- The prototype deeply analyzes Python files and summarizes other detected languages.
- Repository runs are stored on disk under `data/runs/`.
- Git is preferred for ingestion, with a public GitHub archive fallback when `git` is not available on `PATH`.
- Pull request creation is best-effort. When the cloned repository is not a writable git checkout, the backend falls back to generating a patch file under the run artifacts directory.
