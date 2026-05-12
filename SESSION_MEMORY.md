# Session Memory

Last updated: 2026-05-08

## Project Goal

Phillip is building a local, review-first job application assistant for early-career marketing roles. The app should discover suitable jobs, score them, generate tailored application material from his CV and profile, prepare live application forms for review, track follow-ups, and help produce about 5 strong applications per day.

The system may draft and prepare, but Phillip must review and manually submit or send.

## Current Local Setup

- Project path: `/Users/phillip/Desktop/JOB APPLICATION AI`
- Main app: `app.py`
- Local app URL in active use: `http://127.0.0.1:8765`
- Database: `data/job_application_ai.sqlite3`
- Documents/output folder: `documents/`
- Session memory file: `SESSION_MEMORY.md`
- LaunchAgent installed: `com.phillip.job-application-ai`
- SQLite backup created earlier: `data/backups/job_application_ai-20260428-093257.sqlite3`

## User Profile And Preferences

- Name: Phillip de Nobrega
- Location: `4 Hauptville Circle, Constantia, Cape Town, Western Cape, 7806, South Africa`
- Email: `Phillip2002@mweb.co.za`
- Phone: `+27 71 643 0185`
- LinkedIn: `linkedin.com/in/phillip-de-nobrega-87542b353`
- Citizenship/work status: South African plus UK passport/citizenship
- CV source: `/Users/phillip/Desktop/PHILLIP PERSONAL/Phillip_de_Nobrega_CV.pdf`
- Writing sample stored from: `/Users/phillip/Documents/Climate change in South Africa- mr weber (geo).docx`
- Headshot currently referenced from local file: `/Users/phillip/Desktop/PHILLIP PERSONAL/High_MountDA30443-062.jpg`
- Salary target: about `R22,000/month`
- Full-time availability: `2027-01-01`
- Trial/project availability until: `2026-06-12`

### Role preferences

- Target roles: graduate, junior, first-job, assistant, coordinator, associate, executive, specialist, content, brand, social media, growth, partnerships, community, campaign, PPC, SEO, CRM, lifecycle, copy/content writing, and digital media roles
- Avoid: manager, director, head, VP, leadership-heavy roles unless Phillip explicitly approves them
- Location rule: Cape Town / Western Cape for in-person or hybrid roles; otherwise role must be clearly remote
- Remote US/UK/Europe roles are acceptable when truly remote

### Communication preferences

- Follow-up emails are generated for submitted applications, due 7 days later, but sent only after Phillip reviews and clicks send
- Outreach must stay personalized and manually sent
- Writing should sound natural and local, not robotic or over-corporate

## Guardrails

- Do not automate final application submission
- Do not automate final outreach or follow-up sending
- Do not bypass CAPTCHA, MFA, anti-bot checks, rate limits, or platform restrictions
- LinkedIn and Indeed remain guided/manual unless official access exists
- Sensitive ATSs should be treated as manual-first and paced conservatively
- Never invent work authorization, salary, experience, or legal/compliance answers

## Current Product Shape

The app has been refactored into a tool-first workspace inspired by AIApply's structure, while staying local and review-first.

### Current top-level sections

- `Home`
- `Auto Apply Queue`
- `Resume Lab`
- `ATS Scanner`
- `Interview Prep`
- `Profile`
- `Discover`
- `Targets`
- `Jobs`
- `Applications`
- `Outreach`
- `Ops`
- `Analytics`
- `Email`
- `Session`

## Implemented System Capabilities

### Discovery and sourcing

- Public/compliant job discovery from:
  - Greenhouse
  - Lever
  - Ashby
  - SmartRecruiters
  - Recruitee
  - Direct URL
  - Remotive public API
  - Remote OK public API (disabled — requires account to apply)
  - Arbeitnow public API
  - Workable public
  - Teamtailor public
  - **Jobicy RSS** — verified working, no API key needed (`jobicy_rss` source type)
  - **Indeed RSS** — implemented, currently blocked by Indeed (returns 0 gracefully)
  - **WeWorkRemotely RSS** — implemented, currently blocked (returns 0 gracefully)
  - **Adzuna SA API** — implemented, needs `ADZUNA_APP_ID` + `ADZUNA_APP_KEY` in `.env` (free tier at developer.adzuna.com)
- Discovery defaults to a graduate-marketing query
- Strict upstream filtering — non-marketing, medical, and senior titles filtered before queue

### Rejected jobs — never resurface (fixed 2026-05-08)

- `upsert_job` now checks: if existing job by URL has `status='rejected'` → skip update entirely
- Before inserting a new job, checks `lower(title) + lower(company)` fingerprint — if a matching rejected job exists under a different URL/source, the insert is skipped
- This means: saying "No thanks" to a job permanently suppresses it, even if the same role comes in again from a different source

### New starter sources added (2026-05-08)

Go to **Discover → Add starter job sources** to seed them:
- Jobicy marketing RSS + Jobicy copywriting RSS
- CareerJunction all marketing (SA)
- PNet Cape Town marketing
- Careers24 marketing Cape Town
- WorkAfrica marketing Cape Town
- Takealot, Superbalist, Yoco, Peach Payments careers pages
- Buffer (Greenhouse), Mailchimp (Greenhouse), Hootsuite (Greenhouse), Sprout Social (Lever), Later (Lever), Canva (Greenhouse), Notion (Greenhouse)

### Source type dropdown reorganised

- **ATS boards**: Greenhouse, Lever, Ashby, SmartRecruiters, Recruitee, Workable, Teamtailor
- **Job board feeds**: Jobicy RSS, Remotive, Arbeitnow, Indeed RSS, WeWorkRemotely RSS, Adzuna SA, Remote OK
- **Careers pages**: Public careers page, Direct URL

### Queue and application workflow

- Application drafts tracked in SQLite with persistent `queue_state`: review / approved / hold
- Queue quick actions: Approve, Hold, Review, No thanks
- Queue batch actions: Approve safe roles, Hold blocked ATS, Reset queue to review
- `No thanks` stores `reject_reason` + `reject_notes`, reinforces learning

### Resume Lab, ATS Scanner, Form prep, Email/follow-up

(Unchanged from previous session — see prior entries)

## Current Operational State

As of 2026-05-08:
- Server runs on `http://127.0.0.1:8765`
- 42 starter sources seeded (up from 35)
- Jobicy RSS live-tested: found 2 matching marketing jobs on first run
- Rejection fix live-tested: re-running a source after rejecting a job leaves status unchanged

## Known Gaps / Next Recommended Work

1. Get Adzuna API keys (free at developer.adzuna.com) and add to `.env` as `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` — this will unlock SA-specific job discovery with real Cape Town listings
2. Run all sources and review the new Jobicy + SA careers page results
3. Review remaining active drafts and reject weak ones with real reasons
4. Keep improving platform adapters based on real failures (SmartRecruiters, custom forms)
5. Add stronger learning from `No thanks` reasons into future sourcing

## Git / State Handoff

- Latest confirmed commit before this session's changes: `f8dd848` `Update session memory — end of 2026-05-07 session 2`
- Changes in this session are in-memory only (app.py modified, server running with changes)
- Commit these changes before next session
