# Session Memory

Last updated: 2026-05-13

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

## Current Product Shape (as of 2026-05-13)

The app has been rebuilt into a **Tinder-style swipe PWA**. The entire frontend is now the swipe UI — no complex desktop interface.

### How the app works now

- `/` and `/swipe` both serve the swipe card UI (PWA, add to iPhone home screen)
- Cards show: gradient company avatar, job title, company, location chip, remote/hybrid/onsite chip, score chip, scrollable description (up to 2500 chars)
- Swipe right → shortlists the job + shows "Apply Now / Later" bottom sheet
- Swipe left → permanently rejects the job (never resurfaces)
- "Apply Now" → opens job URL directly in browser
- "Later" → saves to queue for later
- The discovery scheduler runs automatically in the background
- `/manifest.json` — PWA manifest for "Add to Home Screen" on iPhone

### Access

- Phone accesses the app via local network (Phillip shares the Mac's IP link to his phone)
- Mac must be on and running `python3 app.py`
- PWA added to iPhone home screen — looks and feels like a native app

### UI features

- Dark background (#0D0D0D), white cards with deep shadows
- Gradient avatar per company (deterministic colour by name)
- Score stripe across card top (green/amber/purple)
- LIKE/NOPE stamps appear progressively as you drag
- Springy snap-back animation on release
- Apply sheet with frosted backdrop after liking
- Description scrollable inside card without triggering swipe
- Action buttons: ✕ (red glow), ↗ (open URL), ♥ (green glow)

## Implemented System Capabilities

### Discovery and sourcing

- Public/compliant job discovery from:
  - Greenhouse, Lever, Ashby, SmartRecruiters, Recruitee, Workable, Teamtailor
  - Jobicy RSS (verified working), Indeed RSS (blocked), WeWorkRemotely RSS (blocked)
  - Remotive, Arbeitnow, Remote OK (disabled)
  - Adzuna SA API (implemented, needs API keys in `.env`)
  - Direct URL, Public careers page
- Strict upstream filtering — non-marketing, medical, and senior titles filtered
- Rejected jobs permanently suppressed — never resurface from any source

### Queue and application workflow

- Swipe right → status = 'shortlisted'
- Swipe left → status = 'rejected' with reason 'swiped left'
- Application drafts tracked in SQLite
- Follow-up emails generated at 7 days, manually sent

## Deployment Config

- `railway.toml` — Railway deployment config (start command: `python app.py`)
- `requirements.txt` — standard library only, no pip deps
- `.env.example` — template for environment variables
- `HOST` defaults to `0.0.0.0` (env var override available)
- `PORT` reads from `PORT` env var (Railway) or `JOB_AI_PORT` (local)
- `JOB_AI_PASSWORD` env var adds HTTP Basic Auth for online deployment
- `JOB_AI_CV_PATH` env var makes CV path configurable

## Current Operational State

As of 2026-05-13:
- Server runs on `http://127.0.0.1:8765`
- 80 jobs in swipe queue (from last check)
- Swipe UI is the only frontend — `/` serves the swipe page
- PWA installable on iPhone via Safari → Share → Add to Home Screen

## Known Gaps / Next Recommended Work

1. **Better job discovery** — current sources not finding the best Cape Town / remote marketing roles for a grad. Phillip mentioned this explicitly.
2. **Get Adzuna API keys** (free at developer.adzuna.com) — add `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` to `.env` for SA-specific Cape Town listings
3. **Source quality audit** — 27 sources had errors on last run (404s, 403s). Remove dead ones, add better ones.
4. **Smarter scoring** — score should weight Cape Town location and junior/grad titles more heavily
5. **Platform adapters** — SmartRecruiters, custom forms still need improvement
6. **Learning from swipe lefts** — rejection reasons from swiping should feed back into sourcing

## Git / State Handoff

- Latest commit: `2a312ad` — Complete swipe UI redesign
- All changes committed and pushed to GitHub
- Server was running at end of session — may need restart next session
