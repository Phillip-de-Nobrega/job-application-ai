# Session Memory

Last updated: 2026-05-07 (end of day)

## Project Goal

Phillip is building a local, review-first job application assistant for early-career marketing roles. The app discovers suitable jobs, scores them, generates tailored application material, prepares live application forms for review, tracks follow-ups, and aims for about 5 strong applications per day.

The system drafts and prepares — Phillip reviews and manually submits or sends.

## Current Local Setup

- Project path: `/Users/phillip/Desktop/JOB APPLICATION AI`
- Main app: `app.py` (single Python file, standard library only)
- Local app URL: `http://127.0.0.1:8765`
- Database: `data/job_application_ai.sqlite3`
- LaunchAgent installed: `com.phillip.job-application-ai`
- GitHub: `git@github.com:Phillip-de-Nobrega/job-application-ai.git`
- Latest commit: `6edc49d` Move site credentials to visible panel

## User Profile

- Name: Phillip de Nobrega
- Location: Constantia, Cape Town, Western Cape, South Africa
- Email: Phillip2002@mweb.co.za
- Phone: +27 71 643 0185
- LinkedIn: linkedin.com/in/phillip-de-nobrega-87542b353
- Citizenship: South African + UK passport
- CV: `/Users/phillip/Desktop/PHILLIP PERSONAL/Phillip_de_Nobrega_CV.pdf`
- Salary target: ~R22,000/month
- Full-time availability: 2027-01-01
- Trial/project availability: until 2026-06-12

### Role preferences
- Target: graduate, junior, entry-level, assistant, coordinator, content, brand, social media, growth, PPC, SEO, CRM, copywriter, digital marketing
- Location: Cape Town in-person/hybrid OR clearly remote globally
- Avoid: manager, director, VP roles

## Current Operational State

- Jobs: ~879
- Sources: 54 (33 enabled)
- Active application drafts: 6 (5 have RemoteOK listing URLs needing real apply links)
- Duplicate Maneuver Marketing still present (apps 17 and 22) — remove one with "Not interested"

## All Work Done This Session (2026-05-07)

### Discovery & scoring
- ENTRY_LEVEL_SIGNALS: added entry level, entry-level, learnership, trainee, placement
- REMOTE_ALLOWED_LOCATION_TERMS: added "africa"
- MARKETING_KEYWORDS: added digital marketing, influencer marketing, public relations, SEM, google ads, affiliate, storytelling, b2c, copy
- Added 8 new job sources (BizCommunity SA, CareerJunction CT, Strava/Ashby, Gymshark, Virgin Active SA, HubSpot/Greenhouse, We Work Remotely disabled, Decathlon SA disabled)
- Rejection learning: score_job penalises prior "not really marketing" (−40) and "wrong location" (−35)
- source_cleanup_recommendations flags sources with >60% rejection rate

### Form prep critical fixes
- Node.js at `/opt/homebrew/bin/node` not on subprocess PATH → fixed with `_find_node()`
- SmartRecruiters: derive `jobs.smartrecruiters.com` apply URL from listing ref
- SmartRecruiters apply button selector added to form_filler.js

### UI/UX full redesign
- UI/UX Pro Max skill applied: Swiss Modernism 2.0 + Job Board/Recruitment palette (#0369A1)
- Lucide SVG icon library (CDN) replacing all emoji
- 78 label replacements: plain English throughout
- Pipeline progress bar on Home: Find → Write Draft → Fill Form → You Submit → Follow Up → Interview
- Status colour badges, section intro text, hover states

### Dashboard UX
- "Review draft" scrolls editor into view
- Error messages: 10s timeout + scroll into view
- "Fill in application form" always visible on every card
- RemoteOK/board-listing jobs: clicking Fill opens listing + inline paste field on card
- "Not interested" button: one-click remove + replace, no prompts
- `/api/jobs/update-url` endpoint to save pasted apply URL

### Form filler intelligence
- classifyField: 5 new open-ended question patterns caught (previously skipped silently)
- answerForCategory: specific answers for SEO tools, marketing results, automation, motivation
- Fixed root bug: generic textarea fallback was dumping all Q&A answers into unrecognised fields
- Unknown questions now left blank + flagged for manual review

### Account signup support
- looksLikeSignupPage() detects signup by URL pattern or field combination
- attemptSignupIfNeeded() fills name, email, password, confirm-password, ticks terms
- Stops before clicking Create Account — user clicks that themselves
- If no password saved: clear message to add one in Saved Logins

### Saved Logins UI
- Moved from hidden `<details>` in Drafts tab to visible panel
- Renamed to "🔐 Saved Logins & Passwords" with clear RemoteOK instructions
- "Manage saved logins" shortcut button added to My Profile tab

## Next Steps When Returning

1. Go through the 5 RemoteOK jobs on Home — click Fill in application form, paste real apply URL
2. Hit "Not interested" on the duplicate Maneuver Marketing card (apps 17 or 22)
3. Add remoteok.com credential in ✏️ Drafts tab → Saved Logins panel
4. Review and approve strong drafts: Happily, Trivium, Coalition Technologies
5. Run Find Jobs sources again periodically to grow supply

## Technical Notes

- Node.js: `/opt/homebrew/bin/node` — `_find_node()` in app.py handles PATH issue
- Keychain passwords: stored under domain + username key, read by `readKeychainPassword()` in form_filler.js
- Global skills installed in `~/.claude/` — GSD, Superpowers, Claude-Mem, Everything CC, UI/UX Pro Max, n8n-MCP, Obsidian, Awesome CC
