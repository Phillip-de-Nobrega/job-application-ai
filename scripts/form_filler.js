#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");
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

function shortText(value, limit = 160) {
  const clean = String(value || "").replace(/\s+/g, " ").trim();
  if (!clean) return "";
  return clean.length > limit ? `${clean.slice(0, limit - 1)}...` : clean;
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

async function fillByLabels(page, labels, value, label, report) {
  for (const text of labels) {
    if (await fillFirst(page.getByLabel(new RegExp(text, "i")), value, label, report)) return true;
  }
  return false;
}

async function fillByPlaceholders(page, placeholders, value, label, report) {
  for (const text of placeholders) {
    if (await fillFirst(page.getByPlaceholder(new RegExp(text, "i")), value, label, report)) return true;
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

async function clickApplyIfPresent(page, report, platform) {
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
        await button.scrollIntoViewIfNeeded({ timeout: 3000 }).catch(() => {});
        await button.click({ timeout: 5000 });
        await page.waitForLoadState("domcontentloaded", { timeout: 10000 }).catch(() => {});
        report.clicked_apply = true;
        pushUnique(report.visited_urls, page.url());
        console.log("clicked apply/start button");
        return true;
      }
    } catch (error) {
      // Continue.
    }
    try {
      const link = page.getByRole("link", { name }).first();
      if (await link.count()) {
        await link.scrollIntoViewIfNeeded({ timeout: 3000 }).catch(() => {});
        await link.click({ timeout: 5000 });
        await page.waitForLoadState("domcontentloaded", { timeout: 10000 }).catch(() => {});
        report.clicked_apply = true;
        pushUnique(report.visited_urls, page.url());
        console.log("clicked apply/start link");
        return true;
      }
    } catch (error) {
      // Continue.
    }
  }
  return false;
}

