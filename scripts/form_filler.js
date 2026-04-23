#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

function argValue(flag) {
  const index = process.argv.indexOf(flag);
  if (index === -1 || index + 1 >= process.argv.length) return "";
  return process.argv[index + 1];
}

function splitName(fullName) {
  const parts = String(fullName || "").trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return { first: "", last: "" };
  if (parts.length === 1) return { first: parts[0], last: "" };
  return { first: parts[0], last: parts.slice(1).join(" ") };
}

async function fillFirst(locator, value, label) {
  if (!value) return false;
  try {
    const count = await locator.count();
    if (!count) return false;
    const target = locator.first();
    await target.scrollIntoViewIfNeeded({ timeout: 3000 }).catch(() => {});
    await target.fill(String(value), { timeout: 5000 });
    console.log(`filled ${label}`);
    return true;
  } catch (error) {
    return false;
  }
}

async function fillByLabels(page, labels, value, label) {
  for (const text of labels) {
    if (await fillFirst(page.getByLabel(new RegExp(text, "i")), value, label)) return true;
  }
  return false;
}

async function fillByPlaceholders(page, placeholders, value, label) {
  for (const text of placeholders) {
    if (await fillFirst(page.getByPlaceholder(new RegExp(text, "i")), value, label)) return true;
  }
  return false;
}

async function fillBySelectors(page, selectors, value, label) {
  for (const selector of selectors) {
    if (await fillFirst(page.locator(selector), value, label)) return true;
  }
  return false;
}

async function selectFirstMatchingOption(page, selectors, wanted, label) {
  if (!wanted) return false;
  const wantedLower = String(wanted).toLowerCase();
  for (const selector of selectors) {
    const select = page.locator(selector).first();
    try {
      if (!(await select.count())) continue;
      const options = await select.locator("option").evaluateAll(nodes => nodes.map(option => ({
        value: option.value,
        text: option.textContent || ""
      })));
      const match = options.find(option => option.text.toLowerCase().includes(wantedLower))
        || options.find(option => option.value.toLowerCase().includes(wantedLower));
      if (match) {
        await select.selectOption(match.value || { label: match.text }, { timeout: 5000 });
        console.log(`selected ${label}`);
        return true;
      }
    } catch (error) {
      // Continue.
    }
  }
  return false;
}

async function chooseRadioOrCheckbox(page, labels, label) {
  for (const text of labels) {
    try {
      const control = page.getByLabel(new RegExp(text, "i")).first();
      if (await control.count()) {
        await control.check({ timeout: 5000 });
        console.log(`selected ${label}`);
        return true;
      }
    } catch (error) {
      // Continue.
    }
  }
  return false;
}

async function clickApplyIfPresent(page) {
  const labels = [
    /apply for this job/i,
    /apply now/i,
    /^apply$/i,
    /start application/i,
    /submit application form/i
  ];
  for (const name of labels) {
    try {
      const button = page.getByRole("button", { name }).first();
      if (await button.count()) {
        await button.scrollIntoViewIfNeeded({ timeout: 3000 }).catch(() => {});
        await button.click({ timeout: 5000 });
        await page.waitForLoadState("domcontentloaded", { timeout: 10000 }).catch(() => {});
        console.log("clicked apply/start button");
        return;
      }
    } catch (error) {
      // Continue; many sites render non-button links or hidden buttons.
    }
    try {
      const link = page.getByRole("link", { name }).first();
      if (await link.count()) {
        await link.scrollIntoViewIfNeeded({ timeout: 3000 }).catch(() => {});
        await link.click({ timeout: 5000 });
        await page.waitForLoadState("domcontentloaded", { timeout: 10000 }).catch(() => {});
        console.log("clicked apply/start link");
        return;
      }
    } catch (error) {
      // Continue.
    }
  }
}

