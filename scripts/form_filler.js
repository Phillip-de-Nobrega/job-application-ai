#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");
const { chromium } = require("playwright");

const MAC_GOOGLE_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

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

function shortText(value, limit = 160) {
  const clean = String(value || "").replace(/\s+/g, " ").trim();
  if (!clean) return "";
  return clean.length > limit ? `${clean.slice(0, limit - 1)}...` : clean;
}

function escapeRegExp(value) {
  return String(value || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function normalizePromptKey(value) {
  return String(value || "").replace(/\s+/g, " ").trim().toLowerCase();
}

function ensureDir(filePath) {
  if (!filePath) return;
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
}

function pushUnique(list, value) {
  if (value && !list.includes(value)) list.push(value);
}

function record(list, item) {
  list.push({
    prompt: shortText(item.prompt || item.label || item.name || item.reason || "Unnamed field", 220),
    category: item.category || "",
    kind: item.kind || "",
    value_preview: shortText(item.value_preview || item.value || item.choice || "", 140),
    reason: shortText(item.reason || "", 220)
  });
}

function readKeychainPassword(credential) {
  if (!credential || !credential.keychain_service || !credential.username) return "";
  try {
    return execFileSync(
      "security",
      [
        "find-generic-password",
        "-a",
        String(credential.username),
        "-s",
        String(credential.keychain_service),
        "-w"
      ],
      { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] }
    ).trim();
  } catch (error) {
    return "";
  }
}

function hostFromUrl(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch (error) {
    return "";
  }
}

function inferPlatform(task, pageUrl = "") {
  const explicit = String(task.platform || "").trim().toLowerCase();
  if (explicit) return explicit;
  const host = hostFromUrl(pageUrl || task.job?.url || "");
  if (host.endsWith("linkedin.com")) return "linkedin";
  if (host.endsWith("indeed.com") || host.endsWith("indeed.co.za")) return "indeed";
  if (host.endsWith("greenhouse.io")) return "greenhouse";
  if (host.endsWith("lever.co")) return "lever";
  if (host.endsWith("ashbyhq.com")) return "ashby";
  if (host.endsWith("smartrecruiters.com")) return "smartrecruiters";
  if (host.includes("workable.com")) return "workable";
  if (host.includes("teamtailor.com")) return "teamtailor";
  if (host.endsWith("recruitee.com")) return "recruitee";
  return "custom";
}

function nowIso() {
  return new Date().toISOString();
}

async function launchBestBrowser(report) {
  const base = {
    headless: false,
    slowMo: 70,
    args: [
      "--disable-crashpad",
      "--disable-crash-reporter",
      "--disable-breakpad"
    ]
  };
  const attempts = [];
  if (fs.existsSync(MAC_GOOGLE_CHROME)) {
    attempts.push({
      label: "system-google-chrome",
      options: { ...base, executablePath: MAC_GOOGLE_CHROME }
    });
  }
  attempts.push({
    label: "playwright-chrome-channel",
    options: { ...base, channel: "chrome" }
  });
  attempts.push({
    label: "playwright-chromium",
    options: { ...base }
  });

  const errors = [];
  for (const attempt of attempts) {
    try {
      const browser = await chromium.launch(attempt.options);
      report.browser = { launcher: attempt.label };
      return browser;
    } catch (error) {
      errors.push(`${attempt.label}: ${error.message}`);
    }
  }
  report.browser = { launcher: "failed" };
  report.errors.push(...errors);
  throw new Error(errors.join("\n"));
}

function stepPatternsForPlatform(platform) {
  const generic = [/^next$/i, /^continue$/i, /save and continue/i, /continue application/i, /next step/i];
  if (platform === "greenhouse") return [...generic, /review/i];
  if (platform === "lever") return [...generic, /continue to application/i];
  if (platform === "ashby") return [...generic, /continue$/i];
  if (platform === "smartrecruiters") return [...generic, /continue$/i];
  if (platform === "workable") return [...generic, /continue$/i];
  return generic;
}

function finalSubmitPatterns() {
  return [
    /^submit$/i,
    /submit application/i,
    /complete application/i,
    /send application/i,
    /^apply$/i,
    /^finish$/i,
    /review and submit/i
  ];
}

async function fillFirst(locator, value, label, report) {
  if (!value) return false;
  try {
    const count = await locator.count();
    if (!count) return false;
    const target = locator.first();
    await target.scrollIntoViewIfNeeded({ timeout: 3000 }).catch(() => {});
    await target.fill(String(value), { timeout: 5000 });
    record(report.filled_fields, { prompt: label, value, kind: "heuristic" });
    console.log(`filled ${label}`);
    return true;
  } catch (error) {
    return false;
  }
}

function matcher(pattern) {
  if (pattern instanceof RegExp) return pattern;
  return new RegExp(String(pattern), "i");
}

function preferredAnswerValue(category, answer) {
  const raw = String(answer?.choice || answer?.value || "").trim();
  if (!raw) return "";
  if (category === "location") return raw.split(",")[0].trim() || raw;
  return raw;
}

async function fillByLabels(page, labels, value, label, report) {
  for (const text of labels) {
    if (await fillFirst(page.getByLabel(matcher(text)), value, label, report)) return true;
  }
  return false;
}

async function fillByPlaceholders(page, placeholders, value, label, report) {
  for (const text of placeholders) {
    if (await fillFirst(page.getByPlaceholder(matcher(text)), value, label, report)) return true;
  }
  return false;
}

async function fillBySelectors(page, selectors, value, label, report) {
  for (const selector of selectors) {
    if (await fillFirst(page.locator(selector), value, label, report)) return true;
  }
  return false;
}

async function selectFirstMatchingOption(page, selectors, wanted, label, report) {
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
        record(report.filled_fields, { prompt: label, value: match.text || match.value, kind: "select" });
        console.log(`selected ${label}`);
        return true;
      }
    } catch (error) {
      // Continue.
    }
  }
  return false;
}

async function chooseRadioOrCheckbox(page, labels, label, report) {
  for (const text of labels) {
    try {
      const control = page.getByLabel(new RegExp(text, "i")).first();
      if (await control.count()) {
        await control.check({ timeout: 5000 });
        record(report.filled_fields, { prompt: label, value: text, kind: "choice" });
        console.log(`selected ${label}`);
        return true;
      }
    } catch (error) {
      // Continue.
    }
  }
  return false;
}

async function clickAndFollow(page, locator, report) {
  const context = page.context();
  const popupPromise = context.waitForEvent("page", { timeout: 4000 }).catch(() => null);
  const currentUrl = page.url();
  await locator.scrollIntoViewIfNeeded({ timeout: 3000 }).catch(() => {});
  await locator.click({ timeout: 5000 });
  const popup = await popupPromise;
  if (popup) {
    await popup.waitForLoadState("domcontentloaded", { timeout: 15000 }).catch(() => {});
    pushUnique(report.visited_urls, popup.url());
    return popup;
  }
  await page.waitForLoadState("domcontentloaded", { timeout: 10000 }).catch(() => {});
  await page.waitForTimeout(1200);
  if (page.url() !== currentUrl) {
    pushUnique(report.visited_urls, page.url());
  }
  return page;
}

