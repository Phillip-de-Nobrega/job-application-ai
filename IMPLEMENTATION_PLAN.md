# Implementation Plan

## Operating Principle

This system is a local, supervised job application assistant. It can research, score, draft, track, and prepare applications, but Phillip reviews before final submission.

It must not:

- Bypass CAPTCHA, MFA, rate limits, paywalls, robots controls, or anti-bot systems.
- Create fake accounts or misrepresent identity.
- Submit bulk applications without review.
- Invent skills, experience, qualifications, salary details, work authorization, or demographic answers.

## Current MVP

Implemented:

- Local Python web app using only the standard library.
- SQLite database in `data/job_application_ai.sqlite3`.
- Profile vault seeded with Phillip's stated preferences.
- Job intake by manual entry or URL import.
- Public ATS discovery for:
  - Greenhouse
  - Lever
  - Ashby
- Marketing-focused fit scoring.
- Extra weighting for outdoor, sports, fitness, wellness, lifestyle, adventure, and consumer brands.
- Application draft generation:
  - Cover letter
  - CV tailoring notes
  - Tailored CV brief export
  - Questionnaire answers
  - Follow-up email
- Application tracking and status updates.
- Print-friendly generated application packs in `documents/`.
- Guided search links for LinkedIn, Indeed, company careers, and remote boards.
- Built-in text extraction from Phillip's current PDF CV.
- Salary checks against R22,000/month with USD/GBP/EUR to ZAR conversion where salary text is visible.
- Target company tracking with bulk import and conversion into automatic sources or outreach leads.
- Session memory tab that reads, drafts, and saves `SESSION_MEMORY.md`.
- Source health panels on Dashboard and Discover showing import counts, visible errors, and run/pause actions.
- Local form-fill smoke test that opens a fake application form through Playwright.
- Daily Review dashboard showing five drafts, missing details, fit concerns, and next actions.
- Application-level company research notes and source links.
- Phillip-voice pass for sent copy, including cover letters, questionnaire answers, follow-up emails, and outreach emails.
- Analytics tab for application funnel, source quality, follow-up health, and recommendations.
- Job alert text import for LinkedIn, Indeed, Google Alerts, recruiter, and company-alert emails.
- Writing-sample ingestion from pasted text or `.txt`, `.md`, `.pdf`, and `.docx` paths, with local style-note analysis.
- Starter target-company seed list for sports, fitness, outdoor, wellness, and South African-relevant brands.
- Safe Automatic Mode pipeline for discovery, shortlisting, draft generation, research, humanizing, quality scoring, checklists, weekly report generation, reminder calendar export, and due follow-up notifications.
- `AUTOMATION_CHECKLIST.md` with separate Phillip and Codex checklists.
- Form-fill feedback storage and feedback-based selector recommendations.
- Source cleanup recommendations and pause-failing-sources action.
- Public careers-page job-link discovery, including Workable/Teamtailor-style public pages when links are visible.
- Workable public published-jobs endpoint support, with fallback to visible careers-page extraction.
- Teamtailor public careers-page extraction with structured `JobPosting` data and embedded job URL parsing.
- Improved company research extraction from page title, meta description, headings, and useful evidence sentences.
- Bounded multi-page company research using supplied research URLs, company-matching links from job posts, and safe homepage/about/careers candidates.
- Read-only IMAP inbox reply tracking with local reply classification and application/outreach matching.

## Phase 1: Profile Quality

Goal: make generated applications much stronger by improving the source-of-truth profile.

Needed from Phillip:

- Email address. Captured: `Phillip2002@mweb.co.za`.
- Phone number. Captured: `+27 71 643 0185`.
- LinkedIn URL. Captured: `https://linkedin.com/in/phillip-de-nobrega-87542b353`.
- Portfolio/GitHub/website URL if any.
- Current notice/start timing. Captured: full-time from 2027-01-01; short trial/project period until 2026-06-12.
- Salary target/range for South African roles. Captured: target around R22,000/month.
- Salary target/range for remote USD/GBP/EUR roles. Captured: convert to ZAR and judge against R22,000/month.
- Whether remote contractor roles are acceptable.
- Whether relocation is acceptable.
- Exact work authorization limits for USA, UK, and Europe. Current note: dual SA/UK citizenship; confirm exact application wording per country.
- Demographic question preferences.

Build tasks:

- Add structured experience entries.
- Add a skill/bullet evidence bank.
- Add approved answer templates.
- Add "never claim" rules.
- Add stronger CV tailoring from approved bullet variants. First version implemented as per-application tailored CV briefs in generated document packs.

## Phase 2: Better Discovery

Goal: reliably produce at least 5 good applications per day.

