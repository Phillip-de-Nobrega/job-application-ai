# Session Memory

Last updated: 2026-04-28

## Latest Handoff

- Local app URL now in active use: `http://127.0.0.1:8766`.
- Local database backup created before tool updates: `data/backups/job_application_ai-20260428-093257.sqlite3`.
- Current code state includes:
  - generalized file/artifact upload handling across ATSs
  - `Refresh with new options` in Applications
  - Applications view filter: `Current batch`, `Active only`, `All`
  - real `batch_id` support so `Current batch` reflects the latest generated set
  - `No thanks` buttons on application cards and in the draft editor, with reject-and-replace behavior
  - combobox/autocomplete handling
  - expandable-section handling
  - slower, jittered browser pacing on sensitive ATSs
  - broader `manual-first ATS` policy
  - per-domain ATS prep rate limits before the harder cooldown after restriction pages
- Recent user-reported issue: some ATSs displayed restriction text such as `We detected unusual activity from your device or network`. The current direction is to reduce automation pace, enforce manual-first handling on sensitive ATSs, and rate-limit retries rather than trying to brute-force form prep.
- Important current status: `app.py` and `scripts/form_filler.js` have uncommitted changes that should be committed before updating Codex or VS Code.

## Project Goal

Phillip is building a local-first job application assistant that can find suitable marketing jobs, generate tailored application material from his CV/profile, prepare online application forms for review, track submissions, and create personalized email follow-ups. The system should help produce about 5 good applications per day.

The app must be review-first: it can fill and draft, but Phillip checks and clicks final submit/send.

## User Preferences

- Target roles: marketing roles, ideally outdoor, sports, fitness, wellness, lifestyle, or consumer brands, but not limited to only those.
- Target locations: Cape Town/Western Cape in-person or hybrid roles, and clearly remote roles based elsewhere. Remote USA/UK/Europe roles can be considered, but roles restricted to another physical city/country should be reviewed carefully.
- Updated location rule from Phillip on 2026-04-23: he lives in Cape Town. Jobs should be in-person/hybrid in Cape Town/Western Cape, or clearly remote if based elsewhere. Non-Cape-Town physical roles should be avoided unless Phillip explicitly approves them.
- Salary target: around R22,000/month. For foreign currencies, convert to South African rand and judge against that target.
- Availability: full-time from 2027-01-01; available until 2026-06-12 for trial/project/internship-style work.
- CV source: `/Users/phillip/Desktop/PHILLIP PERSONAL/Phillip_de_Nobrega_CV.pdf`.
- Email: `Phillip2002@mweb.co.za`.
- Follow-ups: generate a personalized follow-up email for each submitted application, due 7 days after submission, with a countdown and manual send button.
- Automation preference: local app first, not hosted online.

## CV/Profile Facts Extracted

- Name: Phillip de Nobrega.
- Location: Cape Town, South Africa.
- Phone: `+27 71 643 0185`.
- Email: `Phillip2002@mweb.co.za`.
- LinkedIn: `linkedin.com/in/phillip-de-nobrega-87542b353`.
- Citizenship: South African and UK citizenship/passport.
- Education: University of Cape Town, BBusSci Marketing, 75%+ average, honours-equivalent.
- Experience includes:
  - Junior Marketing Content Creator, The Cookie Factory.
  - Market Research Consultant, Look@ / SIGMUND Project.
  - Sports Coach, rugby and water polo.
  - Triathlon/Gym Training App project.
- Certification: Google Analytics Certification, Google Digital Academy 2025.

## Current App State

- Project directory: `/Users/phillip/Desktop/JOB APPLICATION AI`.
- Main app: `app.py`.
- Local URL: `http://127.0.0.1:8766`.
- Database: `data/job_application_ai.sqlite3`.
- Generated docs: `documents/`.
- Local secrets: `.env` exists and is gitignored. Do not reveal its contents.
- Runtime logs: `data/logs/`.
- The app is installed as a macOS LaunchAgent named `com.phillip.job-application-ai`, so it starts at login.
- Last known health check: app was healthy with 538 jobs, 20 applications, 35 sources, 29 enabled sources, 36 targets, 3 automation runs, and 80 inbox messages.
- The app now has Targets and Session tabs.

