# Project map for coding agents

- Production runs on an Ubuntu VPS with `systemd`; GitHub Actions tests and deploys on pushes to `main`. Do not run a second polling instance with the production token.
- Runtime code: `bot.py`. Dependencies: `requirements.txt`. Deployment: `.github/workflows/tests.yml` and `deploy/`. Architecture: `docs/architecture.md`.
- Read only the files relevant to the requested change. Skip `.venv`, model caches, and Git history unless needed.
- Check changes with `.venv/bin/python -m unittest discover -s tests -q` and `git diff --check`.
- `.env` holds secrets and is ignored by Git. Never print or commit its values. The Whisper model cache stays on the VPS.