async function clickApplyIfPresent(page, report, platform) {
  await page.waitForTimeout(1500).catch(() => {});
  const labels = [
    /apply for this job/i,
    /apply now/i,
    /^apply$/i,
    /start application/i,
    /submit application form/i
  ];
  if (platform === "linkedin") labels.unshift(/easy apply/i, /apply on company site/i);
  if (platform === "indeed") labels.unshift(/apply now/i, /apply on company site/i);
  if (platform === "ashby") labels.unshift(/apply now/i);
  if (platform === "lever" || platform === "greenhouse") labels.unshift(/apply for this job/i);
  for (const name of labels) {
    try {
      const button = page.getByRole("button", { name }).first();
      if (await button.count()) {
        page = await clickAndFollow(page, button, report);
        report.clicked_apply = true;
        pushUnique(report.visited_urls, page.url());
        console.log("clicked apply/start button");
        return page;
      }
    } catch (error) {
      // Continue.
    }
    try {
      const link = page.getByRole("link", { name }).first();
      if (await link.count()) {
        page = await clickAndFollow(page, link, report);
        report.clicked_apply = true;
        pushUnique(report.visited_urls, page.url());
        console.log("clicked apply/start link");
        return page;
      }
    } catch (error) {
      // Continue.
    }
  }
  const textFallbacks = [
    /apply for this job/i,
    /apply now/i,
    /start application/i,
    /^apply$/i
  ];
  for (const pattern of textFallbacks) {
    try {
      const locator = page.getByText(pattern).first();
      if (await locator.count()) {
        page = await clickAndFollow(page, locator, report);
        report.clicked_apply = true;
        pushUnique(report.visited_urls, page.url());
        console.log("clicked apply/start text fallback");
        return page;
      }
    } catch (error) {
      // Continue.
    }
  }
  if (platform === "greenhouse") {
    const greenhouseSelectors = [
      'a[href="#app"]',
      'a[href$="#app"]',
      'a[id*="apply" i]',
      'button[id*="apply" i]',
      'a[href*="/application" i]',
      'a[data-mapped="true"]'
    ];
    for (const selector of greenhouseSelectors) {
      try {
        const locator = page.locator(selector).first();
        if (await locator.count()) {
          page = await clickAndFollow(page, locator, report);
          report.clicked_apply = true;
          pushUnique(report.visited_urls, page.url());
          console.log("clicked greenhouse apply fallback");
          return page;
        }
      } catch (error) {
        // Continue.
      }
    }
  }
  if (platform === "ashby") {
    try {
      const currentUrl = page.url();
      const directApplyUrl = currentUrl.replace(/\/+$/, "") + "/application";
      if (directApplyUrl !== currentUrl) {
        await page.goto(directApplyUrl, { waitUntil: "domcontentloaded", timeout: 45000 });
        report.clicked_apply = true;
        pushUnique(report.visited_urls, page.url());
        console.log("navigated directly to Ashby application");
        return page;
      }
    } catch (error) {
      report.errors.push(`Ashby direct application fallback failed: ${error.message}`);
    }
  }
  return page;
}

async function revealExpandableSections(page, report, platform) {
  const revealPatterns = [
    /show more/i,
    /view more/i,
    /expand/i,
    /add another/i,
    /add more/i,
    /add experience/i,
    /add education/i,
    /additional information/i,
    /application questions/i,
    /resume details/i,
    /contact details/i,
    /personal information/i
  ];
  const submitPatterns = finalSubmitPatterns();
  const progressPatterns = stepPatternsForPlatform(platform);
  const controls = page.locator('summary, button[aria-expanded="false"], [role="button"][aria-expanded="false"], button, [role="button"]');
  const count = Math.min(await controls.count().catch(() => 0), 25);
  let revealed = 0;
  const seenTexts = new Set();
  for (let i = 0; i < count; i += 1) {
    const control = controls.nth(i);
    try {
      if (!(await isVisible(control))) continue;
      const disabled = await control.isDisabled().catch(() => false);
      if (disabled) continue;
      const text = shortText(await control.evaluate((node) => {
        const label = node.innerText || node.textContent || node.getAttribute("aria-label") || "";
        return String(label || "").replace(/\s+/g, " ").trim();
      }).catch(() => ""), 120);
      if (!text || seenTexts.has(text)) continue;
      seenTexts.add(text);
      if (submitPatterns.some(pattern => pattern.test(text))) continue;
      if (progressPatterns.some(pattern => pattern.test(text))) continue;
      if (!revealPatterns.some(pattern => pattern.test(text))) continue;
      await control.scrollIntoViewIfNeeded({ timeout: 3000 }).catch(() => {});
      await control.click({ timeout: 3000 }).catch(() => {});
      await page.waitForTimeout(500).catch(() => {});
      revealed += 1;
      record(report.filled_fields, { prompt: `Expanded section`, value: text, kind: "expand" });
      if (revealed >= 4) break;
    } catch (error) {
      // Continue.
    }
  }
  return revealed;
}

async function fillProfileFields(page, task, report) {
  const profile = task.profile || {};
  const name = splitName(profile.full_name);
  const fullAddress = [profile.street_address, profile.suburb, profile.city, profile.region, profile.postcode, profile.country].filter(Boolean).join(", ");

  await fillByLabels(page, [/\bfirst name\b/i, /\bgiven name\b/i], name.first, "first name", report);
  await fillByLabels(page, [/\blast name\b/i, /\bsurname\b/i, /\bfamily name\b/i], name.last, "last name", report);
  await fillByLabels(page, [/\bfull name\b/i, /^name$/i], profile.full_name, "full name", report);
  await fillByLabels(page, [/\bemail\b/i, /\be-mail\b/i], profile.email, "email", report);
  await fillByLabels(page, [/\bphone\b/i, /\bmobile\b/i, /\btelephone\b/i], profile.phone, "phone", report);
  await fillByLabels(page, [/\bstreet address\b/i, /\baddress line 1\b/i, /^\s*address\s*$/i], profile.street_address, "street address", report);
  await fillByLabels(page, [/\bsuburb\b/i, /\bdistrict\b/i, /\baddress line 2\b/i], profile.suburb, "suburb", report);
  await fillByLabels(page, [/^\s*city\s*$/i, /\btown\b/i], profile.city, "city", report);
  await fillByLabels(page, [/\bprovince\b/i, /\bregion\b/i, /\bstate\b/i, /\bcounty\b/i], profile.region, "region", report);
  await fillByLabels(page, [/\bpostcode\b/i, /\bpostal code\b/i, /\bzip\b/i, /\bzip code\b/i], profile.postcode, "postcode", report);
  await fillByLabels(page, [/\bcountry\b/i], profile.country, "country", report);
  await fillByLabels(page, [/\bcurrent location\b/i, /^location$/i, /^\s*city\s*$/i], profile.location, "location", report);
  await fillByLabels(page, [/linkedin/i, /linked in/i], profile.linkedin_url, "linkedin", report);
  await fillByLabels(page, [/\bportfolio\b/i, /\bwebsite\b/i], profile.portfolio_url || profile.linkedin_url, "portfolio/website", report);
  await fillByLabels(page, [/\bcurrent company\b/i, /\bcurrent employer\b/i, /\bemployer\b/i], profile.current_employer, "current employer", report);
  await fillByLabels(page, [/\bcurrent title\b/i, /\bjob title\b/i, /\bcurrent role\b/i], profile.current_job_title, "current job title", report);

  await fillByPlaceholders(page, [/\bemail\b/i, /\be-mail\b/i], profile.email, "email placeholder", report);
  await fillByPlaceholders(page, [/\bphone\b/i, /\bmobile\b/i], profile.phone, "phone placeholder", report);
  await fillByPlaceholders(page, [/linkedin/i], profile.linkedin_url, "linkedin placeholder", report);
  await fillByPlaceholders(page, [/\baddress\b/i], fullAddress || profile.street_address, "address placeholder", report);
  await fillByPlaceholders(page, [/\bcity\b/i], profile.city, "city placeholder", report);
  await fillByPlaceholders(page, [/\bpostcode\b/i, /\bpostal code\b/i, /\bzip\b/i], profile.postcode, "postcode placeholder", report);

  await fillBySelectors(page, [
    'input[name="first_name"]',
    'input[id="first_name"]',
    'input[name="candidate[first_name]"]',
    'input[name="job_application[first_name]"]',
    'input[name*="first" i]',
    'input[id*="first" i]'
  ], name.first, "first name selector", report);
  await fillBySelectors(page, [
    'input[name="last_name"]',
    'input[id="last_name"]',
    'input[name="candidate[last_name]"]',
    'input[name="job_application[last_name]"]',
    'input[name*="last" i]',
    'input[id*="last" i]',
    'input[name*="surname" i]'
  ], name.last, "last name selector", report);
  await fillBySelectors(page, [
    'input[name="name"]',
    'input[id="name"]',
    'input[name="candidate[name]"]',
    'input[name="job_application[name]"]'
  ], profile.full_name, "full name selector", report);
  await fillBySelectors(page, [
    'input[name="email"]',
    'input[id="email"]',
    'input[name="candidate[email]"]',
    'input[name="job_application[email]"]',
    'input[type="email"]',
    'input[name*="email" i]',
    'input[id*="email" i]'
  ], profile.email, "email selector", report);
  await fillBySelectors(page, [
    'input[name="phone"]',
    'input[id="phone"]',
    'input[name="candidate[phone]"]',
    'input[name="job_application[phone]"]',
    'input[type="tel"]',
    'input[name*="phone" i]',
    'input[id*="phone" i]',
    'input[name*="mobile" i]'
  ], profile.phone, "phone selector", report);
  await fillBySelectors(page, [
    'input[name*="linkedin" i]',
    'input[id*="linkedin" i]',
    'input[name*="urls" i]',
    'input[id*="urls" i]'
  ], profile.linkedin_url, "linkedin selector", report);
  await fillBySelectors(page, [
    'input[name*="address" i]',
    'input[id*="address" i]',
    'input[name*="street" i]',
    'input[id*="street" i]'
  ], profile.street_address || fullAddress, "address selector", report);
  await fillBySelectors(page, [
    'input[name*="suburb" i]',
    'input[id*="suburb" i]'
  ], profile.suburb, "suburb selector", report);
  await fillBySelectors(page, [
    'input[name*="city" i]',
    'input[id*="city" i]',
    'input[name*="town" i]',
    'input[id*="town" i]'
  ], profile.city, "city selector", report);
  await fillBySelectors(page, [
    'input[name*="region" i]',
    'input[id*="region" i]',
    'input[name*="province" i]',
    'input[id*="province" i]',
    'input[name*="state" i]',
    'input[id*="state" i]'
  ], profile.region, "region selector", report);
  await fillBySelectors(page, [
    'input[name*="postcode" i]',
    'input[id*="postcode" i]',
    'input[name*="postal" i]',
    'input[id*="postal" i]',
    'input[name*="zip" i]',
    'input[id*="zip" i]'
  ], profile.postcode, "postcode selector", report);
  await fillBySelectors(page, [
    'input[name*="country" i]',
    'input[id*="country" i]'
  ], profile.country, "country selector", report);
  await fillBySelectors(page, [
    'input[name*="employer" i]',
    'input[id*="employer" i]',
    'input[name*="company" i]',
    'input[id*="company" i]'
  ], profile.current_employer, "current employer selector", report);
  await fillBySelectors(page, [
    'input[name*="title" i]',
    'input[id*="title" i]',
    'input[name*="role" i]',
    'input[id*="role" i]'
  ], profile.current_job_title, "current job title selector", report);
  await selectFirstMatchingOption(page, [
    'select[name*="location" i]',
    'select[id*="location" i]',
    'select[name*="country" i]',
    'select[id*="country" i]'
  ], profile.country || "South Africa", "country/location", report);
  await selectFirstMatchingOption(page, [
    'select[name*="region" i]',
    'select[id*="region" i]',
    'select[name*="province" i]',
    'select[id*="province" i]',
    'select[name*="state" i]',
    'select[id*="state" i]'
  ], profile.region || "Western Cape", "region/location", report);
}

