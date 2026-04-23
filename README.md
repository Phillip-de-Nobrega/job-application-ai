# Job Application AI

Local-first job application assistant for Phillip de Nobrega.

This MVP helps with:

- Profile and job-search preference storage.
- Job intake from manual URLs/text.
- API-friendly discovery for Greenhouse, Lever, and Ashby boards.
- Public Workable and Teamtailor career-page discovery where pages/endpoints are available.
- Fit scoring for marketing roles, with weighting for outdoor, sports, and fitness brands.
- Cover letter, questionnaire answer, and follow-up email drafts.
- Tailored CV brief exports for each generated application pack.
- Application tracking from discovery through follow-up.
- Embedded text extraction from the attached CV PDF.
- Salary assessment against a R22,000/month target, including USD/GBP/EUR conversion to ZAR where salary text is visible.
- Target company tracking for dream-fit brands and careers pages.
- Session memory review/editing through the local app.

The app is intentionally review-first. It prepares applications and stops before final submission.
LinkedIn and Indeed should be used as guided/manual sources unless you have explicit permission for automation.

## Run

```bash
python3 app.py
```

Then open:

```text
http://127.0.0.1:8765
```

The app creates local data in `data/job_application_ai.sqlite3` and generated documents in `documents/`.

## CV

Your CV path is pre-filled as:

```text
/Users/phillip/Desktop/PHILLIP PERSONAL/Phillip_de_Nobrega_CV.pdf
```

The app includes a basic built-in PDF text extractor for this CV. If a future PDF is image-only or uses unusual encoding, install a dedicated extractor such as `pdftotext` or paste the CV text into the Profile tab.

## Writing Sample

The Profile tab has a writing-sample section. You can paste text you wrote naturally or provide a local document path. Supported simple formats are `.txt`, `.md`, `.pdf`, and `.docx`. The app extracts the text and stores style notes so generated emails, cover letters, and sent application material can be tuned closer to Phillip's real voice.

## Salary Conversion

The app checks visible salary text against a target of `R22,000/month`. For USD, GBP, and EUR it tries to fetch a current ZAR exchange rate from Frankfurter's public exchange-rate API, then falls back to conservative built-in estimates if offline.

Location fit is strict: in-person or hybrid roles should be in Cape Town/Western Cape. Roles outside Cape Town are only suitable when they are clearly remote, unless Phillip manually approves an exception.

## Email Follow-ups

The Email tab can save local SMTP settings and send test/follow-up emails. MWEB's current SMTP settings are:

- Host: `smtp.mweb.co.za`
- Port: `587`
- Username: full MWEB email address
- Authentication: required
- STARTTLS/encryption: try enabled first; if MWEB rejects it, test again with STARTTLS unticked

The password is stored only in the local `.env` file, which is gitignored. Do not share `.env`.

When an application is marked as submitted, the app schedules a follow-up for 7 days later. The Dashboard and Applications tab show the countdown. If a follow-up is due or overdue, the app shows a browser alert when loaded. Follow-ups are sent only when you click the send button.

Follow-ups can be personalized per application with:

- Contact name
- Contact role
- Contact email
- Company/product/campaign notes

Use **Regenerate personalized follow-up** after adding those details.

## Inbox Reply Tracking

The Email tab also has **Inbox Reply Tracking**. It uses read-only IMAP access to scan the inbox, classify likely recruiter/company replies, and match them back to applications or outreach leads.

MWEB's current IMAP settings are:

- Host: `imap.mweb.co.za`
- Port: `993`
- Username: full MWEB email address
- SSL/TLS: enabled

The inbox password is stored only in `.env`, like SMTP. The app does not delete, archive, mark read, or send email during inbox scans. It creates a local review queue where you can mark likely interview, rejection, outreach reply, reviewed, or ignored.

The Auto Mode tab can also export a local reminder calendar:

```text
data/reminders/job-application-reminders.ics
```

Import that `.ics` file into Calendar if you want follow-up reminders outside the app. The summary file is written to `data/reminders/job-application-reminders.md`.

The app also checks for due follow-ups while it is running and can show a native macOS notification. Use **Notify due now** in Auto Mode to test or manually trigger due reminders. Notifications are reminders only; they do not send emails or submit anything.

## Application Review And Research

The Dashboard has a **Daily Review** section showing the current five drafts to process, missing details, fit concerns, and the next action for each role.

Each application draft has a **Research company** button. It stores company research notes and source links using the saved job posting, and can optionally fetch a company website/about/careers URL that you add in the draft editor. Research notes are also written into the generated application pack.

Company research now checks multiple bounded public signals where possible: a supplied research URL, company-matching links found in the job posting, and safe homepage/about/careers pages when the job URL is on the company's own site. It deliberately excludes ATS apply pages, social platforms, login pages, and common third-party marketing tools so the application angle stays focused on the employer.

Each application draft also has **Humanize sent copy**. Use it before sending or attaching generated material. It rewrites the cover letter, questionnaire answers, and follow-up email toward Phillip's voice: a young South African marketing graduate from Cape Town, professional but natural and not generic. SMTP follow-up sending also runs through this voice pass automatically.

Generated application folders now include a **tailored CV brief** in both `.txt` and `.html`. This is not a fake CV rewrite; it is a truthful brief showing which CV version to use, which keywords to mirror, which evidence bullets to prioritise, and which claims must not be invented.

## Company Outreach

The Outreach tab tracks companies you like even when no job is advertised. It stores company/contact details, personalization notes, source URL, draft status, and do-not-contact status. Outreach emails are review-first and are sent only after you click send.

Outreach drafts have **Humanize outreach**, and outreach sending also applies the same voice pass automatically before SMTP send.

## Target Companies