async function fillProfileFields(page, task, report) {
  const profile = task.profile || {};
  const name = splitName(profile.full_name);

  await fillByLabels(page, ["first name", "given name"], name.first, "first name", report);
  await fillByLabels(page, ["last name", "surname", "family name"], name.last, "last name", report);
  await fillByLabels(page, ["full name", "^name$"], profile.full_name, "full name", report);
  await fillByLabels(page, ["email", "e-mail"], profile.email, "email", report);
  await fillByLabels(page, ["phone", "mobile", "telephone"], profile.phone, "phone", report);
  await fillByLabels(page, ["location", "city", "current location"], profile.location, "location", report);
  await fillByLabels(page, ["linkedin", "linked in"], profile.linkedin_url, "linkedin", report);
  await fillByLabels(page, ["portfolio", "website"], profile.portfolio_url || profile.linkedin_url, "portfolio/website", report);

  await fillByPlaceholders(page, ["email", "e-mail"], profile.email, "email placeholder", report);
  await fillByPlaceholders(page, ["phone", "mobile"], profile.phone, "phone placeholder", report);
  await fillByPlaceholders(page, ["linkedin"], profile.linkedin_url, "linkedin placeholder", report);

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
  await selectFirstMatchingOption(page, [
    'select[name*="location" i]',
    'select[id*="location" i]',
    'select[name*="country" i]',
    'select[id*="country" i]'
  ], "South Africa", "country/location", report);
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

function classifyField(field) {
  const text = `${field.prompt || ""} ${field.name || ""} ${field.id || ""} ${field.placeholder || ""}`.toLowerCase();
  if (/(first name|given name)/.test(text)) return "first_name";
  if (/(last name|surname|family name)/.test(text)) return "last_name";
  if (/(full name|^name$|candidate name)/.test(text)) return "full_name";
  if (/(email|e-mail)/.test(text)) return "email";
  if (/(phone|mobile|telephone|cell)/.test(text)) return "phone";
  if (/linkedin/.test(text)) return "linkedin";
  if (/(portfolio|website|personal site)/.test(text)) return "website";
  if (/(current location|location|city|town|where are you based)/.test(text)) return "location";
  if (/country/.test(text)) return "country";
  if (/(cover letter|cover note|message to hiring|additional information)/.test(text)) return "cover_letter";
  if (/(why.*(role|company|interested)|motivation|why do you want|why would you like)/.test(text)) return "motivation";
  if (/(salary|compensation|pay expectation|rate)/.test(text)) return "salary";
  if (/(availability|start date|notice period|when can you start)/.test(text)) return "availability";
  if (/(work authorization|right to work|visa|sponsorship|authorized to work)/.test(text)) return "work_authorization";
  if (/reference/.test(text)) return "references";
  if (/(gender|ethnicity|race|disability|veteran|demographic|sexual orientation)/.test(text)) return "demographics";
  if (/(resume|cv|curriculum vitae)/.test(text)) return "cv_upload";
  return "";
}

function answerForCategory(category, field, task) {
  const profile = task.profile || {};
  const app = task.application || {};
  const name = splitName(profile.full_name);
  if (category === "first_name") return { value: name.first };
  if (category === "last_name") return { value: name.last };
  if (category === "full_name") return { value: profile.full_name };
  if (category === "email") return { value: profile.email };
  if (category === "phone") return { value: profile.phone };
  if (category === "linkedin") return { value: profile.linkedin_url };
  if (category === "website") return { value: profile.portfolio_url || profile.linkedin_url };
  if (category === "location") return { value: profile.location };
  if (category === "country") return { value: "South Africa", choice: "South Africa" };
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
  return { value: "" };
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
  const fields = await scanVisibleFields(page);
  const scanned = fields.map(field => ({
    prompt: shortText(field.prompt || field.name || field.id || "", 220),
    type: field.type,
    tag: field.tag,
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
    if (!category || category === "cv_upload") continue;
    if (field.currentValue) continue;
    const locator = allLocators.nth(field.index);
    const answer = answerForCategory(category, field, task);
    answer.category = category;
    try {
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

async function detectBlocker(page) {
  const bodyText = shortText(await page.locator("body").innerText().catch(() => ""), 3000).toLowerCase();
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
  await fillProfileFields(page, task, report);
  await uploadCv(page, task, report);
  await fillTextAreas(page, task, report);
  await answerCommonScreening(page, task, report);
  return fillScannedFields(page, task, report, stepLabel);
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

  try {
    const platform = inferPlatform(task, task.job.url);
    console.log(`opening ${task.job.url}`);
    await preLoginIfConfigured(page, task, report, platform);
    if (report.status === "waiting-user-action") {
      await addReviewBanner(page, task).catch(() => {});
      await saveArtifacts(page, task, report);
      await page.waitForTimeout(24 * 60 * 60 * 1000);
      return;
    }
    await page.goto(task.job.url, { waitUntil: "domcontentloaded", timeout: 45000 });
    pushUnique(report.visited_urls, page.url());
    if (!(await resolveBlockerIfPresent(page, task, report))) {
      await addReviewBanner(page, task).catch(() => {});
      await saveArtifacts(page, task, report);
      await page.waitForTimeout(24 * 60 * 60 * 1000);
      return;
    }
    await attemptLoginIfNeeded(page, task, report);
    if (!(await resolveBlockerIfPresent(page, task, report))) {
      await addReviewBanner(page, task).catch(() => {});
      await saveArtifacts(page, task, report);
      await page.waitForTimeout(24 * 60 * 60 * 1000);
      return;
    }
    await clickApplyIfPresent(page, report, platform);
    if (!(await resolveBlockerIfPresent(page, task, report))) {
      await addReviewBanner(page, task).catch(() => {});
      await saveArtifacts(page, task, report);
      await page.waitForTimeout(24 * 60 * 60 * 1000);
      return;
    }
    await attemptLoginIfNeeded(page, task, report);
    let lastFingerprint = "";
    for (let step = 1; step <= 4; step += 1) {
      const fields = await fillCurrentStep(page, task, report, `step-${step}`);
      if (!(await resolveBlockerIfPresent(page, task, report))) {
        await addReviewBanner(page, task).catch(() => {});
        await saveArtifacts(page, task, report);
        await page.waitForTimeout(24 * 60 * 60 * 1000);
        return;
      }
      const fingerprint = fieldFingerprint(fields);
      if (fingerprint && fingerprint === lastFingerprint) break;
      lastFingerprint = fingerprint;
      const advancedWith = await clickSafeContinue(page, report, platform);
      if (!advancedWith) break;
      if (!(await resolveBlockerIfPresent(page, task, report))) {
        await addReviewBanner(page, task).catch(() => {});
        await saveArtifacts(page, task, report);
        await page.waitForTimeout(24 * 60 * 60 * 1000);
        return;
      }
      await attemptLoginIfNeeded(page, task, report);
    }
    await addReviewBanner(page, task).catch(() => {});
    await saveArtifacts(page, task, report);
    console.log("Form preparation complete. Review manually and submit yourself. Close the browser when done.");
    await page.waitForTimeout(24 * 60 * 60 * 1000);
  } catch (error) {
    report.errors.push(error.stack || error.message);
    await saveArtifacts(page, task, report).catch(() => {});
    throw error;
  }
}

main().catch((error) => {
  console.error(error.stack || error.message);
  process.exit(1);
});