## Implemented Features

- Python standard-library local web app with SQLite.
- Profile storage seeded from Phillip's CV and stated preferences.
- CV text extraction from the attached PDF.
- Manual job intake by URL/text.
- Automatic discovery from compliant/public ATS sources:
  - Greenhouse
  - Lever
  - Ashby
  - SmartRecruiters
  - Recruitee
  - Direct URL
  - Remotive public API
  - Remote OK public API
  - Arbeitnow public API
- Starter source seeding for sports/fitness/outdoor-adjacent companies.
- Daily workflow button that runs discovery, rescoring, top-five shortlisting, and draft generation.
- Marketing-focused role scoring with sports/fitness/outdoor boosts.
- Salary checks against R22,000/month with USD/GBP/EUR to ZAR conversion where possible.
- Risk flags for scams, poor location fit, below-target salary, seniority mismatch, and role mismatch.
- Draft generation for cover letter, questionnaire answers, CV tailoring notes, and follow-up email.
- Generated application packs include a tailored CV brief in `.txt` and `.html`.
- Application tracker with statuses and submitted date.
- Follow-up scheduling 7 days after submission.
- Browser alert/countdown for due or overdue follow-ups.
- SMTP email sending through MWEB after manual click. Test email worked.
- Outreach tab for companies with no advertised role.
- Personalized outreach drafts and do-not-contact status.
- Target company tracking with single-company save and bulk import.
- Target companies can be converted into enabled automatic job sources or outreach leads.
- Session tab can read `SESSION_MEMORY.md`, generate an end-session draft, and save the memory file after review.
- Dashboard and Discover now show Source Health with enabled count, errors, recent import counts, and run/pause actions.
- Applications tab has a local form-fill smoke test that launches a fake application form through Playwright.
- Dashboard has a Daily Review section showing the five drafts to process, missing details, fit concerns, and next actions.
- Application drafts have company research fields and a Research company button. Research can use the saved job posting and an optional company/about/careers URL.
- Application drafts have a Humanize sent copy button for cover letters, questionnaire answers, and follow-up emails.
- Outreach drafts have a Humanize outreach button.
- SMTP follow-up and outreach sending automatically applies the Phillip-voice pass before sending.
- Phillip's sending voice: a 23-year-old South African marketing graduate who studied in Cape Town; professional, natural, warm, concise, specific, and not generic AI/corporate language.
- Analytics tab shows application funnel, source quality, follow-up health, and recommendations.
- Discover tab has Import Job Alert for pasted LinkedIn/Indeed/Google Alert/recruiter/company alert emails or text. It extracts links and saves tracked jobs without scraping protected pages.
- Profile tab has writing-sample ingestion from pasted text or local `.txt`, `.md`, `.pdf`, and `.docx` document paths. It stores extracted text and style notes.
- Targets tab has a Seed starter targets button.
- Starter target list has been seeded into the DB: 20 target companies.
- Auto Mode tab runs the safe preparation pipeline: seed targets, convert targets with ATS tokens into sources, run discovery, rescore, shortlist, draft, research, humanize, assess quality/checklists, write report, and update checklist.
- Added application quality score, quality notes, generated checklist, truthfulness/work-authorization flags, and recommended CV version.
- Added CV version, answer bank, story bank, and automation run history.
- Created `AUTOMATION_CHECKLIST.md` with separate Phillip and Codex checklists.
- Weekly report is generated at `documents/weekly-job-search-report.md`.
- Reminder calendar export writes pending follow-ups to `data/reminders/job-application-reminders.ics` and `data/reminders/job-application-reminders.md`.
- Native macOS notification support checks due follow-ups while the app is running and can be triggered manually from Auto Mode.
- Read-only IMAP inbox reply tracking can scan the inbox, classify replies, match them to applications/outreach, and store review items in `inbox_messages`.
- Phillip's real writing sample is now stored from `/Users/phillip/Documents/Climate change in South Africa- mr weber (geo).docx`.
- Writing sample analysis: 4,080 extracted characters, longer explanatory/reflective sentences, no obvious contractions, and a more formal student-writing style.
- Applications now include Form Fill Feedback fields after Prepare Form. Feedback is stored in `form_fill_feedback`.
- Auto Mode tab now shows feedback-based selector recommendations.
- Auto Mode tab now has Source Cleanup and a Pause failing sources action.
- Public careers-page discovery extracts likely job links from visible careers pages, including Workable/Teamtailor-style public pages when links are present.
- Workable public discovery now tries Workable's public published-jobs endpoint before falling back to visible careers-page extraction.
- Teamtailor discovery now handles visible public jobs pages, structured `JobPosting` data, and embedded Teamtailor job URLs.
- Company research now uses bounded multi-page public research: supplied research URL, company-matching links from job posts, and safe homepage/about/careers pages when available. It excludes ATS apply pages, social platforms, login pages, and common third-party marketing tools.
- Analytics now includes a Replies And Outcomes panel for inbox classifications, matched applications, matched outreach, interview signals, rejections, and auto-replies.
- Company research extraction now includes page title, meta description, headings, and useful evidence sentences.
- Location filtering now enforces Phillip's Cape Town rule: Cape Town/Western Cape physical roles are preferred, clearly remote roles are allowed, non-Cape-Town physical roles are penalized/excluded, and remote roles restricted to off-target places are flagged.
- Public careers-page discovery now avoids saving generic navigation/category links such as `Careers`, `View`, `Blog`, `Overview`, and broad department pages as job postings.
- Shortlisting now avoids duplicate company/title pairs so the daily list has distinct opportunities.
- Playwright supervised form filling:
  - Opens a visible browser.
  - Uses a persistent profile in `data/playwright-profile`.
  - Fills obvious fields and uploads CV where clear.
  - Handles common Greenhouse/Lever/Ashby-like field names.
  - Stops before final submit.