async function fillProfileFields(page, task) {
  const profile = task.profile || {};
  const name = splitName(profile.full_name);

  await fillByLabels(page, ["first name", "given name"], name.first, "first name");
  await fillByLabels(page, ["last name", "surname", "family name"], name.last, "last name");
  await fillByLabels(page, ["full name", "^name$"], profile.full_name, "full name");
  await fillByLabels(page, ["email", "e-mail"], profile.email, "email");
  await fillByLabels(page, ["phone", "mobile", "telephone"], profile.phone, "phone");
  await fillByLabels(page, ["location", "city", "current location"], profile.location, "location");
  await fillByLabels(page, ["linkedin", "linked in"], profile.linkedin_url, "linkedin");
  await fillByLabels(page, ["portfolio", "website"], profile.portfolio_url || profile.linkedin_url, "portfolio/website");

  await fillByPlaceholders(page, ["email", "e-mail"], profile.email, "email placeholder");
  await fillByPlaceholders(page, ["phone", "mobile"], profile.phone, "phone placeholder");
  await fillByPlaceholders(page, ["linkedin"], profile.linkedin_url, "linkedin placeholder");

  await fillBySelectors(page, [
    'input[name="first_name"]',
    'input[id="first_name"]',
    'input[name="candidate[first_name]"]',
    'input[name="job_application[first_name]"]',
    'input[name*="first" i]',
    'input[id*="first" i]',
  ], name.first, "first name selector");
  await fillBySelectors(page, [
    'input[name="last_name"]',
    'input[id="last_name"]',
    'input[name="candidate[last_name]"]',
    'input[name="job_application[last_name]"]',
    'input[name*="last" i]',
    'input[id*="last" i]',
    'input[name*="surname" i]',
  ], name.last, "last name selector");
  await fillBySelectors(page, [
    'input[name="name"]',
    'input[id="name"]',
    'input[name="candidate[name]"]',
    'input[name="job_application[name]"]',
  ], profile.full_name, "full name selector");
  await fillBySelectors(page, [
    'input[name="email"]',
    'input[id="email"]',
    'input[name="candidate[email]"]',
    'input[name="job_application[email]"]',
    'input[type="email"]',
    'input[name*="email" i]',
    'input[id*="email" i]',
  ], profile.email, "email selector");
  await fillBySelectors(page, [
    'input[name="phone"]',
    'input[id="phone"]',
    'input[name="candidate[phone]"]',
    'input[name="job_application[phone]"]',
    'input[type="tel"]',
    'input[name*="phone" i]',
    'input[id*="phone" i]',
    'input[name*="mobile" i]',
  ], profile.phone, "phone selector");
  await fillBySelectors(page, [
    'input[name*="linkedin" i]',
    'input[id*="linkedin" i]',
    'input[name*="urls" i]',
    'input[id*="urls" i]',
  ], profile.linkedin_url, "linkedin selector");
  await selectFirstMatchingOption(page, [
    'select[name*="location" i]',
    'select[id*="location" i]',
    'select[name*="country" i]',
    'select[id*="country" i]',
  ], "South Africa", "country/location");
}

async function fillTextAreas(page, task) {
  const app = task.application || {};
  const profile = task.profile || {};
  const answers = app.answers || "";
  const coverLetter = app.cover_letter || "";

  await fillByLabels(page, ["cover letter", "cover note", "message to hiring", "additional information"], coverLetter, "cover letter");
  await fillByLabels(page, ["why.*interested", "why.*role", "why.*company", "why do you want"], answers, "questionnaire answers");
  await fillByLabels(page, ["salary", "compensation"], profile.salary_expectation, "salary expectation");
  await fillByLabels(page, ["notice", "availability", "start date"], profile.availability || profile.notice_period, "availability");
  await fillBySelectors(page, [
    'textarea[name*="cover" i]',
    'textarea[id*="cover" i]',
    'textarea[name*="comments" i]',
    'textarea[id*="comments" i]',
    'textarea[name*="message" i]',
  ], coverLetter, "cover letter selector");
  await fillBySelectors(page, [
    'input[name*="salary" i]',
    'input[id*="salary" i]',
    'input[name*="compensation" i]',
    'input[id*="compensation" i]',
  ], profile.salary_expectation, "salary selector");
  await fillBySelectors(page, [
    'input[name*="available" i]',
    'input[id*="available" i]',
    'input[name*="start" i]',
    'input[id*="start" i]',
    'input[name*="notice" i]',
    'input[id*="notice" i]',
  ], profile.availability || profile.notice_period, "availability selector");

  const textareas = page.locator("textarea");
  const count = await textareas.count().catch(() => 0);
  for (let i = 0; i < count; i += 1) {
    const area = textareas.nth(i);
    try {
      const value = await area.inputValue({ timeout: 1000 }).catch(() => "");
      if (value) continue;
      const meta = `${await area.getAttribute("name").catch(() => "")} ${await area.getAttribute("id").catch(() => "")} ${await area.getAttribute("placeholder").catch(() => "")}`.toLowerCase();
      if (meta.includes("cover")) {
        await area.fill(coverLetter, { timeout: 5000 });
        console.log("filled textarea cover letter");
      } else if (meta.includes("why") || meta.includes("question") || meta.includes("additional")) {
        await area.fill(answers || coverLetter, { timeout: 5000 });
        console.log("filled textarea answers");
      }
    } catch (error) {
      // Leave ambiguous textareas untouched.
    }
  }
}

