# Security finding suppressions

Every finding a gate does not fail on is listed here with its reason, owner and review date. Adding a line needs the approver's OK (the human running the session).

| Finding | Where | Why it is not a gate failure | Exit plan | Approved by | Review by |
|---|---|---|---|---|---|
| npm audit: 5 high (`braces` via `micromatch`, `chokidar`, `fast-glob` ← `tailwindcss` 3) | `frontend/package.json` devDependencies | Build-time only: none of these packages reaches the browser bundle. CI gates `npm audit --omit=dev --audit-level=high` (runtime deps, 0 findings on 2026-10-03). The fix is `tailwindcss` 4, a major upgrade | Eng. Feras decides on tailwind 4 (dependency change); Dependabot shows the update | the session's human (Phase SEC, 2026-10-03) | 2026-11-01 |