## Known Guardrails

- Do not automate final submission.
- Do not bypass CAPTCHA, MFA, login challenges, anti-bot systems, rate limits, paywalls, or robots controls.
- Do not invent credentials, work authorization, salary, qualifications, demographic answers, or experience.
- LinkedIn and Indeed should remain guided/manual unless official permission/API access exists.
- Cold outreach must be personalized, limited, reviewed, and manually sent.

## Current Generated Drafts

Fresh daily shortlist generated on 2026-04-23:

- Happily - Product Growth Marketer - Remote - Worldwide.
- Maneuver Marketing - Creative Strategist - Remote - Worldwide.
- Coalition Technologies - Copywriter - Remote - Worldwide.
- Spacedome Media GmbH - Werksstudent:in -Junior Performance-Marketing Manager - Remote - Berlin.
- Adswerve, Inc - Digital Media Strategist - Remote - Worldwide.

Known generated applications from the previous session:

- Avida - Performance Marketing Manager.
- Red Bull - Field Marketing Manager, Wales & South East, 12 Months FTC.
- Frasers Group - Paid Media Executive, US.
- Red Bull - Event Website Manager.
- Red Bull - National Events Manager.

These were generated into `documents/` and tracked in the local database.

## Important Technical Notes

- Python HTTPS certificate issues were handled by retrying public GET requests with an unverified SSL context only when certificate verification fails. SMTP is unaffected.
- The scheduler waits briefly on startup so the server binds before discovery begins.
- `scripts/install_launch_agent.sh` installs the macOS LaunchAgent using an absolute Python path.
- `scripts/uninstall_launch_agent.sh` removes the LaunchAgent.
- `scripts/form_filler.js` handles supervised Playwright filling and writes logs to `data/logs/form-fill-*.log` files.