async function answerCommonScreening(page, task) {
  const profile = task.profile || {};
  await chooseRadioOrCheckbox(page, ["prefer not", "decline to self", "i do not wish"], "prefer not to answer");
  await fillByLabels(page, ["work authorization", "right to work", "visa"], profile.work_authorization, "work authorization");
  await fillByLabels(page, ["salary expectation", "expected salary", "compensation"], profile.salary_expectation, "salary expectation");
}

async function uploadCv(page, task) {
  const cvPath = task.profile && task.profile.cv_path;
  if (!cvPath || !fs.existsSync(cvPath)) {
    console.log("cv path missing or not found; skipped upload");
    return;
  }

  const inputs = page.locator('input[type="file"]');
  const count = await inputs.count().catch(() => 0);
  for (let i = 0; i < count; i += 1) {
    const input = inputs.nth(i);
    try {
      const meta = [
        await input.getAttribute("name").catch(() => ""),
        await input.getAttribute("id").catch(() => ""),
        await input.getAttribute("aria-label").catch(() => ""),
        await input.getAttribute("accept").catch(() => "")
      ].join(" ").toLowerCase();
      if (i === 0 || meta.includes("resume") || meta.includes("cv") || meta.includes("upload")) {
        await input.setInputFiles(cvPath, { timeout: 8000 });
        console.log("uploaded CV to file input");
        return;
      }
    } catch (error) {
      console.log(`file input skipped: ${error.message}`);
    }
  }
  console.log("no file input found for CV upload");
}

async function addReviewBanner(page, task) {
  await page.evaluate((data) => {
    const banner = document.createElement("div");
    banner.id = "job-application-ai-review-banner";
    banner.textContent = `Job Application AI filled what it could for ${data.title || "this role"}. Review every field manually. The assistant will not click submit.`;
    Object.assign(banner.style, {
      position: "fixed",
      zIndex: "2147483647",
      left: "12px",
      right: "12px",
      bottom: "12px",
      padding: "14px 16px",
      background: "#fff7ed",
      color: "#4a2c0a",
      border: "2px solid #b35c00",
      borderRadius: "8px",
      fontFamily: "Arial, sans-serif",
      fontSize: "15px",
      boxShadow: "0 12px 30px rgba(0,0,0,.18)"
    });
    document.body.appendChild(banner);
  }, { title: task.job && task.job.title });
}

async function main() {
  const taskPath = argValue("--task");
  if (!taskPath) {
    console.error("Usage: node scripts/form_filler.js --task /path/to/task.json");
    process.exit(2);
  }
  const task = JSON.parse(fs.readFileSync(taskPath, "utf8"));
  if (!task.job || !task.job.url) {
    throw new Error("Task is missing job.url");
  }

  const userDataDir = path.join(path.dirname(path.dirname(taskPath)), "playwright-profile");
  fs.mkdirSync(userDataDir, { recursive: true });
  const context = await chromium.launchPersistentContext(userDataDir, {
    headless: false,
    slowMo: 70,
    viewport: { width: 1380, height: 920 },
    acceptDownloads: true
  });
  const page = context.pages()[0] || await context.newPage();
  page.setDefaultTimeout(7000);

  console.log(`opening ${task.job.url}`);
  await page.goto(task.job.url, { waitUntil: "domcontentloaded", timeout: 45000 });
  await clickApplyIfPresent(page);
  await fillProfileFields(page, task);
  await uploadCv(page, task);
  await fillTextAreas(page, task);
  await answerCommonScreening(page, task);
  await addReviewBanner(page, task).catch(() => {});

  console.log("Form preparation complete. Review manually and submit yourself. Close the browser when done.");
  await page.waitForTimeout(24 * 60 * 60 * 1000);
}

main().catch((error) => {
  console.error(error.stack || error.message);
  process.exit(1);
});