function motivationText(task) {
  const app = task.application || {};
  const job = task.job || {};
  const parts = [
    app.company_notes,
    app.research_notes,
    app.answers,
    app.cover_letter,
    `${job.title || ""} at ${job.company || ""}`
  ].filter(Boolean);
  return shortText(parts.join("\n\n"), 900);
}

async function fillTextAreas(page, task, report) {
  const app = task.application || {};
  const profile = task.profile || {};
  const answers = app.answers || "";
  const coverLetter = app.cover_letter || "";
  const whyRole = motivationText(task);

  await fillByLabels(page, ["cover letter", "cover note", "message to hiring", "additional information"], coverLetter, "cover letter", report);
  await fillByLabels(page, ["why.*interested", "why.*role", "why.*company", "why do you want"], whyRole || answers, "questionnaire answers", report);
  await fillByLabels(page, ["salary", "compensation"], profile.salary_expectation, "salary expectation", report);
  await fillByLabels(page, ["notice", "availability", "start date"], profile.availability || profile.notice_period, "availability", report);
  await fillBySelectors(page, [
    'textarea[name*="cover" i]',
    'textarea[id*="cover" i]',
    'textarea[name*="comments" i]',
    'textarea[id*="comments" i]',
    'textarea[name*="message" i]'
  ], coverLetter, "cover letter selector", report);
  await fillBySelectors(page, [
    'input[name*="salary" i]',
    'input[id*="salary" i]',
    'input[name*="compensation" i]',
    'input[id*="compensation" i]'
  ], profile.salary_expectation, "salary selector", report);
  await fillBySelectors(page, [
    'input[name*="available" i]',
    'input[id*="available" i]',
    'input[name*="start" i]',
    'input[id*="start" i]',
    'input[name*="notice" i]',
    'input[id*="notice" i]'
  ], profile.availability || profile.notice_period, "availability selector", report);

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
        record(report.filled_fields, { prompt: "textarea cover letter", value: coverLetter, kind: "textarea" });
      } else if (meta.includes("why") || meta.includes("question") || meta.includes("additional")) {
        const valueToUse = whyRole || answers || coverLetter;
        await area.fill(valueToUse, { timeout: 5000 });
        record(report.filled_fields, { prompt: "textarea answers", value: valueToUse, kind: "textarea" });
      }
    } catch (error) {
      // Leave ambiguous textareas untouched.
    }
  }
}

async function answerCommonScreening(page, task, report) {
  const profile = task.profile || {};
  await chooseRadioOrCheckbox(page, ["prefer not", "decline to self", "i do not wish"], "prefer not to answer", report);
  await fillByLabels(page, ["work authorization", "right to work", "visa"], profile.work_authorization, "work authorization", report);
  await fillByLabels(page, ["salary expectation", "expected salary", "compensation"], profile.salary_expectation, "salary expectation", report);
}

async function scanComboboxFields(page) {
  return page.locator('input[role="combobox"], input[aria-autocomplete], [role="combobox"] input').evaluateAll((nodes) => {
    function clean(value) {
      return String(value || "").replace(/\s+/g, " ").trim();
    }
    function isVisible(node) {
      const style = window.getComputedStyle(node);
      const rect = node.getBoundingClientRect();
      return style.visibility !== "hidden"
        && style.display !== "none"
        && Number(style.opacity || "1") !== 0
        && rect.width > 0
        && rect.height > 0;
    }
    function labelFor(node) {
      const parts = [];
      const id = node.id;
      if (id) {
        document.querySelectorAll(`label[for="${CSS.escape(id)}"]`).forEach(label => parts.push(clean(label.textContent)));
      }
      const closestLabel = node.closest("label");
      if (closestLabel) parts.push(clean(closestLabel.textContent));
      const fieldset = node.closest("fieldset");
      const legend = fieldset ? clean(fieldset.querySelector("legend")?.textContent || "") : "";
      if (legend) parts.push(legend);
      const parentText = clean(node.parentElement?.textContent || "");
      if (parentText && parentText.length < 180) parts.push(parentText);
      parts.push(clean(node.getAttribute("aria-label")));
      parts.push(clean(node.getAttribute("placeholder")));
      return clean(parts.filter(Boolean).join(" | "));
    }
    return nodes.map((node, index) => ({
      index,
      prompt: labelFor(node),
      name: clean(node.getAttribute("name")),
      id: clean(node.id),
      placeholder: clean(node.getAttribute("placeholder")),
      currentValue: clean(node.value || ""),
      required: node.required || clean(node.getAttribute("aria-required")) === "true",
      disabled: node.disabled,
      visible: isVisible(node)
    })).filter(item => item.visible && !item.disabled);
  });
}

async function chooseComboboxOption(page, locator, value, report, prompt, category) {
  const desired = preferredAnswerValue(category, { value });
  if (!desired) return false;
  const variants = Array.from(new Set([
    desired,
    desired.split(",")[0].trim(),
    desired.split(",").slice(0, 2).join(",").trim()
  ].filter(Boolean)));
  await locator.scrollIntoViewIfNeeded({ timeout: 3000 }).catch(() => {});
  await locator.click({ timeout: 3000 }).catch(() => {});
  for (const variant of variants) {
    try {
      await locator.fill("", { timeout: 3000 }).catch(() => {});
      await locator.type(variant, { delay: 35, timeout: 5000 }).catch(() => {});
      await page.waitForTimeout(500).catch(() => {});
      const exactOption = page.getByRole("option", { name: new RegExp(`^${escapeRegExp(variant)}$`, "i") }).first();
      if (await isVisible(exactOption)) {
        await exactOption.click({ timeout: 3000 });
        record(report.filled_fields, { prompt, value: variant, category, kind: "combobox" });
        return true;
      }
      const partialOption = page.getByRole("option", { name: new RegExp(escapeRegExp(variant), "i") }).first();
      if (await isVisible(partialOption)) {
        await partialOption.click({ timeout: 3000 });
        record(report.filled_fields, { prompt, value: variant, category, kind: "combobox" });
        return true;
      }
      await locator.press("ArrowDown").catch(() => {});
      await locator.press("Enter").catch(() => {});
      await page.waitForTimeout(250).catch(() => {});
      const currentValue = await locator.inputValue({ timeout: 1000 }).catch(() => "");
      if (currentValue && currentValue.toLowerCase().includes(variant.toLowerCase().split(",")[0])) {
        record(report.filled_fields, { prompt, value: currentValue, category, kind: "combobox" });
        return true;
      }
    } catch (error) {
      // Continue.
    }
  }
  return false;
}