## Next Good Work Items

1. Add 20-50 target companies in the Targets tab and convert known careers pages into sources.
2. Keep tuning the Phillip-voice rewrite as more real writing examples are provided.
3. Improve Workable/Teamtailor support further if Phillip provides official API keys or reliable public careers URLs.
4. Add stronger reply analytics once real inbox replies are captured.
5. Add inbox labels or API-based reply tracking later if Phillip wants Gmail/Outlook instead of MWEB IMAP.

## Latest Session Update - 2026-04-22

- Created `AGENTS.md` with instructions to read and update `SESSION_MEMORY.md`.
- Created this `SESSION_MEMORY.md` as durable project memory.
- Added `SESSION_MEMORY_PATH` support in `app.py`.
- Added Session tab to the app with refresh, generate end-session draft, and save memory actions.
- Added `target_companies` SQLite table.
- Added Targets tab for dream-fit company tracking.
- Added target bulk import format: `Company | website | industry | careers URL | notes`.
- Added APIs to save/import targets and convert a target into a job source or outreach lead.
- Added Source Health panels on Dashboard and Discover.
- Added local Playwright form-fill smoke test in the Applications tab.
- Added Daily Review cards on the Dashboard.
- Added `research_url`, `research_notes`, and `research_sources` fields to applications.
- Added `/api/applications/research` endpoint.
- Added company research notes/source files into generated application packs.
- Added `email_voice` to the profile.
- Added local Phillip-voice rewrite for generated cover letters, questionnaire answers, follow-up emails, and outreach emails.
- Added `/api/applications/humanize` and `/api/leads/humanize` endpoints.
- Added Humanize sent copy button to application drafts and Humanize outreach button to outreach drafts.
- Follow-up and outreach SMTP sends now run through the Phillip-voice pass before sending.
- Added Analytics tab.
- Added `/api/alerts/import` endpoint.
- Added Import Job Alert panel in Discover for pasted job-alert emails/text.
- Added `writing_sample_path`, `writing_sample_text`, and `writing_style_notes` profile fields.
- Added `/api/profile/extract-writing-sample` endpoint.
- Added writing sample UI in Profile with extraction/analysis button.
- Added starter target-company list and `/api/targets/seed-starter`.
- Seeded 20 starter target companies into the local database.
- Added `cv_versions`, `answer_bank`, `story_bank`, and `automation_runs` tables.
- Added application assessment fields: `quality_score`, `quality_notes`, `checklist`, `truthfulness_flags`, and `recommended_cv_version`.
- Added safe `/api/automation/run` endpoint and Auto Mode tab.
- Added default CV versions, answer bank entries, and story bank entries.
- Added weekly report generation.
- Created `AUTOMATION_CHECKLIST.md`.
- Added `form_fill_feedback` table and `/api/applications/form-feedback`.
- Added source cleanup recommendations and `/api/sources/pause-failing`.
- Paused failing source `Sporty Group sports media` because it returned HTTP 404.
- Added public careers-page link extraction and source support for `careers`, `workable`, and `teamtailor` source types.
- Improved company research page fact extraction.
- Added per-application tailored CV brief exports in `.txt` and `.html`.
- Added reminder calendar export to `data/reminders/job-application-reminders.ics` plus a Markdown summary.
- Added native macOS due follow-up notifications and a Notify due now button in Auto Mode.
- Cleaned generated tailored CV and weekly report formatting.
- Updated README and implementation plan.
- Restarted the LaunchAgent using `scripts/install_launch_agent.sh`.
- Verified `python3 -m py_compile app.py`.
- Verified local endpoints for session memory read, end-session draft generation, and empty target import.
- Verified app health after restart: 359 jobs, 5 applications, 12 sources, 0 targets.
- Did not launch the smoke-test browser automatically; use the Applications tab button when ready.
- Verified application research endpoint on application `1`; it generated stored notes and sources.
- Verified application humanizer endpoint on application `1`; it returned rewritten cover letter, answers, follow-up, and voice-check feedback.
- Verified Analytics tab rendered in the app.
- Verified job-alert import endpoint with a fake alert, then removed the test job; app health returned to 359 jobs, 5 applications, 12 sources, 0 targets.
- Verified writing-sample endpoint using fake text, then cleared that fake sample from the profile.
- Verified app health after starter targets: 359 jobs, 5 applications, 12 sources, 20 targets.
- Ran Automatic Mode once. Result: imported/updated 533 jobs, generated 5 drafts, researched 4 drafts, humanized 5 drafts, assessed 10 applications, and logged automation run `1`.
- After Automatic Mode, app health: 369 jobs, 10 applications, 13 sources, 20 targets, 1 automation run.
- Verified form-fill feedback endpoint with a test row, then deleted the test row.
- Verified careers-page link extraction on a local sample.
- Latest health after pausing failing source: 369 jobs, 10 applications, 13 sources, 12 enabled sources, 20 targets.
- Verified reminder export; currently 0 pending reminders because no applications are marked submitted and no outreach is marked sent.
- Verified due-notification endpoint behavior with no pending due reminders.
- Regenerated the Avida application pack with clean tailored CV output.
- Regenerated `documents/weekly-job-search-report.md` with clean formatting.

