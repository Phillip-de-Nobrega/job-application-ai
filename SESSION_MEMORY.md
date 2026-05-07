# Session Memory

Last updated: 2026-05-07

## Project Goal

Phillip is building a local, review-first job application assistant for early-career marketing roles. The app discovers suitable jobs, scores them, generates tailored application material from his CV and profile, prepares live application forms for review, tracks follow-ups, and aims for about 5 strong applications per day.

The system drafts and prepares — Phillip reviews and manually submits or sends.

## Current Local Setup

- Project path: `/Users/phillip/Desktop/JOB APPLICATION AI`
- Organised copy also at: `/Users/phillip/01_Active_Projects/Python_JobApplicationAI/`
- Main app: `app.py` (single Python file, standard library only)
- Local app URL: `http://127.0.0.1:8765`
- Database: `data/job_application_ai.sqlite3`
- Documents/output folder: `documents/`
- LaunchAgent installed: `com.phillip.job-application-ai`
- GitHub: `git@github.com:Phillip-de-Nobrega/job-application-ai.git`
- Latest commit: `14e7e6f` Add Not Interested button and inline apply URL flow

## User Profile And Preferences

- Name: Phillip de Nobrega
- Location: 4 Hauptville Circle, Constantia, Cape Town, Western Cape, 7806, South Africa
- Email: Phillip2002@mweb.co.za
- Phone: +27 71 643 0185
- LinkedIn: linkedin.com/in/phillip-de-nobrega-87542b353
- Citizenship/work status: South African plus UK passport/citizenship
- CV source: `/Users/phillip/Desktop/PHILLIP PERSONAL/Phillip_de_Nobrega_CV.pdf`
- Salary target: about R22,000/month
- Full-time availability: 2027-01-01
- Trial/project availability until: 2026-06-12

### Role preferences

- Target roles: graduate, junior, entry-level, assistant, coordinator, associate, specialist, content, brand, social media, growth, partnerships, community, campaign, PPC, SEO, CRM, copywriter, digital marketing
- Avoid: manager, director, head, VP, leadership-heavy roles unless Phillip explicitly approves
- Location rule: Cape Town / Western Cape for in-person or hybrid; otherwise clearly remote
- Remote US/UK/Europe roles are acceptable when truly remote

## Current Operational State

- Jobs: ~879
- Sources: 54 (33 enabled) — includes 8 new sources added this session:
  BizCommunity SA, CareerJunction CT, We Work Remotely, Strava (Ashby),
  Gymshark (careers), Virgin Active SA, HubSpot (Greenhouse), Decathlon SA
- Active applications: 6 drafts (5 have RemoteOK listing URLs, 1 has real Ashby URL)
- Duplicate Maneuver Marketing draft still present (apps 17 and 22) — needs cleanup

## Work Done This Session (2026-05-07)

### Discovery improvements
- Expanded `ENTRY_LEVEL_SIGNALS`: added entry level, entry-level, learnership, trainee, placement
- Added "africa" to `REMOTE_ALLOWED_LOCATION_TERMS`
- Strengthened `MARKETING_KEYWORDS`: digital marketing, influencer marketing, public relations, SEM, Google Ads, affiliate, storytelling, b2c, copy
- Added 8 new job sources (BizCommunity, CareerJunction, Strava, HubSpot, etc.)
- Fixed Strava → Ashby (not Lever), Gymshark → careers URL
- Disabled Decathlon SA and We Work Remotely (403/blocking)

### SmartRecruiters fixes
- `discover_smartrecruiters` now derives `jobs.smartrecruiters.com` apply URL from listing ref
- Added SmartRecruiters apply button selectors to `form_filler.js`

### Scoring / rejection learning
- `score_job` now penalises "not really marketing" (−40) and "wrong location" (−35) prior rejects
- `source_cleanup_recommendations` now flags sources with >60% rejection rate

### Form prep critical fix
- Node.js was at `/opt/homebrew/bin/node` but not on subprocess PATH — fixed in `_find_node()`
- Form prep now works for real ATS URLs (confirmed on Sleeper/Ashby job)

### UI/UX redesign
- Applied UI/UX Pro Max skill: Swiss Modernism 2.0 + Job Board/Recruitment palette
- Professional blue palette (#0369A1 primary, #16A34A success, #DC2626 danger)
- Navigation: plain English with Lucide SVG icons (house, clipboard-list, edit-3, etc.)
- 78 label replacements: "Prepare form"→"Fill in application form", "Mark submitted"→"I applied for this", "Humanize"→"Polish writing", "ATS Scanner"→"Readiness Check", etc.
- Added 6-step pipeline progress bar on Home screen
- Status colour badges, section intro text, empty state components
- Removed all emoji, replaced with Lucide icon library (CDN)

### Dashboard UX fixes
- "Review draft" now scrolls editor into view after tab switch
- Error messages stay visible 10s and scroll into view
- "Fill in application form" always shown on every card
- For RemoteOK/board-listing URLs: clicking Fill opens listing in new tab + shows inline paste field on card
- "Not interested" button: one-click removal + replacement, no prompts
- Fixed action messages to be specific and actionable

### Known remaining tasks
1. Review the 6 active drafts and reject weak ones with real reasons
2. Fix duplicate Maneuver Marketing (apps 17 and 22 — same job, one is a duplicate)
3. For the 5 RemoteOK-URL jobs: use the new inline paste flow to add real apply URLs
4. Run sources again to grow supply from the new sources

## Node.js Path Note

Node is at `/opt/homebrew/bin/node` — not on the Python subprocess PATH on macOS.
The app now uses `_find_node()` to locate it. If form prep ever fails with "node not found",
check this function in app.py.

## Credentials And Secrets Status

- `.env` exists and is gitignored
- MWEB SMTP and IMAP were configured earlier
- No secret values in this file