async function fillComboboxFields(page, task, report) {
  const fields = await scanComboboxFields(page).catch(() => []);
  if (!fields.length) return;
  const locators = page.locator('input[role="combobox"], input[aria-autocomplete], [role="combobox"] input');
  for (const field of fields) {
    const prompt = field.prompt || field.name || field.id || "Combobox";
    const category = classifyField({ ...field, tag: "input", type: "text" });
    if (!category) continue;
    if (String(field.currentValue || "").trim()) continue;
    const answer = answerForCategory(category, field, task);
    const desired = preferredAnswerValue(category, answer);
    if (!desired) continue;
    const locator = locators.nth(field.index);
    try {
      const filled = await chooseComboboxOption(page, locator, desired, report, prompt, category);
      if (filled && answer.review) {
        record(report.review_fields, { prompt, category, value: desired, reason: answer.reason || "Review this combobox selection before submit." });
      } else if (!filled && field.required) {
        record(report.review_fields, { prompt, category, reason: "Could not safely resolve this autocomplete/combobox field." });
      }
    } catch (error) {
      if (field.required) {
        record(report.review_fields, { prompt, category, reason: error.message });
      }
    }
  }
}

async function uploadCv(page, task, report) {
  const cvPath = task.profile && task.profile.cv_path;
  if (!cvPath || !fs.existsSync(cvPath)) {
    record(report.skipped_fields, { prompt: "CV upload", reason: "CV path missing or not found." });
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
        record(report.filled_fields, { prompt: "CV upload", value: path.basename(cvPath), kind: "file" });
        console.log("uploaded CV to file input");
        return;
      }
    } catch (error) {
      record(report.skipped_fields, { prompt: "CV upload", reason: error.message });
    }
  }
  record(report.skipped_fields, { prompt: "CV upload", reason: "No file input found." });
}

async function uploadCoverLetter(page, task, report) {
  const coverLetterPath = task.application && task.application.cover_letter_file_path;
  if (!coverLetterPath || !fs.existsSync(coverLetterPath)) return;
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
      if (meta.includes("cover") || meta.includes("motivation") || meta.includes("supporting")) {
        await input.setInputFiles(coverLetterPath, { timeout: 8000 });
        record(report.filled_fields, { prompt: "Cover letter upload", value: path.basename(coverLetterPath), kind: "file" });
        return;
      }
    } catch (error) {
      record(report.skipped_fields, { prompt: "Cover letter upload", reason: error.message });
    }
  }
}

async function uploadHeadshot(page, task, report) {
  const headshotPath = task.profile && task.profile.headshot_path;
  if (!headshotPath || !fs.existsSync(headshotPath)) return;
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
      if (meta.includes("photo") || meta.includes("headshot") || meta.includes("avatar") || meta.includes("profile")) {
        await input.setInputFiles(headshotPath, { timeout: 8000 });
        record(report.filled_fields, { prompt: "Headshot upload", value: path.basename(headshotPath), kind: "file" });
        return;
      }
    } catch (error) {
      record(report.skipped_fields, { prompt: "Headshot upload", reason: error.message });
    }
  }
}

