# Agent Instructions

## Session Memory

At the start of any new work session in this project, read `SESSION_MEMORY.md` before making plans or edits. Treat it as the durable handoff for what Phillip is building, what is already implemented, what decisions have been made, and what should happen next.

When Phillip says `end session`, update `SESSION_MEMORY.md` before replying. The update should:

- Replace stale project status with the latest completed work.
- Record important decisions, credentials status without exposing secrets, blockers, and next recommended actions.
- Keep enough detail for a future session to continue without re-asking known context.
- Never include passwords, SMTP secrets, API keys, cookies, or private tokens.

If `SESSION_MEMORY.md` is missing, create it from the current project state and conversation context.

## Project Guardrails

This is a local, review-first job application assistant. It may discover jobs from compliant public sources, score roles, draft cover letters and answers, prepare form filling, track applications, and schedule follow-ups.

Do not implement CAPTCHA bypass, MFA bypass, anti-bot evasion, fake accounts, hidden scraping, or automated final submission. LinkedIn and Indeed should remain guided/manual unless Phillip has explicit permission or official API access.

Cold outreach must remain personalized, reviewed by Phillip, and sent only after an explicit click. Respect do-not-contact and suppression rules.
