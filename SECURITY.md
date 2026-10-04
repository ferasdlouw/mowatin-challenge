# Security policy

## Reporting a vulnerability
Please report privately through GitHub: **Security → Report a vulnerability** on this repository (private vulnerability reporting). Do not open a public issue, pull request or discussion for a security problem.

Include what you found, how to reproduce it (a request body or steps), and the impact you expect. Please do not include real personal data or API keys.

## Scope
In scope:
- The API in `backend/` (`POST /v1/translate`, `GET /v1/glossary`, `GET /health`) and its deployment config (`render.yaml`).
- The web app in `frontend/` (deployed to `mowatin.pages.dev`).
- The CI workflow and committed agent configuration (`.github/`, `.claude/`, `.agent/`).
- Safety controls: Quran text never machine-translated, fatwa questions referred, unsourced hadith never presented as authentic, prompt injection.

Out of scope: denial of service by volume (please describe the issue instead of load-testing the live instance; it runs on a free tier), third-party services (Google AI Studio, OpenRouter, Render, Cloudflare), and findings that need a compromised device.

## What to expect
- This is a competition project run by volunteers; there is **no bug bounty**.
- We aim to acknowledge a report within 3 days and to share a fix or a decision within 14 days.
- We credit reporters in the fix commit unless you ask us not to.

## Design notes
The threat model, audit and secure-change checklist live in [`docs/security/`](docs/security/).