Sources to add:

- Workable public job widgets/API where available. First version implemented for public published jobs and visible careers pages.
- SmartRecruiters.
- Recruitee.
- Teamtailor. First version implemented for visible public pages; official API still needs a Public Read API key from the company account.
- Remote OK.
- Otta/Welcome to the Jungle-style sources if allowed and practical.
- South African sources that expose usable public pages or alerts.
- Email alert ingestion from LinkedIn, Indeed, Google Alerts, company job alerts, and recruiters.

LinkedIn and Indeed approach:

- Use them as guided sources unless explicit permission/API access exists.
- Open searches in the user's browser.
- User saves or pastes job links/descriptions into the app.
- App drafts and tracks the application.
- No hidden scraping, CAPTCHA bypass, or automated mass submission.

Build tasks:

- Add duplicate detection by semantic-ish text fingerprinting.
- Add saved search presets.
- Add company blacklist and keyword filters.
- Add daily shortlist workflow.
- Add scam/risk flags.
- Use the Targets tab as the source-of-truth list for 20-50 dream-fit companies.

Automation target:

- Run a local scheduled search job.
- Pull jobs from compliant sources automatically.
- Score and deduplicate roles.
- Create a daily queue of the best 5-15 roles.
- Keep LinkedIn/Indeed as guided sources unless explicit automation permission/API access exists.
- Never bypass CAPTCHA, login challenges, rate limits, robots controls, or anti-bot systems.

Implemented safe first version:

- Paste job-alert emails/text into Discover.
- Extract usable job links.
- Save them as tracked jobs for scoring and review.
- Do not log into or scrape protected LinkedIn/Indeed pages.

## Phase 3: Company Research

Goal: make each cover letter specific to the business.

Build tasks:

- Fetch company website/about/careers pages where available.
- Extract product, customer, industry, tone, and recent signal.
- Store citations with each generated draft.
- Add "company angle" evidence to cover letters.
- Add review warnings when research is weak or unverified.

Optional:

- Add an LLM provider key for summarization and drafting.
- Keep citation and evidence checks mandatory even with an LLM.

## Phase 4: Supervised Form Filling

Goal: fill application forms locally, then stop before final submission.

Recommended tool:

- Playwright.

Build tasks:

- Install Playwright and browser dependencies.
- Add a "prepare application" button.
- Open job application URL in a controlled browser.
- Fill fields where labels are clear.
- Upload selected CV/cover letter.
- Pause on login, MFA, CAPTCHA, ambiguous fields, or final submit.
- Save screenshots and a submission checklist.

Rules:

- User must click final submit.
- User handles account login.
- No anti-bot evasion.

## Phase 4B: Company Outreach

Goal: contact carefully selected companies even when no role is advertised.

Implemented first version:

- Company lead database.
- Contact name, role, email, source URL, and company notes.
- Personalized outreach draft generation.
- Review-first sending through the configured MWEB SMTP account.
- Do-not-contact status.

Build tasks:

- Add company discovery from approved public sources.
- Add source citations for each company/contact.
- Add duplicate detection by company domain and contact email.
- Add suppression-list enforcement before every send.
- Add daily outreach limit.
- Add cold outreach follow-up reminders.
- Add bounce/reply tracking.

## Phase 5: Email Follow-ups

Goal: follow up without losing track.

MVP behavior:

- Generate follow-up drafts.
- Open `mailto:` draft links.
- Export pending follow-ups to `data/reminders/job-application-reminders.ics`.
- Show native macOS notifications for due follow-ups while the local app is running.

Next build options:

- SMTP sending with an app password.
- Gmail API integration.
- Apple Mail draft automation.
- Richer notification preferences and per-reminder snooze controls.
- Reply tracking via Gmail/Outlook APIs if Phillip later moves away from MWEB IMAP or wants stronger mailbox labels.

Needed from Phillip:

- Which email provider to use.
- Whether the app should only create drafts or actually send after approval.
- Follow-up cadence, for example 7 days after application and 14 days after interview.

## Phase 6: Analytics

Goal: improve the job search over time.

Metrics:

- Applications per day.
- Response rate by source.
- Response rate by role type.
- Response rate by industry.
- Response rate by CV version.
- Time from application to response.
- Interview conversion rate.

Build tasks:

- Add analytics dashboard.
- Add weekly report.
- Add reminder calendar export.
- Add native follow-up notifications.
- Add inbox/reply tracking.
- Add reply/outcome analytics.
- Add recommendations based on outcomes.

## Recommended Immediate Next Step

Add 20-50 target companies in the Targets tab, convert known careers pages into enabled sources, then run the daily workflow and review the generated drafts.
