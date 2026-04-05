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

- `VITE_API_BASE_URL` defaults to `http://localhost:5173`

## Notes

- The prototype deeply analyzes Python files and summarizes other detected languages.
- Repository runs are stored on disk under `data/runs/`.
- Git is preferred for ingestion, with a public GitHub archive fallback when `git` is not available on `PATH`.
- Pull request creation is best-effort. When the cloned repository is not a writable git checkout, the backend falls back to generating a patch file under the run artifacts directory.


## Features

**1. Hero Section & Entry Point**

<img width="1891" height="685" alt="image" src="https://github.com/user-attachments/assets/043b97e9-ea7f-4354-a1db-d1bb38455cde" />


A clean interface where users can instantly understand the product’s purpose.

- Clear value proposition: “Understand your codebase. Fix issues instantly.”
- Direct repository input field for quick analysis
- Minimal, distraction-free UI focused on action
- Light/Dark mode support for better usability

<br>
<br>

**2. Analysis Pipeline Visualization**

<img width="1894" height="517" alt="image" src="https://github.com/user-attachments/assets/c9e6d51e-b77c-45b5-94d5-4700d98f255f" />


Real-time visibility into the internal processing pipeline:

- Repository cloning & indexing
- Code structure mapping
- Static analysis execution
- AI suggestion generation
- Report assembly

This gives users transparency into how the system works internally.

<br>
<br>

**3. Repository Health & Metrics Dashboard**

<img width="1895" height="556" alt="image" src="https://github.com/user-attachments/assets/2e21f262-5291-40de-b6ca-75468f93be6e" />


High-level insights into repository quality:

- Repository Health Score → overall maintainability indicator
- Total Findings → full issue count (no truncation)
- Hotspots → most problematic files
- Issue Groups → clustered patterns for faster fixes
- Language Breakdown → detected tech stack

<br>
<br>

**4. Findings Workspace (Core Engine)**

<img width="1892" height="853" alt="image" src="https://github.com/user-attachments/assets/9a86fa7f-53ad-4463-9bea-3a60b942c59f" />


The main workspace where developers interact with issues:

-	Advanced filtering (severity, impact, category, file) 
-	Search across issues, symbols, and rules 
-	Grouped vs raw findings view 
-	Large dataset virtualization (handles 1000+ issues smoothly) 
-	Batch actions like “Fix All High Issues” 

<br>
<br>

**5. Intelligent Issue Grouping**

<img width="1893" height="867" alt="image" src="https://github.com/user-attachments/assets/34d8f57f-8039-4369-b04e-9806e8a9a6f7" />


Instead of showing isolated issues, the system clusters repeated patterns:
-	Detects recurring problems across multiple files 
-	Shows a representative finding 
-	Provides a single actionable fix 
-	Reduces noise and speeds up remediation 

<br>
<br>

**6. Deep Issue Analysis Drawer**

<img width="1878" height="867" alt="image" src="https://github.com/user-attachments/assets/f3973a1f-bdd4-45b7-8b4f-13d5db9457eb" />


Each issue expands into a detailed breakdown:
-	Severity, impact, confidence scoring 
-	Exact file location and rule mapping 
-	Clear explanation of the issue 
-	Root cause analysis 
-	Business impact description 

<br>
<br>

**7. AI-Powered Fix Suggestions**

<img width="1873" height="326" alt="image" src="https://github.com/user-attachments/assets/2d6f0970-552c-435f-83c5-57298452f63e" />


Not just suggestions — actionable fixes:
-	Real command or patch (e.g., dependency fixes) 
-	Context-aware recommendations 
-	Designed for production usage, not generic advice 

<br>
<br>

**8. Code Context & Snippet View**

<img width="1869" height="420" alt="image" src="https://github.com/user-attachments/assets/c23d29eb-8493-4b91-a659-887fb4a001d8" />


Developers can see:
-	Exact code location of the issue 
-	Relevant snippet with context 
-	Helps validate and trust the fix 

<br>
<br>

**9. Action System (Fix & PR Flow)**

<img width="1880" height="867" alt="image" src="https://github.com/user-attachments/assets/f7da4d2e-702b-42ea-b630-a1f5a8b954a7" />


Built-in workflow to resolve issues:
-	Apply fixes inline 
-	Fix all issues in a file 
-	Fix grouped issues 
-	Create Pull Requests (when configured) 
