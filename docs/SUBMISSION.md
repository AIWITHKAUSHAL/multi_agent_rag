# Publishing the submission

The project is prepared locally. GitHub publication and YouTube recording/upload are separate steps that need your account and final content.

## Public GitHub repository

From this exact project directory, initialize an independent repository if it does not already have its own `.git` directory. This is especially important when a parent folder happens to be a Git repository.

```bash
git init -b main
git add .gitignore .dockerignore .env.example .python-version pyproject.toml uv.lock Makefile Dockerfile compose.yaml README.md app tests scripts examples evaluation docs .github
git diff --cached --stat
git diff --cached --name-only
```

Inspect the staged files. They must exclude `.env`, API keys, uploaded private documents, `data/`, `.venv/`, caches and unrelated parent files. Review trace exports for private content before adding any live report.

```bash
git commit -m "Build observable six-agent RAG classroom application"
gh repo create multi-agent-agentic-rag-classroom --public --source=. --remote=origin --push
```

The last command creates a public repository under your authenticated GitHub account. Choose the repository name and account intentionally; alternatively create the repository in GitHub's website and push to its URL. These publishing commands have not been run automatically.

## Test evidence

Run `uv run pytest -q`, then start the server and run `uv run python scripts/evaluate.py`. Review the full JSON and human-check source grounding. Add a sanitized result report under `docs/`; raw live reports remain ignored by default because traces include full uploaded passages. Preserve failed cases honestly and explain any fixes/re-runs.

## Video

Use `docs/VIDEO_SCRIPT.md`. Record your own architecture explanation and code walkthrough, then demonstrate upload, direct question, retrieval, calculation, multi-step reasoning, follow-up memory and failures live. Upload to YouTube with the visibility required by your course.

Add the real GitHub and YouTube links to README before submitting. The assignment deadline in the provided brief is 25 September 2026 at 17:58; this workspace was prepared after that date, so submission acceptance depends on your course's policy.