async function addReviewBanner(page, task) {
  await page.evaluate((data) => {
    const existing = document.getElementById("job-application-ai-review-banner");
    if (existing) existing.remove();
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

async function scanVisibleFields(page) {
  return page.locator("input, textarea, select").evaluateAll((nodes) => {
    function clean(value) {
      return String(value || "").replace(/\s+/g, " ").trim();
    }
    function isVisible(node) {
      const style = window.getComputedStyle(node);
      const rect = node.getBoundingClientRect();
      return style.visibility !== "hidden"
        && style.display !== "none"
        && Number(style.opacity || "1") !== 0
        && rect.width > 0
        && rect.height > 0;
    }
    function labelFor(node) {
      const parts = [];
      const id = node.id;
      if (id) {
        document.querySelectorAll(`label[for="${CSS.escape(id)}"]`).forEach(label => parts.push(clean(label.textContent)));
      }
      const closestLabel = node.closest("label");
      if (closestLabel) parts.push(clean(closestLabel.textContent));
      const fieldset = node.closest("fieldset");
      const legend = fieldset ? clean(fieldset.querySelector("legend")?.textContent || "") : "";
      if (legend) parts.push(legend);
      const parentText = clean(node.parentElement?.textContent || "");
      if (parentText && parentText.length < 180) parts.push(parentText);
      const section = clean(node.closest("section, form, div")?.querySelector("h1, h2, h3, h4")?.textContent || "");
      if (section) parts.push(section);
      parts.push(clean(node.getAttribute("aria-label")));
      parts.push(clean(node.getAttribute("placeholder")));
      return clean(parts.filter(Boolean).join(" | "));
    }
    return nodes.map((node, index) => {
      const tag = node.tagName.toLowerCase();
      const type = tag === "input" ? (node.getAttribute("type") || "text").toLowerCase() : tag;
      const prompt = labelFor(node);
      const options = tag === "select"
        ? Array.from(node.querySelectorAll("option")).map(option => clean(option.textContent || option.value)).filter(Boolean)
        : [];
      const currentValue = tag === "select"
        ? clean(node.options[node.selectedIndex]?.textContent || node.value || "")
        : type === "checkbox" || type === "radio"
          ? (node.checked ? "checked" : "")
          : clean(node.value || "");
      return {
        index,
        tag,
        type,
        name: clean(node.getAttribute("name")),
        id: clean(node.id),
        prompt,
        placeholder: clean(node.getAttribute("placeholder")),
        required: node.required || clean(node.getAttribute("aria-required")) === "true",
        disabled: node.disabled,
        visible: isVisible(node),
        currentValue,
        options
      };
    }).filter(item => item.visible && !item.disabled && item.type !== "hidden");
  });
}

function fieldFingerprint(fields) {
  return fields.map(field => `${field.tag}:${field.type}:${field.name || field.id || ""}:${field.prompt || ""}`).join("|");
}

function isLikelyApplicationField(field) {
  const prompt = `${field.prompt || ""} ${field.name || ""} ${field.id || ""}`.toLowerCase();
  if (/(search|sort by|share this job|filter jobs|location search)/.test(prompt)) return false;
  if (field.tag === "textarea") return true;
  if (field.tag === "select" && field.options && field.options.length > 0 && field.options.length < 50) return true;
  if (field.type === "file" || field.type === "email" || field.type === "tel" || field.type === "date") return true;
  if (/(first name|last name|surname|full name|email|phone|mobile|location|country|linkedin|website|portfolio|cover letter|salary|compensation|availability|start date|notice|work authorization|right to work|visa|resume|cv)/.test(prompt)) return true;
  return false;
}

async function hasVisibleApplicationFields(page) {
  const fields = await scanVisibleFields(page).catch(() => []);
  const relevant = fields.filter(isLikelyApplicationField);
  return {
    hasFields: relevant.length >= 2,
    relevantCount: relevant.length,
    fields: relevant
  };
}

async function waitForRenderableForm(page, platform, report) {
  const maxAttempts = ["ashby", "greenhouse", "lever", "smartrecruiters", "workable", "teamtailor"].includes(platform || "") ? 6 : 3;
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    const visibility = await hasVisibleApplicationFields(page);
    if (visibility.hasFields || visibility.fields.length) return visibility.fields;
    await page.waitForLoadState("domcontentloaded", { timeout: 5000 }).catch(() => {});
    await page.waitForLoadState("networkidle", { timeout: 5000 }).catch(() => {});
    await page.waitForTimeout(1000 + attempt * 400).catch(() => {});
  }
  if (report && ["ashby", "greenhouse", "lever", "smartrecruiters", "workable", "teamtailor"].includes(platform || "")) {
    record(report.review_fields, {
      prompt: "Form render wait",
      reason: "The application page stayed in a loading or blank state during scanning. Retry Prepare form if fields do not appear."
    });
  }
  return [];
}

function classifyField(field) {
  const text = `${field.prompt || ""} ${field.name || ""} ${field.id || ""} ${field.placeholder || ""}`.toLowerCase();
  const normalized = text.replace(/[_-]+/g, " ");
  if (/\b(first name|given name)\b/.test(normalized)) return "first_name";
  if (/\b(last name|surname|family name)\b/.test(normalized)) return "last_name";
  if (/\b(full name|candidate name)\b/.test(normalized) || /^name\b/.test(normalized)) return "full_name";
  if (/\bemail\b/.test(normalized)) return "email";
  if (/\b(phone|mobile|telephone|cell)\b/.test(normalized)) return "phone";
  if (/linkedin/.test(normalized)) return "linkedin";
  if (/\b(portfolio|website|personal site)\b/.test(normalized)) return "website";
  if (/\b(street address|address line 1|address)\b/.test(normalized)) return "street_address";
  if (/\b(suburb|district|address line 2)\b/.test(normalized)) return "suburb";
  if (/\b(current location|location)\b/.test(normalized)) return "location";
  if (/\b(city|town)\b/.test(normalized)) return "city";
  if (/\b(region|province|state|county)\b/.test(normalized)) return "region";
  if (/\b(postcode|postal code|zip|zip code)\b/.test(normalized)) return "postcode";
  if (/\bcountry\b/.test(normalized)) return "country";
  if (/\b(current employer|current company|employer)\b/.test(normalized)) return "current_employer";
  if (/\b(current title|job title|current role)\b/.test(normalized)) return "current_job_title";
  if (field.type === "file" && /\b(cover letter|cover note|motivation letter|supporting statement)\b/.test(normalized)) return "cover_letter_upload";
  if (field.type === "file") return "file_upload";
  if (/\b(cover letter|cover note|message to hiring|additional information|hiring manager message)\b/.test(normalized)) return "cover_letter";
  if (/(why.*(role|company|interested)|motivation|why do you want|why would you like)/.test(normalized)) return "motivation";
  if (/\b(salary|compensation|pay expectation|rate)\b/.test(normalized)) return "salary";
  if (/\b(availability|start date|notice period|when can you start)\b/.test(normalized)) return "availability";
  if (/\b(work authorization|right to work|visa|sponsorship|authorized to work)\b/.test(normalized)) return "work_authorization";
  if (/\breference/.test(normalized)) return "references";
  if (/\b(gender|ethnicity|race|disability|veteran|demographic|sexual orientation)\b/.test(normalized)) return "demographics";
  if (/\b(photo|headshot|avatar|profile picture)\b/.test(normalized)) return "headshot_upload";
  if (/\b(resume|cv|curriculum vitae)\b/.test(normalized)) return "cv_upload";
  if (/\b(how many years|briefly describe|experience do you have|tell us about|share an example)\b/.test(normalized)) return "custom_question";
  return "";
}

function inferArtifactKind(field) {
  const text = `${field.prompt || ""} ${field.name || ""} ${field.id || ""} ${field.placeholder || ""}`.toLowerCase();
  const normalized = text.replace(/[_-]+/g, " ");
  if (/\b(resume|cv|curriculum vitae)\b/.test(normalized)) return "cv_upload";
  if (/\b(photo|headshot|avatar|profile picture)\b/.test(normalized)) return "headshot";
  if (/\b(cover letter|cover note)\b/.test(normalized)) return "cover_letter";
  if (/\b(motivation letter|motivation statement)\b/.test(normalized)) return "motivation_letter";
  if (/\b(supporting statement|personal statement|statement of interest)\b/.test(normalized)) return "supporting_statement";
  if (/\b(questionnaire|application answers|response document|responses)\b/.test(normalized)) return "questionnaire_answers";
  if (/\b(additional information|supporting document)\b/.test(normalized)) return "additional_information";
  return "";
}

function resolveArtifactForField(field, task) {
  const artifacts = task.application?.artifacts || {};
  const inferred = inferArtifactKind(field);
  const candidates = [];
  if (inferred === "cv_upload") {
    candidates.push(["cv_upload", artifacts.cv_upload], ["resume", artifacts.resume], ["cv_upload", task.profile?.cv_path]);
  } else if (inferred === "headshot") {
    candidates.push(["headshot", artifacts.headshot], ["photo", artifacts.photo], ["headshot", task.profile?.headshot_path]);
  } else if (inferred === "cover_letter") {
    candidates.push(["cover_letter", artifacts.cover_letter], ["motivation_letter", artifacts.motivation_letter], ["supporting_statement", artifacts.supporting_statement]);
  } else if (inferred === "motivation_letter") {
    candidates.push(["motivation_letter", artifacts.motivation_letter], ["cover_letter", artifacts.cover_letter], ["supporting_statement", artifacts.supporting_statement]);
  } else if (inferred === "supporting_statement") {
    candidates.push(["supporting_statement", artifacts.supporting_statement], ["additional_information", artifacts.additional_information], ["questionnaire_answers", artifacts.questionnaire_answers], ["cover_letter", artifacts.cover_letter]);
  } else if (inferred === "questionnaire_answers" || inferred === "additional_information") {
    candidates.push(["questionnaire_answers", artifacts.questionnaire_answers], ["additional_information", artifacts.additional_information], ["supporting_statement", artifacts.supporting_statement], ["cover_letter", artifacts.cover_letter]);
  } else {
    candidates.push(["cv_upload", artifacts.cv_upload], ["cover_letter", artifacts.cover_letter], ["supporting_statement", artifacts.supporting_statement], ["questionnaire_answers", artifacts.questionnaire_answers]);
  }
  for (const [kind, artifactPath] of candidates) {
    if (artifactPath && fs.existsSync(artifactPath)) {
      return { kind, path: artifactPath };
    }
  }
  return { kind: inferred || "file_upload", path: "" };
}

function answerForCategory(category, field, task) {
  const profile = task.profile || {};
  const app = task.application || {};
  const name = splitName(profile.full_name);
  const override = findPromptOverride(field, task);
  if (override) {
    return {
      value: override,
      review: true,
      reason: "Saved manual override from the in-app field review."
    };
  }
  if (category === "first_name") return { value: name.first };
  if (category === "last_name") return { value: name.last };
  if (category === "full_name") return { value: profile.full_name };
  if (category === "email") return { value: profile.email };
  if (category === "phone") return { value: profile.phone };
  if (category === "linkedin") return { value: profile.linkedin_url };
  if (category === "website") return { value: profile.portfolio_url || profile.linkedin_url };
  if (category === "street_address") return { value: profile.street_address };
  if (category === "suburb") return { value: profile.suburb };
  if (category === "location") return { value: profile.location };
  if (category === "city") return { value: profile.city };
  if (category === "region") return { value: profile.region };
  if (category === "postcode") return { value: profile.postcode };
  if (category === "country") return { value: profile.country || "South Africa", choice: profile.country || "South Africa" };
  if (category === "current_employer") return { value: profile.current_employer };
  if (category === "current_job_title") return { value: profile.current_job_title };
  if (category === "cover_letter") return { value: app.cover_letter };
  if (category === "motivation") return { value: motivationText(task) };
  if (category === "salary") return { value: profile.salary_expectation };
  if (category === "availability") return { value: profile.availability || profile.notice_period };
  if (category === "references") return { value: profile.references_policy || "Available on request." };
  if (category === "demographics") return { choice: "Prefer not to answer" };
  if (category === "work_authorization") {
    const prompt = `${field.prompt || ""} ${field.name || ""}`.toLowerCase();
    const jobText = `${task.job?.location || ""} ${task.job?.description || ""}`.toLowerCase();
    const sponsorship = /sponsorship|require sponsorship|need sponsorship/.test(prompt);
    const southAfrica = /south africa/.test(prompt) || /south africa|cape town/.test(jobText);
    const unitedKingdom = /\buk\b|united kingdom|britain/.test(prompt) || /\buk\b|united kingdom|london/.test(jobText);
    if (sponsorship && (southAfrica || unitedKingdom)) return { choice: "No", review: true, reason: "Check sponsorship wording before submit." };
    if (!sponsorship && (southAfrica || unitedKingdom)) return { choice: "Yes", value: profile.work_authorization, review: true, reason: "Check right-to-work wording before submit." };
    return { value: profile.work_authorization, review: true, reason: "Legal/work authorization wording needs manual review." };
  }
  if (category === "custom_question") {
    const prompt = `${field.prompt || ""} ${field.name || ""}`.toLowerCase();
    if (/health[, ]+wellness[, ]+and fitness industry/.test(prompt)) {
      return {
        value: field.type === "number"
          ? "0"
          : "0 years of direct full-time marketing work inside a health, wellness, or fitness company. My closest relevant experience is sports coaching, endurance training, and building my own triathlon and gym training app, so I understand the audience and category well even though my formal brand experience is still early-career.",
        review: true,
        reason: "Custom industry-experience answer generated from profile context."
      };
    }
    if (/social media influencers/.test(prompt)) {
      return {
        value: "I do not have direct professional ownership of influencer campaigns yet. My closest experience is producing social content, managing posting calendars, and thinking carefully about audience-brand fit, so I would be honest that influencer execution is an area I am ready to grow into rather than something I have already led end to end.",
        review: true,
        reason: "Custom influencer answer generated from profile context."
      };
    }
    if (/meta ads/.test(prompt)) {
      return {
        value: "I do not have full professional campaign ownership with Meta Ads yet, so I would not overclaim years of direct paid social execution. I do have digital marketing training, Google Analytics exposure, and a strong understanding of targeting, creative testing, and performance thinking, but I would treat this as an honest early-career growth area rather than pretend I have already led a major Meta campaign.",
        review: true,
        reason: "Custom Meta Ads answer generated from profile context."
      };
    }
    return {
      value: app.answers || app.cover_letter || "",
      review: true,
      reason: "General custom question answer; review before submit."
    };
  }
  return { value: "" };
}

function findPromptOverride(field, task) {
  const overrides = task.application?.form_prep_overrides || {};
  if (!overrides || typeof overrides !== "object") return "";
  const candidates = [
    field.prompt,
    shortText(field.prompt || "", 220),
    `${field.prompt || ""} ${field.name || ""}`.trim(),
    field.name,
    field.id
  ].map(normalizePromptKey).filter(Boolean);
  for (const [rawKey, rawValue] of Object.entries(overrides)) {
    const key = normalizePromptKey(rawKey);
    if (!key) continue;
    if (candidates.includes(key) || candidates.some(candidate => candidate && (candidate.startsWith(key) || key.startsWith(candidate)))) {
      return String(rawValue || "");
    }
  }
  return "";
}

async function fillLocatorFromScan(locator, field, answer, report) {
  const choice = answer.choice || answer.value || "";
  if (!choice) return false;
  const prompt = field.prompt || field.name || field.id || "field";
  if (field.tag === "select") {
    const options = await locator.locator("option").evaluateAll(nodes => nodes.map(node => ({
      value: node.value || "",
      text: (node.textContent || "").trim()
    }))).catch(() => []);
    const wanted = String(choice).toLowerCase();
    const match = options.find(option => option.text.toLowerCase() === wanted)
      || options.find(option => option.text.toLowerCase().includes(wanted))
      || options.find(option => option.value.toLowerCase().includes(wanted));
    if (!match) return false;
    await locator.selectOption(match.value || { label: match.text }, { timeout: 5000 });
    record(report.filled_fields, { prompt, value: match.text || match.value, category: answer.category, kind: "select" });
    return true;
  }
  if (field.type === "checkbox" || field.type === "radio") {
    const wanted = String(choice).toLowerCase();
    const promptText = `${field.prompt || ""} ${field.name || ""}`.toLowerCase();
    if ((wanted.includes("prefer not") && promptText.includes("prefer not")) || (wanted === "yes" && promptText.includes("yes")) || (wanted === "no" && promptText.includes("no"))) {
      await locator.check({ timeout: 5000 });
      record(report.filled_fields, { prompt, value: choice, category: answer.category, kind: field.type });
      return true;
    }
    return false;
  }
  if (field.type === "date" && /^\d{4}-\d{2}-\d{2}$/.test(String(answer.value || ""))) {
    await locator.fill(String(answer.value), { timeout: 5000 });
    record(report.filled_fields, { prompt, value: answer.value, category: answer.category, kind: "date" });
    return true;
  }
  if (!String(answer.value || "").trim()) return false;
  await locator.fill(String(answer.value), { timeout: 5000 });
  record(report.filled_fields, { prompt, value: answer.value, category: answer.category, kind: field.tag });
  return true;
}

async function fillScannedFields(page, task, report, stepLabel = "step-1") {
  let fields = await scanVisibleFields(page);
  if (!fields.length) {
    fields = await waitForRenderableForm(page, report.platform || "", report);
  }
  const scanned = fields.map(field => ({
    prompt: shortText(field.prompt || field.name || field.id || "", 220),
    type: field.type,
    tag: field.tag,
    category: classifyField(field),
    required: Boolean(field.required),
    step: stepLabel,
    options: (field.options || []).slice(0, 8)
  }));
  report.scanned_fields.push(...scanned);
  report.step_history.push({
    step: stepLabel,
    url: page.url(),
    field_count: fields.length,
    required_count: fields.filter(field => field.required).length
  });
  const allLocators = page.locator("input, textarea, select");

  for (const field of fields) {
    const prompt = field.prompt || field.name || field.id || "Unnamed field";
    const category = classifyField(field);
    if (category === "cv_upload") {
      try {
        const locator = allLocators.nth(field.index);
        const cvPath = task.profile && task.profile.cv_path;
        if (cvPath && fs.existsSync(cvPath)) {
          await locator.setInputFiles(cvPath, { timeout: 8000 });
          record(report.filled_fields, { prompt, value: path.basename(cvPath), category, kind: "file" });
        } else {
          record(report.review_fields, { prompt, category, reason: "CV path was not available for this upload field." });
        }
      } catch (error) {
        record(report.review_fields, { prompt, category, reason: error.message });
      }
      continue;
    }
    if (category === "headshot_upload") {
      try {
        const locator = allLocators.nth(field.index);
        const headshotPath = task.profile && task.profile.headshot_path;
        if (headshotPath && fs.existsSync(headshotPath)) {
          await locator.setInputFiles(headshotPath, { timeout: 8000 });
          record(report.filled_fields, { prompt, value: path.basename(headshotPath), category, kind: "file" });
        } else {
          record(report.review_fields, { prompt, category, reason: "Headshot path was not available for this upload field." });
        }
      } catch (error) {
        record(report.review_fields, { prompt, category, reason: error.message });
      }
      continue;
    }
    if (category === "cover_letter_upload") {
      try {
        const locator = allLocators.nth(field.index);
        const coverLetterPath = task.application && task.application.cover_letter_file_path;
        if (coverLetterPath && fs.existsSync(coverLetterPath)) {
          await locator.setInputFiles(coverLetterPath, { timeout: 8000 });
          record(report.filled_fields, { prompt, value: path.basename(coverLetterPath), category, kind: "file" });
        } else {
          record(report.review_fields, { prompt, category, reason: "Cover-letter file path was not available for this upload field." });
        }
      } catch (error) {
        record(report.review_fields, { prompt, category, reason: error.message });
      }
      continue;
    }
    if (category === "file_upload") {
      try {
        const locator = allLocators.nth(field.index);
        const artifact = resolveArtifactForField(field, task);
        if (artifact.path) {
          await locator.setInputFiles(artifact.path, { timeout: 8000 });
          record(report.filled_fields, { prompt, value: path.basename(artifact.path), category: artifact.kind, kind: "file" });
        } else if (field.required) {
          record(report.review_fields, {
            prompt,
            category,
            reason: "This file upload asks for a document type that is not generated yet. Review and upload manually."
          });
        } else {
          record(report.skipped_fields, { prompt, category, reason: "Optional file upload without a safe matching artifact." });
        }
      } catch (error) {
        record(report.review_fields, { prompt, category, reason: error.message });
      }
      continue;
    }
    if (!category) continue;
    const currentValue = String(field.currentValue || "").trim();
    const looksLikeBadPrefill = Boolean(
      currentValue
      && category === "custom_question"
      && currentValue.toLowerCase() === String(task.profile?.location || "").trim().toLowerCase()
    );
    if (currentValue && !looksLikeBadPrefill) continue;
    const locator = allLocators.nth(field.index);
    const answer = answerForCategory(category, field, task);
    answer.category = category;
    try {
      if (looksLikeBadPrefill) {
        await locator.fill("", { timeout: 3000 }).catch(() => {});
      }
      const filled = await fillLocatorFromScan(locator, field, answer, report);
      if (filled) {
        if (answer.review) {
          record(report.review_fields, { prompt, category, value: answer.choice || answer.value, reason: answer.reason || "Review this answer before submit." });
        }
      } else if (field.required) {
        record(report.review_fields, {
          prompt,
          category,
          reason: answer.reason || `Could not safely fill this required ${category.replace(/_/g, " ")} field.`
        });
      } else {
        record(report.skipped_fields, { prompt, category, reason: "No safe automatic answer." });
      }
    } catch (error) {
      if (field.required) {
        record(report.review_fields, { prompt, category, reason: error.message });
      } else {
        record(report.skipped_fields, { prompt, category, reason: error.message });
      }
    }
  }
  return fields;
}

async function isVisible(locator) {
  try {
    return await locator.isVisible({ timeout: 1500 });
  } catch (error) {
    return false;
  }
}

function persistReport(task, report) {
  if (!task.report_path) return;
  ensureDir(task.report_path);
  fs.writeFileSync(task.report_path, JSON.stringify(report, null, 2), "utf8");
}

function cooldownHoursForBlocker(platform, url = "") {
  const host = hostFromUrl(url);
  const key = String(platform || "").toLowerCase();
  if (host.endsWith("smartrecruiters.com") || key === "smartrecruiters") return 12;
  if (host.endsWith("myworkdayjobs.com") || key === "workday") return 12;
  return 6;
}

function shouldHoldBrowserOpen(report) {
  return !["blocked-domain"].includes(String(report?.status || ""));
}

async function detectBlocker(page) {
  const bodyText = shortText(await page.locator("body").innerText().catch(() => ""), 3000).toLowerCase();
  if (/access is temporarily restricted|detected unusual activity|automated \(bot\) activity|use of developer or inspection tools|rapid taps or clicks/.test(bodyText)) {
    return {
      kind: "platform-restriction",
      message: "The ATS restricted access after detecting unusual or automated activity.",
      url: page.url(),
      cooldown_hours: cooldownHoursForBlocker("", page.url())
    };
  }
  const recaptcha = await page.locator('iframe[src*="recaptcha"], iframe[title*="captcha" i], iframe[src*="hcaptcha"]').count().catch(() => 0);
  if (recaptcha || /verify you are human|security check|unusual traffic|robot|captcha/.test(bodyText)) {
    return {
      kind: "captcha",
      message: "Security check or CAPTCHA is visible.",
      url: page.url()
    };
  }
  const otpInputCount = await page.locator('input[name*="code" i], input[id*="code" i], input[autocomplete="one-time-code"]').count().catch(() => 0);
  if (otpInputCount || /verification code|authentication code|two-factor|two factor|multi-factor|enter the code|one-time passcode/.test(bodyText)) {
    return {
      kind: "mfa",
      message: "A verification code or multi-factor prompt is visible.",
      url: page.url()
    };
  }
  return null;
}

async function waitForManualClearance(page, task, report, blocker) {
  if (blocker.kind === "platform-restriction") {
    const cooldownHours = Number(blocker.cooldown_hours || cooldownHoursForBlocker(report.platform || "", blocker.url || page.url()));
    const blockedUntil = new Date(Date.now() + cooldownHours * 60 * 60 * 1000).toISOString();
    report.status = "blocked-domain";
    report.blocker = {
      kind: blocker.kind,
      message: blocker.message,
      url: blocker.url || page.url(),
      detected_at: report.blocker?.detected_at || nowIso(),
      last_seen_at: nowIso(),
      blocked_until: blockedUntil,
      cooldown_hours: cooldownHours
    };
    record(report.review_fields, {
      prompt: "ATS restriction page",
      reason: `${blocker.message} Cooldown set until ${blockedUntil}. Retry later and avoid rapid repeated attempts on this ATS.`
    });
    persistReport(task, report);
    return false;
  }
  report.status = "waiting-user-action";
  report.blocker = {
    kind: blocker.kind,
    message: blocker.message,
    url: blocker.url || page.url(),
    detected_at: report.blocker?.detected_at || nowIso(),
    last_seen_at: nowIso()
  };
  persistReport(task, report);
  const started = Date.now();
  const timeoutMs = 20 * 60 * 1000;
  while (Date.now() - started < timeoutMs) {
    await page.waitForTimeout(4000);
    pushUnique(report.visited_urls, page.url());
    const current = await detectBlocker(page);
    if (!current) {
      report.blocker.cleared_at = nowIso();
      report.status = "resuming";
      persistReport(task, report);
      return true;
    }
    report.blocker.last_seen_at = nowIso();
    report.blocker.url = page.url();
    persistReport(task, report);
  }
  record(report.review_fields, {
    prompt: `Manual ${blocker.kind}`,
    reason: `The ${blocker.kind} prompt stayed visible for more than 20 minutes. Clear it manually, then use Resume form if needed.`
  });
  report.status = "waiting-user-action";
  persistReport(task, report);
  return false;
}

async function resolveBlockerIfPresent(page, task, report) {
  const blocker = await detectBlocker(page);
  if (!blocker) return true;
  const formVisibility = await hasVisibleApplicationFields(page);
  if (formVisibility.hasFields) {
    record(report.review_fields, {
      prompt: `Visible ${blocker.kind}`,
      reason: `${blocker.message} The form fields are already visible, so the assistant will keep filling and leave the challenge for your review.`
    });
    report.blocker = {
      kind: blocker.kind,
      message: blocker.message,
      url: blocker.url || page.url(),
      detected_at: report.blocker?.detected_at || nowIso(),
      last_seen_at: nowIso(),
      mode: "visible-with-form"
    };
    return true;
  }
  return waitForManualClearance(page, task, report, blocker);
}

async function preLoginIfConfigured(page, task, report, platform) {
  const credential = task.site_credential || {};
  if (!credential.login_url || !credential.password_set) return false;
  if (!["linkedin", "indeed"].includes(platform)) return false;
  if (report.login.prelogin_attempted) return false;
  report.login.prelogin_attempted = true;
  report.login.status = "prelogin";
  report.login.login_url = credential.login_url;
  await page.goto(credential.login_url, { waitUntil: "domcontentloaded", timeout: 45000 });
  pushUnique(report.visited_urls, page.url());
  if (!(await resolveBlockerIfPresent(page, task, report))) return false;
  const passwordField = page.locator('input[type="password"]').first();
  if (!(await isVisible(passwordField))) {
    report.login.status = "session-reused";
    report.login.result_url = page.url();
  } else {
    await attemptLoginIfNeeded(page, task, report);
  }
  await page.goto(task.job.url, { waitUntil: "domcontentloaded", timeout: 45000 });
  pushUnique(report.visited_urls, page.url());
  return true;
}

async function attemptLoginIfNeeded(page, task, report) {
  const credential = task.site_credential || {};
  const passwordField = page.locator('input[type="password"]').first();
  if (!(await isVisible(passwordField))) {
    if (!credential.password_set) report.login = { status: "session-only", username: credential.username || "" };
    return false;
  }
  const password = readKeychainPassword(credential);
  if (!password) {
    report.login = {
      status: credential.username ? "password-missing" : "no-credentials",
      username: credential.username || "",
      login_url: page.url()
    };
    record(report.review_fields, { prompt: "Login", reason: "Password field is visible but no Keychain password is saved for this site." });
    return false;
  }

  report.login = { status: "attempted", username: credential.username || "", login_url: page.url() };
  const username = credential.username || task.profile?.email || "";
  await fillByLabels(page, ["email", "username", "login"], username, "login username", report);
  await fillByPlaceholders(page, ["email", "username"], username, "login username placeholder", report);
  await fillBySelectors(page, [
    'input[type="email"]',
    'input[name*="email" i]',
    'input[id*="email" i]',
    'input[name*="user" i]',
    'input[id*="user" i]',
    'input[name*="login" i]'
  ], username, "login username selector", report);
  await passwordField.scrollIntoViewIfNeeded({ timeout: 3000 }).catch(() => {});
  await passwordField.fill(password, { timeout: 5000 });
  record(report.filled_fields, { prompt: "login password", value: "[saved in Keychain]", kind: "login" });

  const buttons = [
    /sign in/i,
    /log in/i,
    /continue/i,
    /next/i,
    /submit/i
  ];
  let clicked = false;
  for (const name of buttons) {
    try {
      const button = page.getByRole("button", { name }).first();
      if (await button.count()) {
        await button.click({ timeout: 5000 });
        clicked = true;
        break;
      }
    } catch (error) {
      // Continue.
    }
  }
  if (!clicked) {
    await passwordField.press("Enter").catch(() => {});
  }

  await page.waitForLoadState("domcontentloaded", { timeout: 12000 }).catch(() => {});
  await page.waitForTimeout(2000);
  pushUnique(report.visited_urls, page.url());
  const blockerCleared = await resolveBlockerIfPresent(page, task, report);
  if (!blockerCleared) {
    report.login.status = "waiting-user-action";
    return false;
  }
  const stillOnPassword = await isVisible(passwordField);
  report.login.status = stillOnPassword ? "needs-review" : "success";
  report.login.result_url = page.url();
  if (stillOnPassword) {
    record(report.review_fields, { prompt: "Login", reason: "Password field is still visible. MFA, CAPTCHA, or manual review may be required." });
  }
  return !stillOnPassword;
}

async function clickSafeContinue(page, report, platform) {
  const progressPatterns = stepPatternsForPlatform(platform);
  const submitPatterns = finalSubmitPatterns();
  const controls = page.locator('button, input[type="submit"], input[type="button"]');
  const count = await controls.count().catch(() => 0);
  for (let i = 0; i < count; i += 1) {
    const control = controls.nth(i);
    try {
      if (!(await isVisible(control))) continue;
      const disabled = await control.isDisabled().catch(() => false);
      if (disabled) continue;
      const text = shortText(await control.evaluate((node) => {
        const label = node.innerText || node.textContent || node.value || node.getAttribute("aria-label") || "";
        return String(label || "").replace(/\s+/g, " ").trim();
      }).catch(() => ""));
      if (!text) continue;
      if (submitPatterns.some(pattern => pattern.test(text))) continue;
      if (!progressPatterns.some(pattern => pattern.test(text))) continue;
      await control.scrollIntoViewIfNeeded({ timeout: 3000 }).catch(() => {});
      await control.click({ timeout: 5000 });
      await page.waitForLoadState("domcontentloaded", { timeout: 12000 }).catch(() => {});
      await page.waitForTimeout(1200);
      pushUnique(report.visited_urls, page.url());
      report.step_history.push({
        step: `advance:${report.step_history.length + 1}`,
        url: page.url(),
        action: text
      });
      return text;
    } catch (error) {
      // Continue.
    }
  }
  return "";
}

async function fillCurrentStep(page, task, report, stepLabel) {
  await revealExpandableSections(page, report, report.platform || "");
  await fillProfileFields(page, task, report);
  await uploadCv(page, task, report);
  await uploadCoverLetter(page, task, report);
  await uploadHeadshot(page, task, report);
  await fillTextAreas(page, task, report);
  await answerCommonScreening(page, task, report);
  await fillComboboxFields(page, task, report);
  let fields = await fillScannedFields(page, task, report, stepLabel);
  if (!fields.length && !report.clicked_apply && ["ashby", "greenhouse", "lever", "smartrecruiters", "workable", "teamtailor"].includes(report.platform || "")) {
    page = await clickApplyIfPresent(page, report, report.platform || "");
    await revealExpandableSections(page, report, report.platform || "");
    await fillProfileFields(page, task, report);
    await uploadCv(page, task, report);
    await uploadCoverLetter(page, task, report);
    await uploadHeadshot(page, task, report);
    await fillTextAreas(page, task, report);
    await answerCommonScreening(page, task, report);
    await fillComboboxFields(page, task, report);
    fields = await fillScannedFields(page, task, report, `${stepLabel}-after-apply`);
  }
  return { page, fields };
}

async function saveArtifacts(page, task, report) {
  report.last_url = page.url();
  report.finished_at = new Date().toISOString();
  if (!["waiting-user-action", "resuming"].includes(report.status)) {
    report.status = report.errors.length
      ? "needs-review"
      : report.review_fields.length
        ? "review-required"
        : "ready-for-review";
  }
  if (task.screenshot_path) {
    ensureDir(task.screenshot_path);
    await page.screenshot({ path: task.screenshot_path, fullPage: true }).catch((error) => {
      report.errors.push(`Screenshot failed: ${error.message}`);
    });
  }
  persistReport(task, report);
}

async function saveSessionState(context, statePath, report) {
  if (!statePath) return;
  try {
    ensureDir(statePath);
    await context.storageState({ path: statePath });
  } catch (error) {
    if (report) report.errors.push(`Could not save browser session state: ${error.message}`);
  }
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

  const report = {
    created_at: task.created_at || new Date().toISOString(),
    task_path: taskPath,
    platform: inferPlatform(task),
    status: "started",
    browser: {},
    clicked_apply: false,
    visited_urls: [],
    login: { status: "not-attempted" },
    blocker: {},
    scanned_fields: [],
    step_history: [],
    filled_fields: [],
    skipped_fields: [],
    review_fields: [],
    errors: []
  };

  const dataDir = path.dirname(path.dirname(taskPath));
  const statePath = path.join(dataDir, "playwright-storage-state.json");
  const browser = await launchBestBrowser(report);
  const context = await browser.newContext({
    viewport: { width: 1380, height: 920 },
    acceptDownloads: true,
    storageState: fs.existsSync(statePath) ? statePath : undefined
  });
  let page = await context.newPage();
  page.setDefaultTimeout(7000);

  try {
    const platform = inferPlatform(task, task.job.url);
    console.log(`opening ${task.job.url}`);
    await preLoginIfConfigured(page, task, report, platform);
    if (report.status === "waiting-user-action") {
      await saveSessionState(context, statePath, report);
      await addReviewBanner(page, task).catch(() => {});
      await saveArtifacts(page, task, report);
      if (shouldHoldBrowserOpen(report)) await page.waitForTimeout(24 * 60 * 60 * 1000);
      return;
    }
    await page.goto(task.job.url, { waitUntil: "domcontentloaded", timeout: 45000 });
    pushUnique(report.visited_urls, page.url());
    if (!(await resolveBlockerIfPresent(page, task, report))) {
      await saveSessionState(context, statePath, report);
      await addReviewBanner(page, task).catch(() => {});
      await saveArtifacts(page, task, report);
      if (shouldHoldBrowserOpen(report)) await page.waitForTimeout(24 * 60 * 60 * 1000);
      return;
    }
    await attemptLoginIfNeeded(page, task, report);
    await saveSessionState(context, statePath, report);
    if (!(await resolveBlockerIfPresent(page, task, report))) {
      await saveSessionState(context, statePath, report);
      await addReviewBanner(page, task).catch(() => {});
      await saveArtifacts(page, task, report);
      if (shouldHoldBrowserOpen(report)) await page.waitForTimeout(24 * 60 * 60 * 1000);
      return;
    }
    page = await clickApplyIfPresent(page, report, platform);
    await saveSessionState(context, statePath, report);
    if (!(await resolveBlockerIfPresent(page, task, report))) {
      await saveSessionState(context, statePath, report);
      await addReviewBanner(page, task).catch(() => {});
      await saveArtifacts(page, task, report);
      if (shouldHoldBrowserOpen(report)) await page.waitForTimeout(24 * 60 * 60 * 1000);
      return;
    }
    await attemptLoginIfNeeded(page, task, report);
    await saveSessionState(context, statePath, report);
    let lastFingerprint = "";
    for (let step = 1; step <= 6; step += 1) {
      const stepResult = await fillCurrentStep(page, task, report, `step-${step}`);
      page = stepResult.page;
      const fields = stepResult.fields;
      if (!(await resolveBlockerIfPresent(page, task, report))) {
        await saveSessionState(context, statePath, report);
        await addReviewBanner(page, task).catch(() => {});
        await saveArtifacts(page, task, report);
        if (shouldHoldBrowserOpen(report)) await page.waitForTimeout(24 * 60 * 60 * 1000);
        return;
      }
      const fingerprint = fieldFingerprint(fields);
      if (fingerprint && fingerprint === lastFingerprint) break;
      lastFingerprint = fingerprint;
      const advancedWith = await clickSafeContinue(page, report, platform);
      if (!advancedWith) break;
      if (!(await resolveBlockerIfPresent(page, task, report))) {
        await saveSessionState(context, statePath, report);
        await addReviewBanner(page, task).catch(() => {});
        await saveArtifacts(page, task, report);
        if (shouldHoldBrowserOpen(report)) await page.waitForTimeout(24 * 60 * 60 * 1000);
        return;
      }
      await attemptLoginIfNeeded(page, task, report);
      await saveSessionState(context, statePath, report);
    }
    await saveSessionState(context, statePath, report);
    await addReviewBanner(page, task).catch(() => {});
    await saveArtifacts(page, task, report);
    console.log("Form preparation complete. Review manually and submit yourself. Close the browser when done.");
    if (shouldHoldBrowserOpen(report)) await page.waitForTimeout(24 * 60 * 60 * 1000);
  } catch (error) {
    report.errors.push(error.stack || error.message);
    await saveSessionState(context, statePath, report).catch(() => {});
    await saveArtifacts(page, task, report).catch(() => {});
    throw error;
  } finally {
    await browser.close().catch(() => {});
  }
}

main().catch((error) => {
  console.error(error.stack || error.message);
  process.exit(1);
});