## Latest Session Update - 2026-04-23

- Added Phillip's strict Cape Town location rule into scoring and shortlisting.
- Added Remote OK query parsing fix; Remote OK now imports relevant remote marketing roles instead of returning zero because the query was treated as one long phrase.
- Added Arbeitnow Europe remote jobs as a safe public API source.
- Seeded the new source into the database as source `94`.
- Ran Remote OK source `43`; it imported 39 roles.
- Ran Arbeitnow source `94`; it imported 39 roles.
- Improved careers-page extraction so generic navigation/category links are not saved as fake jobs.
- Changed generic `/careers` and `/jobs` pages with no visible job links to `no-visible-jobs` instead of creating one fake job.
- Added location hints from careers-page context when Cape Town, Western Cape, Johannesburg, Durban, or remote wording is visible.
- Added duplicate company/title suppression in the daily shortlist.
- Fixed short keyword matching so location keyword `uk` does not trigger inside unrelated words.
- Tightened remote eligibility checks using full posting text, so remote jobs with hidden geography restrictions or city-tied remote wording are flagged harder.
- Added low-yield source cleanup for public careers-page URLs returning repeated `no-visible-jobs`, and paused 12 such weak sources plus timeout/failure cases.
- Shortlist now considers drafted roles as part of the active review queue, so stronger existing opportunities do not get replaced by weaker new ones.
- Draft generation now pulls more specific role priorities from each posting for cover letters, answers, and follow-up emails.
- Company research now ignores job-board homepages like Remote OK, Remotive, and Arbeitnow when trying to infer company pages.
- Added official research URL defaults for Avida, Happily, Maneuver Marketing, Coalition Technologies, Brandwatch, and Red Bull.
- Added a small Cape Town priority in shortlist ordering when jobs are otherwise close, and increased manager/director seniority penalties.
- Added a persistent `too senior for me` job flag in the Jobs view; flagged jobs are rescored down and excluded from the shortlist.
- Added a `Use saved URL now` button in the Applications view so Phillip can rerun company research from the saved research URL without retyping it.
- Restarted the LaunchAgent after code changes.
- Ran Auto Mode. Result: 27 sources ran, 663 jobs imported/updated, 538 jobs rescored, 5 jobs shortlisted, 5 drafts generated, 5 drafts humanized, 20 applications assessed, weekly report regenerated, reminders exported, inbox scan checked 80 messages and imported 6 new inbox messages.
- Current app state after this run: 538 jobs, 20 applications, 35 sources, 29 enabled sources, 36 target companies, 3 automation runs, 80 inbox messages.
- Latest generated application packs are in `documents/` for Happily, Maneuver Marketing, Coalition Technologies, Spacedome Media GmbH, and Adswerve.
- Known issue: Auto Mode still tries some weak/failing public careers pages; currently seen errors include Sporty Group 404 and Yoco timeout. Use Source Cleanup / Pause failing sources if they keep failing.
- After cleanup and shortlist retuning later the same day, enabled sources dropped to 17 and the preferred active five became Happily, Avida, Maneuver Marketing, Coalition Technologies, and Red Bull Cape Town.