The Targets tab stores companies Phillip actively wants to watch, including website, careers URL, industry, priority, ATS source token, and notes about why the company fits. A target can be converted into:

- an enabled automatic job source, when a careers URL or ATS token is known;
- an outreach lead, when no suitable job is advertised but the company is worth contacting.

Bulk import supports one company per line:

```text
Company | website | industry | careers URL | notes
```

Use **Seed starter targets** to add an initial sports/fitness/outdoor/wellness list, including brands such as Nike, adidas, Salomon, Patagonia, Decathlon, Totalsports, Cape Union Mart, Red Bull, Garmin, Strava, WHOOP, Virgin Active South Africa, and Discovery Vitality.

## Automation Direction

The long-term target is automatic discovery plus supervised application filling:

- scheduled local job searches,
- compliant ATS/company-career-page discovery,
- scoring and deduplication,
- daily shortlist of the best roles,
- Playwright-assisted form filling,
- final submit left to you.

LinkedIn and Indeed should stay guided/manual unless explicit permission or official access exists. The app should not bypass CAPTCHA, MFA, rate limits, robots controls, or anti-bot systems.

## Job Alert Import

The Discover tab has **Import Job Alert**. Paste a LinkedIn, Indeed, Google Alert, recruiter, or company job-alert email into it. The app extracts usable job links and saves them for scoring/review without scraping protected pages.

## Automatic Discovery

The Discover tab has **Automatic Sources**. Save Greenhouse, Lever, Ashby, SmartRecruiters, Recruitee, or direct URL sources there. Enabled sources rerun once per day while the local app is open, and can also be run manually with **Run all enabled now**.

Use **Seed starter sources** to add an initial sports/fitness/outdoor-adjacent set, including Sleeper, Sweatpals, Eight Sleep, Avida, TeamSnap, WHOOP, Sporty Group, Red Bull, Frasers Group, AIM Sports Group, ThirdChannel, and Bommarito Performance Systems.

Source examples:

- Greenhouse: board token from `boards.greenhouse.io/<token>`
- Lever: site name from `jobs.lever.co/<site>`
- Ashby: board name from Ashby job board URLs
- SmartRecruiters: company identifier from SmartRecruiters company URLs
- Recruitee: subdomain from `{company}.recruitee.com`
- Workable: account subdomain from `apply.workable.com/<company>` or a Workable careers URL. The app first tries Workable's public published-jobs endpoint, then falls back to visible page extraction.
- Teamtailor: public careers URL, jobs URL, or subdomain. The app extracts visible job links and structured job data; official Teamtailor API access still requires a Public Read API key from the company account.
- Direct URL: a specific careers/job page URL

The Dashboard has **Run daily workflow**. It runs enabled sources, rescoring, top-five shortlisting, and draft generation in one action.

The Dashboard and Discover tab include **Source Health**, which shows enabled source count, visible source errors, recent import counts, and quick run/pause actions.

The Auto Mode tab includes **Source Cleanup**, which recommends broken or low-value sources. Use **Pause failing sources** to stop known broken sources from slowing down automatic runs.

Public careers-page sources can now extract likely job links from normal careers pages, including Workable- or Teamtailor-hosted pages where the jobs are visible on public pages. This is not a private API integration and does not bypass login or platform controls.

The parser also reads public `JobPosting` JSON-LD structured data and embedded ATS job URLs when present.

## Analytics

The Analytics tab shows:

- job/application totals and response rate;
- application funnel by status;
- source quality by tracked jobs, average score, strong fits, drafts, submissions, and responses;
- follow-up health;
- inbox reply classification and matched application/outreach outcomes;
- practical recommendations for what to fix next.

## Automatic Mode

The Auto Mode tab runs the safe preparation pipeline in one action:

- seed target companies;
- convert targets with known ATS tokens into enabled sources;
- run enabled sources;
- rescore jobs;
- shortlist top roles;
- generate drafts;
- add research notes;
- humanize sent copy;
- calculate quality scores and checklists;
- write a weekly report;
- export follow-up reminders to a local calendar file;
- show native macOS notifications for due follow-ups;
- scan configured inbox replies and update the local reply queue;
- update `AUTOMATION_CHECKLIST.md`.

Automatic Mode does not submit applications or send emails. Final submit/send remains manual.

The generated checklist is stored at `AUTOMATION_CHECKLIST.md`. The weekly report is stored at `documents/weekly-job-search-report.md`. Reminder exports are stored in `data/reminders/`.

## Supervised Form Filling

The Applications tab includes **Prepare form**. It creates a local task, opens a visible Playwright browser, fills clear fields, uploads the CV where it can identify a file upload, and then stops for manual review. It never clicks final submit.

The Playwright browser uses a persistent local profile under `data/playwright-profile`, so manual logins can be reused where a site allows it.

Use **Run form-fill smoke test** in the Applications tab to open a fake local application form and check that the filler works before trying a real job site.

After using **Prepare form**, save **Form Fill Feedback** in the application draft. Record what worked, what was missed, what was wrong, and notes about the ATS. The Auto Mode tab summarizes feedback and recommends selector improvements.

Setup:

```bash
npm install
npx playwright install chromium
```

## Start at Login

To run the app automatically when you log into macOS:

```bash
scripts/install_launch_agent.sh
```

To remove that startup item:

```bash
scripts/uninstall_launch_agent.sh
```

## Session Memory

The app has a Session tab that reads and writes `SESSION_MEMORY.md`. Use **Generate end-session draft** near the end of a work session, review the text, then use **Save memory file**. Future Codex sessions should read `SESSION_MEMORY.md` before continuing.

## Next Integrations

Recommended next additions:

- Add broader form mappings for more ATS platforms.
- Add an LLM provider key for stronger company research and document generation.
