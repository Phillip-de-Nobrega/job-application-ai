# Session Memory

Last updated: 2026-04-29

## Project Goal

Phillip is building a local, review-first job application assistant for early-career marketing roles. The app should discover suitable jobs, score them, generate tailored application material from his CV and profile, prepare live application forms for review, track follow-ups, and help produce about 5 strong applications per day.

The system may draft and prepare, but Phillip must review and manually submit or send.

## Current Local Setup

- Project path: `/Users/phillip/Desktop/JOB APPLICATION AI`
- Main app: `app.py`
- Local app URL in active use: `http://127.0.0.1:8766`
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
  - Remote OK public API
  - Arbeitnow public API
- Discovery now defaults to a graduate-marketing query instead of broad marketing terms
- Source records, Discover defaults, Targets defaults, and starter sources are normalized to this graduate-marketing query
- Upstream filtering is stricter so non-marketing, medical, and clearly senior titles are filtered before they pollute the queue

### Queue and application workflow

- Application drafts are tracked in SQLite
- Each application has persistent `queue_state`:
  - `review`
  - `approved`
  - `hold`
- `Auto Apply Queue` groups cards into:
  - Needs Review
  - Approved
  - On Hold
- Queue quick actions:
  - Approve
  - Hold
  - Review
  - No thanks
- Queue batch actions:
  - Approve safe roles
  - Hold blocked ATS roles
  - Reset queue to review
- `No thanks` now stores:
  - `reject_reason`
  - `reject_notes`
- Reject reasons reinforce learning:
  - `too senior` / `manager` reasons also reinforce `too_senior` on the linked job
- Current batch behavior is real, based on `batch_id`, not simple timestamp slicing

### Resume Lab

- CV version storage and management
- CV version editor
- Set default CV version
- Save new CV version
- Delete non-default CV version
- Generated Packs panel shows per-application artifacts in `documents/`
- CV metadata now includes file existence and file name
- Tailoring diff views show:
  - matched keywords
  - missing keywords
  - evidence to emphasize
  - top role keywords
  - recommended CV summary

### ATS Scanner

- Per-draft scanner cards show:
  - next action
  - role-fit summary
  - missing items
  - truth flags
  - keyword coverage
  - missing keywords
- ATS platform stats panel shows per-platform:
  - reports
  - completion rate
  - fill rate
  - waiting/manual prompts
  - restrictions
  - submitted count
- Fill-rate calculation is capped correctly at 100%
- Top reject reasons are surfaced so Phillip can see why the queue is being pruned

### Form preparation

- Supervised Playwright-based visible-browser form preparation
- Persistent browser profile in `data/playwright-profile`
- macOS Keychain-backed site credential support exists
- Form prep writes structured reports and screenshots
- Resume upload works
- Cover-letter/supporting-statement/questionnaire/headshot artifact matching is generalized across upload fields
- Combobox/autocomplete handling exists for country, city, region, and similar controls
- Expandable/collapsed sections can be opened before filling
- Multi-step progress handling is in place
- Field overrides exist for reruns
- Form prep pauses for CAPTCHA/MFA/security prompts and can be resumed
- Sensitive ATS pacing is slowed with waits and jitter
- Manual-first policy and per-domain cooldown/rate limiting exist for sensitive ATSs

### Email and follow-up

- SMTP sending through MWEB is wired, but still manual-click for real sends
- Follow-up schedule defaults to 7 days after submission
- Countdown/reminder UI exists
- Read-only IMAP inbox scanning/tracking exists

### Session and memory

- Session tab can read and write `SESSION_MEMORY.md`
- End-session handoff flow exists
- `AGENTS.md` instructs future sessions to read this file first

## Recent Product Changes Since The Older Memory File

- Refactored the app into the tool-first workspace
- Added queue approval states and queue batch actions
- Added Resume Lab editing and generated-pack visibility
- Added ATS Scanner comparison summary and platform stats
- Added CV tailoring diff views
- Tuned discovery toward graduate/junior marketing roles at source-import level
- Added reject-reason capture and learning
- Added stale-draft cleanup and queue pruning support
- Tightened title filtering so generic non-marketing roles do not slip through because of broad description keywords

## Current Operational State

Latest known healthy state after source run, rescore, and queue cleanup:

- Jobs: `824`
- Applications total: `37`
- Sources: `35`
- Enabled sources: `17`
- Active draft/ready applications after cleanup: `7`

Current active queue is intentionally small because filtering is now stricter and the bottleneck is supply quality, not queue logic.

### Current strongest remaining active drafts

- Happily - Product Growth Marketer
- Maneuver Marketing - Creative Strategist
- Coalition Technologies - Copywriter
- Adswerve, Inc - Digital Media Strategist
- Trivium - PPC & Amazon Strategist
- IAPWE - Freelance Writer

There was also one duplicate older `Maneuver Marketing - Creative Strategist` draft still active during the last queue inspection, so duplicate cleanup should be revisited if it remains visible.

### Learned reject reasons so far

- `too senior`: 9
- `not really marketing`: 7
- `wrong location`: 2

### Latest ATS stats snapshot seen during verification

- `ashby`: reports 2, fill rate 100
- `lever`: reports 1, fill rate 100
- `smartrecruiters`: reports 3, fill rate 0
- `custom`: reports 1, fill rate 0

These are operational indicators, not promises of submission success.

## Important Technical Decisions

- The app remains local-first
- Final submission is deliberately manual
- Sensitive ATSs are handled with:
  - manual-first policy
  - slower pacing
  - per-domain prep rate limits
  - cooldown after restriction pages
- SmartRecruiters-style restriction pages are treated as platform restrictions, not CAPTCHA bypass targets
- Discovery quality now matters more than bulk volume; the app should not pad the queue with obvious bad-fit roles

## Credentials And Secrets Status

- `.env` exists and is gitignored
- Site credentials can be stored locally with passwords in macOS Keychain
- MWEB SMTP and inbox tracking were configured earlier, but no secret values should be stored in this file

## Known Gaps / Next Recommended Work

1. Improve candidate supply for true graduate/junior marketing roles
   - add or retune better sources
   - add more relevant targets
   - keep pruning generic non-marketing boards
2. Review the remaining active drafts and reject weak ones with real reasons
3. Revisit duplicate-active-draft cleanup if duplicate Maneuver records still show
4. Keep improving platform adapters based on real failures from:
   - SmartRecruiters
   - Greenhouse
   - Lever
   - custom company forms
5. Add stronger learning from `No thanks` reasons into future sourcing and shortlisting

## Git / State Handoff

- Latest confirmed commit before this memory refresh: `5557079` `Tighten queue quality and discovery learning`
- Repo was clean before updating this file
- This file should be committed now so future sessions have the accurate handoff
