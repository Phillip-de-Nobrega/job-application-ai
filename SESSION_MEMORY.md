# Session Memory

Last updated: 2026-05-07 (end of session 2)

## Project Goal

Local, review-first job application assistant for early-career marketing roles. Discovers jobs, scores them, generates tailored application material, prepares forms for review, tracks follow-ups. Target: ~5 strong applications per day. Phillip reviews and manually submits.

## Current Local Setup

- Project path: `/Users/phillip/Desktop/JOB APPLICATION AI`
- Main app: `app.py` (single Python file, standard library only)
- Local app URL: `http://127.0.0.1:8765`
- Database: `data/job_application_ai.sqlite3`
- LaunchAgent: `com.phillip.job-application-ai`
- GitHub: `git@github.com:Phillip-de-Nobrega/job-application-ai.git`
- Latest commit: `d72d886`

## User Profile

- Name: Phillip de Nobrega
- Email: Phillip2002@mweb.co.za | Phone: +27 71 643 0185
- Location: Constantia, Cape Town, Western Cape, SA
- LinkedIn: linkedin.com/in/phillip-de-nobrega-87542b353
- Citizenship: SA + UK passport
- CV: `/Users/phillip/Desktop/PHILLIP PERSONAL/Phillip_de_Nobrega_CV.pdf`
- Salary target: ~R22,000/month
- Full-time from: 2027-01-01 | Trial/project until: 2026-06-12

## Current Operational State

- Jobs in DB: ~880
- Active drafts: ~3 (sources still running to refill)
- Enabled sources: 14 (Ashby, Lever, Greenhouse, Remotive, Gymshark, Virgin Active SA, Luno)
- SmartRecruiters cooldown clears ~10:35 UTC 2026-05-07

### Disabled sources (and why)
- RemoteOK — CAPTCHA/signup gated, can't auto-apply
- RedBull, FrasersGroup, AIM Sports, ThirdChannel, Bommarito (SmartRecruiters) — dump entire global catalogue, mostly wrong-location jobs
- BizCommunity — scrapes category pages, not real job listings
- CareerJunction — same issue
- Arbeitnow — mostly German student/intern roles
- We Work Remotely — 403 blocker

## Work Done This Session (2026-05-07 continued)

### Platform cleanup
- Added BLOCKED_JOB_PLATFORMS list blocking remoteok, indeed, linkedin, ziprecruiter, monster, glassdoor etc.
- `should_keep_discovered_role` now rejects jobs from blocked platforms at import
- `is_board_prep_blocked_url` checks all blocked platforms
- Rejected/removed ~350+ junk jobs (German, wrong-location, non-job-listing pages)
- Removed duplicate source records (6 deduped)

### UX improvements
- Scroll position preserved on "Not interested", "I applied for this", "Fill in application form"
- Daily Review now shows ALL pending applications (no 5-card cap)
- Each card: Fill in application form (primary), I applied for this, ✕ Remove (top-right), Edit draft, Open job
- "Skip all" batch button when multiple cards present
- Empty state: "All clear!" with proper guidance
- Submitted applications now correctly leave Daily Review and appear in Follow-up Reminders

### Form filler improvements
- `looksLikeSignupPage()` detects signup pages by URL or field pattern
- `attemptSignupIfNeeded()` fills name/email/password on signup pages — stops before Create Account
- Fills name/email even without saved password; leaves password field for manual entry
- Saved Logins panel moved to visible location in Drafts tab (was hidden in `<details>`)
- "Manage saved logins" button added to My Profile tab

### Form filler question answers
- Catches 5 more open-ended question patterns (previously silently skipped)
- Added specific answers: SEO tools, marketing results, automation experience, motivation
- Fixed root bug: generic textarea fallback was dumping entire Q&A into unrecognised fields
- Unknown questions now flagged empty for manual review

## Technical Notes

- Node.js: `/opt/homebrew/bin/node` — `_find_node()` in app.py handles PATH
- SmartRecruiters rate limit: 12h cooldown after bot detection. Check `active_domain_rate_limits()`
- Global Claude skills in `~/.claude/`: GSD, Superpowers, Claude-Mem, Everything CC, UI/UX Pro Max, n8n-MCP

## Next Steps

1. Add remoteok.com credential in Drafts → Saved Logins (email + password) for future use
2. Wait for SmartRecruiters cooldown to clear (~10:35 UTC), then WHOOP/TeamSnap/Sporty boards reactivate
3. Run "Search all sources now" to refill the pipeline when queue is empty
4. Consider adding more Greenhouse/Lever/Ashby boards for SA-relevant or remote-friendly companies