## Earlier Session Update - 2026-04-23

- Added IMAP inbox configuration fields in the Email tab.
- Added `/api/email/inbox-config`, `/api/email/scan-inbox`, and `/api/inbox/status`.
- Added `inbox_messages` table for local reply tracking.
- Added read-only inbox scanning using IMAP, with MWEB defaults `imap.mweb.co.za`, port `993`, SSL enabled.
- Added reply classification for interviews, rejections, auto-replies, general replies, and unknown messages.
- Added application/outreach matching by contact email, email domain, company name, and role title terms.
- Added Tracked Replies UI with actions to mark interview, rejected, outreach replied, reviewed, or ignored.
- Automatic Mode scans inbox replies when IMAP credentials are configured.
- Added Workable public published-jobs endpoint support with fallback to visible careers-page extraction.
- Added structured `JobPosting` JSON-LD and embedded ATS URL parsing for public careers pages.
- Improved Teamtailor support for public jobs URLs and visible embedded job links.
- Verified `python3 -m py_compile app.py`.
- Verified local parser checks for structured jobs, Workable payloads, inbox classification, and Avida reply matching.
- Restarted the LaunchAgent using `scripts/install_launch_agent.sh`.
- Verified running app state after restart: 381 jobs, 10 applications, 13 sources, 12 enabled sources, 20 targets, 0 inbox messages, IMAP password not set.
- Added Phillip's real writing sample from the climate change `.docx`.
- Updated the local voice pass so formal application material uses the saved writing sample as a light style guide without copying private passages.
- Updated `AUTOMATION_CHECKLIST.md`: real writing sample and voice tuning are now marked complete.
- Added deeper company research URL inference and fixed a bad tool-link inference case where `Customer.io` was being saved as a company research URL.
- Added reply/outcome analytics to the Analytics tab.
- Ran Auto Mode on 2026-04-23. Result: 534 jobs imported/updated, 381 rescored, 5 shortlisted, 5 new drafts generated, 5 humanized, 15 assessed, run id `2`.
- Regenerated research and application document packs for applications `11` through `15` after tightening research URL inference.
- Latest generated drafts include RedBull On Premise Marketing Specialist, RedBull Brand Marketing Intern, RedBull Marketing_Brand Marketing Specialist, WHOOP Deputy Chief of Staff, and Sweatpals Senior Lifecycle Marketing Manager.
- Phillip saved the MWEB IMAP password locally through the Email tab. Do not expose it.
- Fixed inbox message saving by replacing the partial-index `ON CONFLICT` upsert with explicit select/update/insert logic.
- Ran inbox scan: 80 messages scanned, 79 imported, 0 auto-matched. Classifications: 34 unknown, 32 auto_reply, 9 reply, 4 interview.
- Added manual inbox matching controls in Tracked Replies: Match application and Match outreach.
- Updated profile and scoring for Phillip's location preference: Cape Town in-person/hybrid or remote elsewhere only.
- Rescored all 381 jobs after the location preference update.
- Earlier in the day, the strict location filter temporarily produced only 1 questionable role; this was superseded by the later Remote OK/Arbeitnow source work above, which produced 5 distinct current drafts.

## End Session Rule

When Phillip says `end session`, update this file with:

- What changed during the session.
- Files changed.
- Current app health/status if checked.
- Any new decisions or user preferences.
- Any blockers or risks.
- The best next actions.

Do not store secrets in this file.
