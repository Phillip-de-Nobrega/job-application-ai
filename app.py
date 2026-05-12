#!/usr/bin/env python3
"""
Local-first job application assistant.

This app deliberately keeps application submission supervised. It drafts, tracks,
and prepares materials, but it does not bypass platform controls or submit final
applications on the user's behalf.
"""

from __future__ import annotations

import datetime as dt
import base64
import imaplib
import html
import json
import os
import re
import shutil
import smtplib
import ssl
import sqlite3
import subprocess
import sys
import threading
import textwrap
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
import zlib
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import parseaddr, parsedate_to_datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "documents"
TASK_DIR = DATA_DIR / "form_tasks"
LOG_DIR = DATA_DIR / "logs"
SMOKE_DIR = DATA_DIR / "smoke"
FORM_PREP_DIR = DATA_DIR / "form_prep"
REMINDERS_DIR = DATA_DIR / "reminders"
NOTIFIED_REMINDERS_PATH = REMINDERS_DIR / "notified-reminders.json"
DB_PATH = DATA_DIR / "job_application_ai.sqlite3"
ENV_PATH = ROOT / ".env"
SESSION_MEMORY_PATH = ROOT / "SESSION_MEMORY.md"
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", os.environ.get("JOB_AI_PORT", "8765")))
DISCOVERY_CHECK_SECONDS = 600
AUTH_PASSWORD = os.environ.get("JOB_AI_PASSWORD", "")

CV_PATH = os.environ.get("JOB_AI_CV_PATH", "/Users/phillip/Desktop/PHILLIP PERSONAL/Phillip_de_Nobrega_CV.pdf")


DEFAULT_PROFILE: dict[str, str] = {
    "full_name": "Phillip de Nobrega",
    "email": "Phillip2002@mweb.co.za",
    "phone": "+27 71 643 0185",
    "location": "Cape Town, South Africa",
    "street_address": "4 Hauptville Circle",
    "suburb": "Constantia",
    "city": "Cape Town",
    "region": "Western Cape",
    "postcode": "7806",
    "country": "South Africa",
    "headshot_path": "",
    "current_employer": "",
    "current_job_title": "",
    "drivers_license": "",
    "cv_path": CV_PATH,
    "cv_text": "",
    "portfolio_url": "",
    "linkedin_url": "https://linkedin.com/in/phillip-de-nobrega-87542b353",
    "target_roles": "Early-career marketing roles, especially graduate, junior, assistant, coordinator, associate, executive, specialist, content, brand, social media, growth, partnerships, community, and campaign roles. Avoid managerial, director, head-of, VP, or other leadership roles unless Phillip explicitly approves them.",
    "preferred_industries": "Outdoor, sports, fitness, wellness, performance, lifestyle, adventure, consumer brands, events, and agencies serving those markets.",
    "target_locations": "Cape Town in-person/hybrid roles, or remote roles based anywhere Phillip can legally work. Non-Cape-Town in-person roles should be avoided unless Phillip explicitly approves them.",
    "daily_target": "5 high-quality applications per day.",
    "submission_policy": "Fill and draft everything, then stop for Phillip to review and submit.",
    "work_authorization": "Dual South African and UK citizenship. South Africa and UK work eligibility likely; confirm right-to-work wording per application. USA/EU remote roles should be checked case by case.",
    "salary_expectation": "Target around R22,000 per month. Higher is preferred; lower can be considered if the opportunity is strong. Convert foreign-currency salaries to ZAR before judging.",
    "salary_target_zar_monthly": "22000",
    "availability": "Available for full-time employment from 2027-01-01. Available until 2026-06-12 for a trial period, contract project, internship-style work, or similar short-term arrangement.",
    "notice_period": "Available for full-time employment from 2027-01-01; short trial/project availability until 2026-06-12.",
    "relocation": "Prefer Cape Town or remote roles. In-person roles outside Cape Town should be avoided unless Phillip explicitly approves them.",
    "demographics_policy": "Prefer not to answer unless Phillip decides otherwise.",
    "references_policy": "Available on request.",
    "email_provider": "mweb.co.za",
    "tone": "Direct, confident, warm, and specific. Avoid exaggeration and do not invent experience.",
    "email_voice": "Sound like Phillip: a 23-year-old South African marketing graduate who studied in Cape Town. Keep it professional but natural, warm, concise, and specific. Avoid generic AI phrases, inflated claims, and overly polished corporate language.",
    "writing_sample_path": "",
    "writing_sample_text": "",
    "writing_style_notes": "",
}

GRADUATE_MARKETING_DISCOVERY_QUERY = (
    "graduate junior entry level marketing coordinator marketing assistant "
    "brand assistant social media assistant content creator community coordinator "
    "campaign coordinator copywriter crm executive content curator remote cape town uk"
)


MARKETING_KEYWORDS = {
    "marketing": 8,
    "brand": 8,
    "campaign": 7,
    "content": 7,
    "social media": 7,
    "community": 6,
    "growth": 6,
    "performance marketing": 7,
    "digital marketing": 8,
    "seo": 5,
    "sem": 5,
    "email marketing": 5,
    "crm": 5,
    "copywriting": 6,
    "copy": 4,
    "partnership": 6,
    "influencer": 5,
    "influencer marketing": 6,
    "affiliate": 4,
    "public relations": 5,
    "pr ": 4,
    "events": 5,
    "analytics": 5,
    "google analytics": 5,
    "paid media": 6,
    "meta ads": 5,
    "google ads": 5,
    "tiktok": 4,
    "instagram": 4,
    "creative": 5,
    "consumer": 4,
    "storytelling": 4,
    "b2c": 4,
}

PREFERRED_KEYWORDS = {
    "outdoor": 9,
    "sports": 9,
    "sport": 9,
    "fitness": 9,
    "wellness": 7,
    "training": 4,
    "running": 6,
    "cycling": 6,
    "adventure": 7,
    "lifestyle": 5,
    "athlete": 6,
    "performance": 5,
    "apparel": 5,
    "equipment": 4,
}

LOCATION_KEYWORDS = {
    "south africa": 10,
    "cape town": 14,
    "remote": 12,
    "johannesburg": -4,
    "durban": -4,
    "uk": 5,
    "united kingdom": 5,
    "usa": 5,
    "united states": 5,
    "europe": 5,
    "emea": 5,
}

REMOTE_ALLOWED_LOCATION_TERMS = [
    "worldwide",
    "anywhere",
    "global",
    "south africa",
    "cape town",
    "western cape",
    "africa",
    "uk",
    "united kingdom",
    "england",
    "scotland",
    "wales",
    "europe",
    "emea",
    "eu ",
    "european",
    "usa",
    "us ",
    "united states",
]

REMOTE_RESTRICTED_LOCATION_TERMS = [
    "argentina",
    "brazil",
    "latam",
    "asia",
    "philippines",
    "colombia",
    "canada",
    "australia",
    "new zealand",
    "israel",
]

REMOTE_RESTRICTION_PATTERNS = [
    "must be based in",
    "must reside in",
    "must live in",
    "must be located in",
    "you must be located in",
    "applicants must be located in",
    "location:",
    "us only",
    "u.s. only",
    "europe only",
    "eu only",
    "uk only",
    "remote within",
    "remote in the us",
    "remote in the united states",
    "remote in europe",
    "remote in germany",
    "remote role based in",
    "remote position based in",
    "based in dublin",
    "based in ireland",
    "based in berlin",
    "based in london",
]

OUTSIDE_CAPE_PHYSICAL_TERMS = [
    "johannesburg",
    "durban",
    "pretoria",
    "gauteng",
    "kwazulu",
    "kwazulu-natal",
    "sandton",
    "london",
    "dublin",
    "ireland",
    "milan",
    "munich",
    "berlin",
    "amsterdam",
    "paris",
    "spain",
    "italy",
    "germany",
    "netherlands",
    "new york",
    "san francisco",
    "california",
    "seattle",
    "boston",
    "chicago",
    "los angeles",
    "austin",
    "miami",
    "dubai",
    "australia",
    "malaysia",
    "petaling jaya",
    "singapore",
    "cairo",
    "egypt",
]

SENIORITY_WARNINGS = [
    "senior ",
    "sr. ",
    "sr ",
    "manager",
    "marketing manager",
    "brand manager",
    "growth manager",
    "director",
    "director ",
    "senior director",
    "director of",
    "vp ",
    "vice president",
    "head of",
    "principal ",
    "lead ",
    "lead",
    "10+ years",
    "12+ years",
    "15+ years",
]

ENTRY_LEVEL_SIGNALS = [
    "intern",
    "internship",
    "graduate",
    "junior",
    "assistant",
    "associate",
    "coordinator",
    "specialist",
    "executive",
    "creator",
    "ambassador",
    "entry level",
    "entry-level",
    "learnership",
    "trainee",
    "placement",
]

MARKETING_TITLE_SIGNALS = [
    "marketing",
    "marketer",
    "brand",
    "content",
    "social",
    "media",
    "growth",
    "community",
    "communications",
    "campaign",
    "partnership",
    "advertising",
    "ppc",
    "paid media",
    "digital media",
    "media strategist",
    "lifecycle",
    "crm",
    "seo",
    "creative strategist",
    "copywriter",
    "writer",
    "content creator",
    "marketing coordinator",
    "marketing specialist",
    "marketing executive",
    "brand coordinator",
    "brand specialist",
    "social media coordinator",
    "social media specialist",
]

NON_TARGET_TITLE_SIGNALS = [
    "engineer",
    "developer",
    "designer",
    "creative director",
    "product manager",
    "project coordinator",
    "project manager",
    "account executive",
    "accounting",
    "customer success",
    "sales ",
    "revenue specialist",
    "ml ",
    "machine learning",
    "data scientist",
    "data analyst",
    "online data analyst",
    "content reviewer",
    "reviewer",
    "rater",
    "moderator",
    "finance",
    "accountant",
    "legal",
    "learning and development",
    "learning & development",
    "training specialist",
    "doctor",
    "physician",
    "radiologist",
    "radiology",
    "neuroradiologist",
    "nurse",
    "surgeon",
    "therapist",
    "clinical",
    "medical",
    "healthcare",
    "warehouse",
    "retail associate",
    "sales assistant",
]

HARD_NON_TARGET_TITLE_SIGNALS = [
    "creative director",
    "content reviewer",
    "online data analyst",
    "data analyst",
    "doctor",
    "physician",
    "radiologist",
    "radiology",
    "neuroradiologist",
    "nurse",
    "surgeon",
    "therapist",
    "clinical",
    "medical",
    "healthcare",
    "office assistant",
    "technical support",
    "support operator",
    "moderator",
    "rater",
]

SCAM_WARNINGS = [
    "pay to start",
    "registration fee",
    "investment required",
    "crypto",
    "whatsapp only",
    "telegram",
    "no experience required high pay",
    "send id",
    "bank details",
]

FX_TO_ZAR_ESTIMATES = {
    "ZAR": 1.0,
    "R": 1.0,
    "USD": 18.5,
    "$": 18.5,
    "GBP": 23.5,
    "£": 23.5,
    "EUR": 20.0,
    "€": 20.0,
}

FX_SYMBOL_TO_CODE = {
    "R": "ZAR",
    "$": "USD",
    "£": "GBP",
    "€": "EUR",
}

FX_CACHE: dict[str, float] = {}

STARTER_JOB_SOURCES = [
    {
        "name": "Sleeper sports platform",
        "source_type": "ashby",
        "token": "sleeper",
        "query": GRADUATE_MARKETING_DISCOVERY_QUERY,
    },
    {
        "name": "Sweatpals fitness community",
        "source_type": "ashby",
        "token": "sweatpals",
        "query": GRADUATE_MARKETING_DISCOVERY_QUERY,
    },
    {
        "name": "Eight Sleep sleep fitness",
        "source_type": "ashby",
        "token": "eightsleep",
        "query": GRADUATE_MARKETING_DISCOVERY_QUERY,
    },
    {
        "name": "Avida fitness coaching",
        "source_type": "ashby",
        "token": "avida",
        "query": GRADUATE_MARKETING_DISCOVERY_QUERY,
    },
    {
        "name": "TeamSnap sports platform",
        "source_type": "lever",
        "token": "teamsnap",
        "query": GRADUATE_MARKETING_DISCOVERY_QUERY,
    },
    {
        "name": "WHOOP performance wearable",
        "source_type": "lever",
        "token": "whoop",
        "query": GRADUATE_MARKETING_DISCOVERY_QUERY,
    },
    {
        "name": "Sporty Group sports media",
        "source_type": "lever",
        "token": "sporty",
        "query": GRADUATE_MARKETING_DISCOVERY_QUERY,
    },
    {
        "name": "Red Bull sports marketing",
        "source_type": "smartrecruiters",
        "token": "RedBull",
        "query": "marketing",
    },
    {
        "name": "Frasers Group sports retail",
        "source_type": "smartrecruiters",
        "token": "FrasersGroup",
        "query": "marketing",
    },
    {
        "name": "AIM Sports Group",
        "source_type": "smartrecruiters",
        "token": "AIMSportsGroup",
        "query": "marketing",
    },
    {
        "name": "ThirdChannel sport brand ambassadors",
        "source_type": "smartrecruiters",
        "token": "ThirdChannel1",
        "query": "marketing",
    },
    {
        "name": "Bommarito sports performance",
        "source_type": "smartrecruiters",
        "token": "BommaritoPerformanceSystems",
        "query": "marketing",
    },
    {
        "name": "Remotive remote marketing",
        "source_type": "remotive",
        "token": "marketing",
        "query": f"{GRADUATE_MARKETING_DISCOVERY_QUERY} marketing brand content community social media",
    },
    {
        "name": "Remotive remote growth",
        "source_type": "remotive",
        "token": "marketing",
        "query": f"{GRADUATE_MARKETING_DISCOVERY_QUERY} growth campaign performance marketing",
    },
    {
        "name": "Arbeitnow Europe remote marketing",
        "source_type": "arbeitnow",
        "token": "public",
        "query": f"{GRADUATE_MARKETING_DISCOVERY_QUERY} marketing brand content social media community copywriter growth",
    },
    {
        "name": "BizCommunity SA marketing jobs",
        "source_type": "careers",
        "token": "https://www.bizcommunity.com/Job/196/",
        "query": GRADUATE_MARKETING_DISCOVERY_QUERY,
    },
    {
        "name": "CareerJunction Cape Town marketing",
        "source_type": "careers",
        "token": "https://www.careerjunction.co.za/jobs/marketing/cape-town",
        "query": GRADUATE_MARKETING_DISCOVERY_QUERY,
    },
    {
        "name": "We Work Remotely marketing",
        "source_type": "careers",
        "token": "https://weworkremotely.com/remote-jobs/marketing",
        "query": GRADUATE_MARKETING_DISCOVERY_QUERY,
    },
    {
        "name": "Strava fitness app",
        "source_type": "lever",
        "token": "strava",
        "query": GRADUATE_MARKETING_DISCOVERY_QUERY,
    },
    {
        "name": "Gymshark fitness apparel",
        "source_type": "careers",
        "token": "https://www.gymshark.com/pages/careers",
        "query": GRADUATE_MARKETING_DISCOVERY_QUERY,
    },
    {
        "name": "Virgin Active SA",
        "source_type": "careers",
        "token": "https://www.virginactive.co.za/careers",
        "query": GRADUATE_MARKETING_DISCOVERY_QUERY,
    },
    {
        "name": "HubSpot marketing platform",
        "source_type": "greenhouse",
        "token": "hubspot",
        "query": GRADUATE_MARKETING_DISCOVERY_QUERY,
    },
    {
        "name": "Decathlon SA sports retail",
        "source_type": "careers",
        "token": "https://www.decathlon.co.za/pages/careers",
        "query": GRADUATE_MARKETING_DISCOVERY_QUERY,
    },
    # --- Indeed RSS: SA + remote marketing ---
    {
        "name": "Indeed Cape Town marketing (RSS)",
        "source_type": "indeed_rss",
        "token": "Cape Town, Western Cape",
        "query": "marketing junior graduate content social media brand",
    },
    {
        "name": "Indeed remote marketing roles (RSS)",
        "source_type": "indeed_rss",
        "token": "remote",
        "query": "marketing junior graduate remote content brand",
    },
    # --- Jobicy RSS: verified working remote job board ---
    {
        "name": "Jobicy remote marketing jobs (RSS)",
        "source_type": "jobicy_rss",
        "token": "marketing",
        "query": GRADUATE_MARKETING_DISCOVERY_QUERY,
    },
    {
        "name": "Jobicy remote copywriting jobs (RSS)",
        "source_type": "jobicy_rss",
        "token": "copywriting",
        "query": GRADUATE_MARKETING_DISCOVERY_QUERY,
    },
    # --- SA company careers pages ---
    {
        "name": "Takealot SA e-commerce",
        "source_type": "careers",
        "token": "https://www.takealot.com/about/careers",
        "query": GRADUATE_MARKETING_DISCOVERY_QUERY,
    },
    {
        "name": "Superbalist fashion retail SA",
        "source_type": "careers",
        "token": "https://superbalist.com/about/careers",
        "query": GRADUATE_MARKETING_DISCOVERY_QUERY,
    },
    {
        "name": "Yoco fintech SA",
        "source_type": "careers",
        "token": "https://www.yoco.com/za/careers/",
        "query": GRADUATE_MARKETING_DISCOVERY_QUERY,
    },
    {
        "name": "Peach Payments SA fintech",
        "source_type": "careers",
        "token": "https://www.peachpayments.com/careers",
        "query": GRADUATE_MARKETING_DISCOVERY_QUERY,
    },
    {
        "name": "CareerJunction all marketing SA",
        "source_type": "careers",
        "token": "https://www.careerjunction.co.za/jobs/marketing",
        "query": GRADUATE_MARKETING_DISCOVERY_QUERY,
    },
    {
        "name": "PNet Cape Town marketing",
        "source_type": "careers",
        "token": "https://www.pnet.co.za/jobs/marketing/cape-town/western-cape/1/",
        "query": GRADUATE_MARKETING_DISCOVERY_QUERY,
    },
    {
        "name": "Careers24 marketing Cape Town",
        "source_type": "careers",
        "token": "https://www.careers24.com/jobs/?keyterms=marketing&location=Cape+Town",
        "query": GRADUATE_MARKETING_DISCOVERY_QUERY,
    },
    {
        "name": "WorkAfrica marketing Cape Town",
        "source_type": "careers",
        "token": "https://workafrica.co.za/jobs/marketing/cape-town",
        "query": GRADUATE_MARKETING_DISCOVERY_QUERY,
    },
    # --- Remote-friendly global companies on Greenhouse/Lever/Ashby ---
    {
        "name": "Buffer remote social media",
        "source_type": "greenhouse",
        "token": "buffer",
        "query": GRADUATE_MARKETING_DISCOVERY_QUERY,
    },
    {
        "name": "Mailchimp email marketing",
        "source_type": "greenhouse",
        "token": "mailchimp",
        "query": GRADUATE_MARKETING_DISCOVERY_QUERY,
    },
    {
        "name": "Hootsuite social media platform",
        "source_type": "greenhouse",
        "token": "hootsuite",
        "query": GRADUATE_MARKETING_DISCOVERY_QUERY,
    },
    {
        "name": "Sprout Social marketing",
        "source_type": "lever",
        "token": "sproutsocial",
        "query": GRADUATE_MARKETING_DISCOVERY_QUERY,
    },
    {
        "name": "Later social media tool",
        "source_type": "lever",
        "token": "later",
        "query": GRADUATE_MARKETING_DISCOVERY_QUERY,
    },
    {
        "name": "Canva design platform",
        "source_type": "greenhouse",
        "token": "canva",
        "query": GRADUATE_MARKETING_DISCOVERY_QUERY,
    },
    {
        "name": "Notion productivity tool",
        "source_type": "greenhouse",
        "token": "notion",
        "query": GRADUATE_MARKETING_DISCOVERY_QUERY,
    },
]

STARTER_TARGET_COMPANIES = [
    {
        "company": "Nike",
        "website": "https://www.nike.com",
        "careers_url": "https://jobs.nike.com",
        "industry": "Sportswear, fitness, running, lifestyle",
        "priority": 5,
        "notes": "Dream-fit global sports brand with strong running, training, athlete, and lifestyle campaigns.",
    },
    {
        "company": "adidas",
        "website": "https://www.adidas.com",
        "careers_url": "https://careers.adidas-group.com",
        "industry": "Sportswear, football, running, training, lifestyle",
        "priority": 5,
        "notes": "Strong fit for sport, brand, retail, community, and campaign work.",
    },
    {
        "company": "PUMA",
        "website": "https://about.puma.com",
        "careers_url": "https://about.puma.com/en/careers",
        "industry": "Sportswear, running, football, lifestyle",
        "priority": 4,
        "notes": "Sports and lifestyle brand with marketing, brand, social, and retail campaign potential.",
    },
    {
        "company": "Under Armour",
        "website": "https://www.underarmour.com",
        "careers_url": "https://careers.underarmour.com",
        "industry": "Performance apparel, training, fitness",
        "priority": 4,
        "notes": "Performance-focused brand that matches Phillip's sport and training background.",
    },
    {
        "company": "Salomon",
        "website": "https://www.salomon.com",
        "careers_url": "https://www.salomon.com/en-us/careers",
        "industry": "Outdoor, trail running, adventure",
        "priority": 5,
        "notes": "Strong outdoor/trail running fit, useful for endurance and adventure positioning.",
    },
    {
        "company": "The North Face",
        "website": "https://www.thenorthface.com",
        "careers_url": "https://www.vfc.com/careers",
        "industry": "Outdoor, adventure, apparel",
        "priority": 5,
        "notes": "Outdoor/adventure brand with strong community and storytelling angle.",
    },
    {
        "company": "Patagonia",
        "website": "https://www.patagonia.com",
        "careers_url": "https://www.patagonia.com/jobs",
        "industry": "Outdoor, sustainability, apparel",
        "priority": 5,
        "notes": "Outdoor brand with sustainability and community storytelling fit.",
    },
    {
        "company": "Decathlon",
        "website": "https://www.decathlon.co.za",
        "careers_url": "https://www.decathlon.co.za/pages/careers",
        "industry": "Sports retail, outdoor, fitness, South Africa",
        "priority": 5,
        "notes": "South African sports retail fit with practical marketing and community potential.",
    },
    {
        "company": "Totalsports",
        "website": "https://www.totalsports.co.za",
        "careers_url": "https://tfglimited.co.za/careers/",
        "industry": "Sports retail, South Africa",
        "priority": 5,
        "notes": "South African sports retail brand; good fit for brand, retail, and campaign experience.",
    },
    {
        "company": "Sportsmans Warehouse",
        "website": "https://www.sportsmanswarehouse.co.za",
        "careers_url": "https://www.sportsmanswarehouse.co.za/careers",
        "industry": "Sports retail, outdoor, fitness, South Africa",
        "priority": 4,
        "notes": "Local sports/outdoor retail fit with content, events, and community angles.",
    },
    {
        "company": "Cape Union Mart",
        "website": "https://www.capeunionmart.co.za",
        "careers_url": "https://www.capeunionmart.co.za/careers",
        "industry": "Outdoor retail, adventure, South Africa",
        "priority": 5,
        "notes": "Cape Town-relevant outdoor/adventure brand with strong local fit.",
    },
    {
        "company": "Red Bull",
        "website": "https://www.redbull.com/za-en",
        "careers_url": "https://jobs.redbull.com",
        "industry": "Sports marketing, events, lifestyle, energy drink",
        "priority": 5,
        "source_type": "smartrecruiters",
        "source_token": "RedBull",
        "notes": "Excellent fit for sport, events, content, athlete/community marketing, and Cape Town opportunities.",
    },
    {
        "company": "Garmin",
        "website": "https://www.garmin.com",
        "careers_url": "https://careers.garmin.com",
        "industry": "Fitness technology, endurance sport, wearables",
        "priority": 4,
        "notes": "Strong fit for triathlon, training analytics, fitness tech, and product marketing.",
    },
    {
        "company": "Strava",
        "website": "https://www.strava.com",
        "careers_url": "https://www.strava.com/careers",
        "industry": "Fitness app, running, cycling, community",
        "priority": 5,
        "notes": "Strong fit for endurance sport, community, analytics, and digital product marketing.",
    },
    {
        "company": "WHOOP",
        "website": "https://www.whoop.com",
        "careers_url": "https://www.whoop.com/careers",
        "industry": "Performance wearable, fitness, recovery",
        "priority": 5,
        "source_type": "lever",
        "source_token": "whoop",
        "notes": "Strong fit for performance, training analytics, wellness, and sport-focused content.",
    },
    {
        "company": "Zwift",
        "website": "https://www.zwift.com",
        "careers_url": "https://www.zwift.com/careers",
        "industry": "Fitness technology, cycling, running, community",
        "priority": 4,
        "notes": "Good fit for endurance sport, digital community, and training technology.",
    },
    {
        "company": "Gymshark",
        "website": "https://www.gymshark.com",
        "careers_url": "https://www.gymshark.com/pages/careers",
        "industry": "Fitness apparel, influencer marketing, community",
        "priority": 4,
        "notes": "Strong brand/community/social media fit in fitness apparel.",
    },
    {
        "company": "lululemon",
        "website": "https://www.lululemon.com",
        "careers_url": "https://careers.lululemon.com",
        "industry": "Fitness, wellness, apparel, community",
        "priority": 4,
        "notes": "Good fit for wellness, community, events, and brand marketing.",
    },
    {
        "company": "Virgin Active South Africa",
        "website": "https://www.virginactive.co.za",
        "careers_url": "https://www.virginactive.co.za/careers",
        "industry": "Fitness, gyms, wellness, South Africa",
        "priority": 5,
        "notes": "Local fitness/wellness fit with content, community, events, and growth marketing potential.",
    },
    {
        "company": "Discovery Vitality",
        "website": "https://www.discovery.co.za",
        "careers_url": "https://www.discovery.co.za/corporate/careers",
        "industry": "Wellness, health rewards, South Africa",
        "priority": 4,
        "notes": "South African wellness/behaviour-change brand with strong analytics and marketing angle.",
    },
    {
        "company": "Yoco",
        "website": "https://www.yoco.com",
        "careers_url": "https://www.yoco.com/za/careers/",
        "industry": "Cape Town fintech, small business, growth marketing",
        "priority": 4,
        "notes": "Cape Town-relevant fintech brand with strong small-business, content, growth, and campaign angle.",
    },
    {
        "company": "Takealot",
        "website": "https://www.takealot.com",
        "careers_url": "https://www.takealot.com/careers",
        "industry": "Cape Town ecommerce, retail, consumer marketing",
        "priority": 4,
        "notes": "Cape Town ecommerce brand with marketing, retail, CRM, social, and consumer campaign relevance.",
    },
    {
        "company": "Bash",
        "website": "https://www.bash.com",
        "careers_url": "https://tfglimited.co.za/careers/",
        "industry": "Cape Town ecommerce, fashion, sports retail, TFG",
        "priority": 4,
        "notes": "TFG ecommerce platform; relevant for consumer, retail, fashion/sports, content, and brand work.",
    },
    {
        "company": "TFG",
        "website": "https://tfglimited.co.za",
        "careers_url": "https://tfglimited.co.za/careers/",
        "industry": "Cape Town retail group, sports/fashion/lifestyle",
        "priority": 4,
        "notes": "Cape Town retail group behind multiple consumer brands, useful for brand, CRM, retail, and campaign roles.",
    },
    {
        "company": "Woolworths South Africa",
        "website": "https://www.woolworths.co.za",
        "careers_url": "https://www.woolworths.co.za/careers",
        "industry": "Cape Town retail, food, fashion, loyalty, consumer brand",
        "priority": 4,
        "notes": "Cape Town-headquartered consumer brand with marketing, loyalty, content, and campaign potential.",
    },
    {
        "company": "Pick n Pay",
        "website": "https://www.pnp.co.za",
        "careers_url": "https://www.pnp.co.za/careers",
        "industry": "Cape Town retail, loyalty, consumer marketing",
        "priority": 3,
        "notes": "Cape Town retail brand with Smart Shopper, CRM, campaign, and consumer marketing relevance.",
    },
    {
        "company": "Ciovita",
        "website": "https://ciovita.com",
        "careers_url": "https://ciovita.com/pages/careers",
        "industry": "Cape Town cycling apparel, endurance sport, ecommerce",
        "priority": 5,
        "notes": "Strong Cape Town endurance-sport brand fit for cycling, content, ecommerce, community, and events.",
    },
    {
        "company": "First Ascent",
        "website": "https://www.firstascent.co.za",
        "careers_url": "https://www.capeunionmart.co.za/careers",
        "industry": "Cape Town outdoor apparel, endurance, adventure",
        "priority": 5,
        "notes": "Local outdoor and endurance brand; strong fit for sport/outdoor content, product, and campaign work.",
    },
    {
        "company": "Travelstart",
        "website": "https://www.travelstart.co.za",
        "careers_url": "https://www.travelstart.co.za/lp/careers",
        "industry": "Cape Town travel, ecommerce, performance marketing",
        "priority": 3,
        "notes": "Cape Town travel/ecommerce brand with performance, CRM, content, and campaign marketing relevance.",
    },
    {
        "company": "Luno",
        "website": "https://www.luno.com",
        "careers_url": "https://www.luno.com/careers",
        "industry": "Remote/Cape Town fintech, consumer app, growth",
        "priority": 3,
        "notes": "Remote-friendly consumer fintech with growth, content, lifecycle, and app marketing angles.",
    },
    {
        "company": "Ozow",
        "website": "https://ozow.com",
        "careers_url": "https://ozow.com/careers/",
        "industry": "Cape Town fintech, payments, growth marketing",
        "priority": 3,
        "notes": "Cape Town payments brand with B2B/B2C marketing, content, partnership, and growth relevance.",
    },
    {
        "company": "Stitch",
        "website": "https://stitch.money",
        "careers_url": "https://stitch.money/careers",
        "industry": "Cape Town fintech, payments, startup growth",
        "priority": 3,
        "notes": "Cape Town fintech startup with marketing, content, events, growth, and partnership potential.",
    },
    {
        "company": "Peach Payments",
        "website": "https://www.peachpayments.com",
        "careers_url": "https://www.peachpayments.com/careers",
        "industry": "Cape Town fintech, ecommerce payments",
        "priority": 3,
        "notes": "Cape Town payments company with ecommerce, B2B, content, and partnership marketing angles.",
    },
    {
        "company": "SnapScan",
        "website": "https://www.snapscan.co.za",
        "careers_url": "https://www.snapscan.co.za/careers",
        "industry": "Cape Town fintech, payments, small business",
        "priority": 3,
        "notes": "Cape Town consumer/small-business payments brand with content, growth, and merchant marketing relevance.",
    },
    {
        "company": "JOBJACK",
        "website": "https://jobjack.co.za",
        "careers_url": "https://jobjack.co.za/careers",
        "industry": "Cape Town HR tech, startup, growth",
        "priority": 3,
        "notes": "Cape Town startup with growth, community, content, and employer/candidate marketing relevance.",
    },
    {
        "company": "Aerobotics",
        "website": "https://www.aerobotics.com",
        "careers_url": "https://www.aerobotics.com/careers",
        "industry": "Cape Town agri-tech, AI, B2B marketing",
        "priority": 3,
        "notes": "Cape Town tech company; useful for B2B, product, content, research, and AI/tech marketing positioning.",
    },
]

KNOWN_COMPANY_RESEARCH_URLS = {
    "avida": "https://www.avida.life/",
    "happily": "https://teamhappily.com/",
    "maneuver marketing": "https://maneuvermarketing.com/",
    "coalition technologies": "https://coalitiontechnologies.co/about-us/",
    "brandwatch": "https://www.brandwatch.com/company/about/",
    "redbull": "https://www.redbull.com/company",
}

DEFAULT_EMAIL_ENV = {
    "JOB_AI_SMTP_HOST": "smtp.mweb.co.za",
    "JOB_AI_SMTP_PORT": "587",
    "JOB_AI_SMTP_USER": "Phillip2002@mweb.co.za",
    "JOB_AI_SMTP_FROM": "Phillip2002@mweb.co.za",
    "JOB_AI_SMTP_STARTTLS": "1",
    "JOB_AI_IMAP_HOST": "imap.mweb.co.za",
    "JOB_AI_IMAP_PORT": "993",
    "JOB_AI_IMAP_USER": "Phillip2002@mweb.co.za",
    "JOB_AI_IMAP_SSL": "1",
    "JOB_AI_IMAP_MAILBOX": "INBOX",
    "JOB_AI_IMAP_LOOKBACK_DAYS": "45",
}


def now_iso() -> str:
    return dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat()


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(exist_ok=True)
    DOCS_DIR.mkdir(exist_ok=True)
    TASK_DIR.mkdir(exist_ok=True)
    LOG_DIR.mkdir(exist_ok=True)
    SMOKE_DIR.mkdir(exist_ok=True)
    FORM_PREP_DIR.mkdir(exist_ok=True)
    REMINDERS_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            create table if not exists profile (
                key text primary key,
                value text not null
            );

            create table if not exists jobs (
                id integer primary key autoincrement,
                title text not null default '',
                company text not null default '',
                location text not null default '',
                url text not null default '',
                source text not null default 'manual',
                description text not null default '',
                raw_json text not null default '{}',
                status text not null default 'new',
                too_senior integer not null default 0,
                score integer not null default 0,
                score_reasons text not null default '',
                concerns text not null default '',
                created_at text not null,
                updated_at text not null
            );

            create unique index if not exists idx_jobs_url on jobs(url) where url != '';
            create index if not exists idx_jobs_status on jobs(status);

            create table if not exists job_sources (
                id integer primary key autoincrement,
                name text not null default '',
                source_type text not null default '',
                token text not null default '',
                query text not null default '',
                enabled integer not null default 1,
                last_run text not null default '',
                last_result text not null default '',
                created_at text not null,
                updated_at text not null
            );

            create unique index if not exists idx_job_sources_unique on job_sources(source_type, token, query);

            create table if not exists applications (
                id integer primary key autoincrement,
                job_id integer not null references jobs(id) on delete cascade,
                status text not null default 'draft',
                queue_state text not null default 'review',
                reject_reason text not null default '',
                reject_notes text not null default '',
                contact_email text not null default '',
                contact_name text not null default '',
                contact_role text not null default '',
                company_notes text not null default '',
                cover_letter text not null default '',
                cv_notes text not null default '',
                answers text not null default '',
                follow_up text not null default '',
                next_follow_up text not null default '',
                follow_up_sent_at text not null default '',
                form_prep_overrides text not null default '',
                form_prep_report_path text not null default '',
                form_prep_screenshot_path text not null default '',
                form_prep_task_path text not null default '',
                form_prep_started_at text not null default '',
                created_at text not null,
                updated_at text not null
            );

            create table if not exists events (
                id integer primary key autoincrement,
                application_id integer not null references applications(id) on delete cascade,
                kind text not null,
                body text not null,
                created_at text not null
            );

            create table if not exists company_leads (
                id integer primary key autoincrement,
                company text not null default '',
                website text not null default '',
                industry text not null default '',
                contact_name text not null default '',
                contact_role text not null default '',
                contact_email text not null default '',
                source_url text not null default '',
                company_notes text not null default '',
                contact_search_notes text not null default '',
                outreach_style text not null default 'intro',
                status text not null default 'found',
                outreach_email text not null default '',
                next_follow_up text not null default '',
                sent_at text not null default '',
                do_not_contact integer not null default 0,
                created_at text not null,
                updated_at text not null
            );

            create unique index if not exists idx_company_leads_contact on company_leads(contact_email) where contact_email != '';

            create table if not exists target_companies (
                id integer primary key autoincrement,
                company text not null default '',
                website text not null default '',
                careers_url text not null default '',
                industry text not null default '',
                priority integer not null default 3,
                source_type text not null default '',
                source_token text not null default '',
                source_query text not null default 'marketing',
                notes text not null default '',
                status text not null default 'target',
                source_id integer not null default 0,
                lead_id integer not null default 0,
                created_at text not null,
                updated_at text not null
            );

            create table if not exists cv_versions (
                id integer primary key autoincrement,
                name text not null default '',
                focus text not null default '',
                notes text not null default '',
                file_path text not null default '',
                is_default integer not null default 0,
                created_at text not null,
                updated_at text not null
            );

            create table if not exists answer_bank (
                id integer primary key autoincrement,
                question_key text not null default '',
                question text not null default '',
                answer text not null default '',
                category text not null default '',
                approved integer not null default 1,
                created_at text not null,
                updated_at text not null
            );

            create table if not exists story_bank (
                id integer primary key autoincrement,
                title text not null default '',
                category text not null default '',
                story text not null default '',
                proof_points text not null default '',
                approved integer not null default 1,
                created_at text not null,
                updated_at text not null
            );

            create table if not exists automation_runs (
                id integer primary key autoincrement,
                kind text not null default 'auto-mode',
                summary text not null default '',
                details text not null default '{}',
                created_at text not null
            );

            create table if not exists form_fill_feedback (
                id integer primary key autoincrement,
                application_id integer not null references applications(id) on delete cascade,
                worked text not null default '',
                missed text not null default '',
                wrong text not null default '',
                notes text not null default '',
                created_at text not null
            );

            create table if not exists inbox_messages (
                id integer primary key autoincrement,
                message_uid text not null default '',
                mailbox text not null default '',
                from_email text not null default '',
                from_name text not null default '',
                subject text not null default '',
                snippet text not null default '',
                received_at text not null default '',
                matched_type text not null default '',
                application_id integer not null default 0,
                lead_id integer not null default 0,
                classification text not null default '',
                confidence integer not null default 0,
                status text not null default 'new',
                raw_headers text not null default '',
                created_at text not null,
                updated_at text not null
            );

            create unique index if not exists idx_inbox_messages_uid on inbox_messages(message_uid) where message_uid != '';

            create table if not exists site_credentials (
                id integer primary key autoincrement,
                domain text not null default '',
                login_url text not null default '',
                username text not null default '',
                notes text not null default '',
                enabled integer not null default 1,
                created_at text not null,
                updated_at text not null
            );

            create unique index if not exists idx_site_credentials_domain on site_credentials(domain);
            """
        )
        for key, value in DEFAULT_PROFILE.items():
            conn.execute(
                "insert or ignore into profile(key, value) values(?, ?)",
                (key, value),
            )
        ensure_column(conn, "applications", "contact_email", "text not null default ''")
        ensure_column(conn, "applications", "contact_name", "text not null default ''")
        ensure_column(conn, "applications", "contact_role", "text not null default ''")
        ensure_column(conn, "applications", "company_notes", "text not null default ''")
        ensure_column(conn, "applications", "follow_up_sent_at", "text not null default ''")
        ensure_column(conn, "applications", "research_url", "text not null default ''")
        ensure_column(conn, "applications", "research_notes", "text not null default ''")
        ensure_column(conn, "applications", "research_sources", "text not null default ''")
        ensure_column(conn, "applications", "quality_score", "integer not null default 0")
        ensure_column(conn, "applications", "quality_notes", "text not null default ''")
        ensure_column(conn, "applications", "checklist", "text not null default ''")
        ensure_column(conn, "applications", "truthfulness_flags", "text not null default ''")
        ensure_column(conn, "applications", "recommended_cv_version", "text not null default ''")
        ensure_column(conn, "applications", "form_prep_overrides", "text not null default ''")
        ensure_column(conn, "applications", "form_prep_report_path", "text not null default ''")
        ensure_column(conn, "applications", "form_prep_screenshot_path", "text not null default ''")
        ensure_column(conn, "applications", "form_prep_task_path", "text not null default ''")
        ensure_column(conn, "applications", "form_prep_started_at", "text not null default ''")
        ensure_column(conn, "applications", "batch_id", "text not null default ''")
        ensure_column(conn, "applications", "queue_state", "text not null default 'review'")
        ensure_column(conn, "applications", "reject_reason", "text not null default ''")
        ensure_column(conn, "applications", "reject_notes", "text not null default ''")
        conn.execute("update applications set queue_state='review' where queue_state=''")
        ensure_column(conn, "jobs", "reject_reason", "text not null default ''")
        ensure_column(conn, "jobs", "too_senior", "integer not null default 0")
        ensure_column(conn, "company_leads", "contact_search_notes", "text not null default ''")
        ensure_column(conn, "company_leads", "outreach_style", "text not null default 'intro'")
        conn.execute("update company_leads set outreach_style='intro' where outreach_style=''")
        conn.execute(
            """
            update job_sources
            set query=?
            where query=''
              and source_type in ('greenhouse', 'lever', 'ashby', 'smartrecruiters', 'recruitee', 'remotive', 'remoteok', 'arbeitnow', 'workable', 'teamtailor', 'careers', 'url')
            """,
            (GRADUATE_MARKETING_DISCOVERY_QUERY,),
        )
        seed_default_cv_versions(conn)
        seed_default_answer_bank(conn)
        seed_default_story_bank(conn)
        conn.commit()


def ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in conn.execute(f"pragma table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"alter table {table} add column {column} {definition}")


def load_local_env() -> dict[str, str]:
    values = dict(DEFAULT_EMAIL_ENV)
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                values[key] = value
    for key in list(DEFAULT_EMAIL_ENV) + ["JOB_AI_SMTP_PASSWORD", "JOB_AI_SMTP_TO", "JOB_AI_IMAP_PASSWORD"]:
        if os.environ.get(key):
            values[key] = os.environ[key]
    return values


def write_local_env(updates: dict[str, str]) -> None:
    allowed = set(DEFAULT_EMAIL_ENV) | {"JOB_AI_SMTP_PASSWORD", "JOB_AI_SMTP_TO", "JOB_AI_IMAP_PASSWORD"}
    current = load_local_env()
    for key, value in updates.items():
        if key in allowed:
            current[key] = value
    lines = [
        "# Local email settings for Job Application AI.",
        "# This file is gitignored. Do not share it.",
    ]
    for key in [
        "JOB_AI_SMTP_HOST",
        "JOB_AI_SMTP_PORT",
        "JOB_AI_SMTP_USER",
        "JOB_AI_SMTP_FROM",
        "JOB_AI_SMTP_TO",
        "JOB_AI_SMTP_STARTTLS",
        "JOB_AI_SMTP_PASSWORD",
        "JOB_AI_IMAP_HOST",
        "JOB_AI_IMAP_PORT",
        "JOB_AI_IMAP_USER",
        "JOB_AI_IMAP_SSL",
        "JOB_AI_IMAP_MAILBOX",
        "JOB_AI_IMAP_LOOKBACK_DAYS",
        "JOB_AI_IMAP_PASSWORD",
    ]:
        value = current.get(key, "")
        if value:
            escaped = value.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'{key}="{escaped}"')
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def seed_default_cv_versions(conn: sqlite3.Connection) -> None:
    timestamp = now_iso()
    rows = [
        ("General marketing CV", "general marketing", "Use for broad marketing, brand, campaign, and coordinator roles.", CV_PATH, 1),
        ("Sports and fitness marketing CV", "sports fitness outdoor wellness", "Prioritise sport, coaching, Ironman training, fitness tech, and consumer brand evidence.", CV_PATH, 0),
        ("Content and social media CV", "content social media creative", "Prioritise Cookie Factory content work, Canva, captions, short-form video, and social reporting.", CV_PATH, 0),
        ("Research and analytics CV", "research analytics insights", "Prioritise UCT thesis, Look@ / SIGMUND, Google Analytics, survey design, and data-led recommendations.", CV_PATH, 0),
        ("Startup and growth CV", "startup growth product ai", "Prioritise AI-assisted training app, AR startup project, experimentation, and practical execution.", CV_PATH, 0),
    ]
    for name, focus, notes, file_path, is_default in rows:
        conn.execute(
            """
            insert into cv_versions(name, focus, notes, file_path, is_default, created_at, updated_at)
            select ?, ?, ?, ?, ?, ?, ?
            where not exists(select 1 from cv_versions where name=?)
            """,
            (name, focus, notes, file_path, is_default, timestamp, timestamp, name),
        )


def save_cv_version(conn: sqlite3.Connection, data: dict[str, Any]) -> int:
    cv_id = int(data.get("id") or 0)
    name = normalize_space(str(data.get("name", "")))
    if not name:
        raise RuntimeError("CV version name is required.")
    focus = normalize_space(str(data.get("focus", "")))
    notes = normalize_space(str(data.get("notes", "")))
    file_path = normalize_space(str(data.get("file_path", "")))
    is_default = 1 if data.get("is_default") else 0
    timestamp = now_iso()
    if is_default:
        conn.execute("update cv_versions set is_default=0, updated_at=?", (timestamp,))
    if cv_id:
        conn.execute(
            """
            update cv_versions
            set name=?, focus=?, notes=?, file_path=?, is_default=?, updated_at=?
            where id=?
            """,
            (name, focus, notes, file_path, is_default, timestamp, cv_id),
        )
        conn.commit()
        return cv_id
    cur = conn.execute(
        """
        insert into cv_versions(name, focus, notes, file_path, is_default, created_at, updated_at)
        values(?, ?, ?, ?, ?, ?, ?)
        """,
        (name, focus, notes, file_path, is_default, timestamp, timestamp),
    )
    conn.commit()
    return int(cur.lastrowid)


def delete_cv_version(conn: sqlite3.Connection, cv_id: int) -> None:
    row = conn.execute("select id, is_default from cv_versions where id=?", (cv_id,)).fetchone()
    if not row:
        return
    if int(row["is_default"] or 0):
        raise RuntimeError("Set another default CV before deleting the current default.")
    conn.execute("delete from cv_versions where id=?", (cv_id,))
    conn.commit()


def seed_default_answer_bank(conn: sqlite3.Connection) -> None:
    timestamp = now_iso()
    rows = [
        ("why_role", "Why are you interested in this role?", "I am interested because the role sits close to the kind of marketing work I want to build my career around: brand, content, campaigns, and work that connects properly with a real audience. I also like roles where I can combine practical execution with research and measurement.", "motivation"),
        ("why_company", "Why this company?", "The company stood out because of the way it connects product, brand, and community. I am especially interested in teams where marketing is not just about posting content, but about understanding the audience and building trust over time.", "motivation"),
        ("about_you", "Tell us about yourself.", "I am a UCT Business Science Marketing graduate based in Cape Town, with hands-on content work, market research experience, Google Analytics training, and a strong personal link to sport through coaching and Ironman 70.3 training.", "profile"),
        ("salary", "What are your salary expectations?", "My target is around R22,000 per month. I am open to assessing the full opportunity, especially where there is strong learning, growth, or brand fit.", "logistics"),
        ("start_date", "When can you start?", "I am available for full-time employment from 1 January 2027. Until 12 June 2026, I can consider a trial period, project, internship-style arrangement, or other short-term work.", "logistics"),
        ("work_authorization", "What is your work authorization?", "I have South African and UK citizenship. I can work in South Africa and the UK, and I would check remote USA/EU arrangements case by case before confirming.", "logistics"),
        ("references", "References", "References are available on request.", "logistics"),
    ]
    for key, question, answer, category in rows:
        conn.execute(
            """
            insert into answer_bank(question_key, question, answer, category, approved, created_at, updated_at)
            select ?, ?, ?, ?, 1, ?, ?
            where not exists(select 1 from answer_bank where question_key=?)
            """,
            (key, question, answer, category, timestamp, timestamp, key),
        )


def seed_default_story_bank(conn: sqlite3.Connection) -> None:
    timestamp = now_iso()
    rows = [
        ("UCT VR/AR thesis", "research analytics", "Phillip completed primary B2B research on VR/AR adoption, using interviews and theory-led analysis to understand managerial decision-making.", "UCT thesis, qualitative interviews, DOI/IRT frameworks, innovation adoption"),
        ("The Cookie Factory content work", "content social", "Phillip created weekly social content, designed graphics in Canva, wrote captions, scheduled posts, and reviewed engagement performance.", "6 posts per week, Instagram/Facebook/TikTok, product photography, monthly reports"),
        ("Look@ / SIGMUND project", "strategy startup", "Phillip helped develop a strategic marketing plan for an AR-driven startup, combining industry research with audience and revenue recommendations.", "AR startup, People Planet Profit, referral programmes, brand partnerships"),
        ("Sports coaching", "leadership sport", "Phillip coached rugby and water polo, planned sessions, coordinated squads, and helped organise a major school water polo tournament.", "Rugby, water polo, SACS Junior School, Rangers Academy, leadership"),
        ("Triathlon and gym training app", "product fitness ai", "Phillip built a personal training app with AI-assisted development to solve a real training-load problem across gym and triathlon.", "Training blocks, workout tracking, nutrition monitoring, performance analytics"),
    ]
    for title, category, story, proof in rows:
        conn.execute(
            """
            insert into story_bank(title, category, story, proof_points, approved, created_at, updated_at)
            select ?, ?, ?, ?, 1, ?, ?
            where not exists(select 1 from story_bank where title=?)
            """,
            (title, category, story, proof, timestamp, timestamp, title),
        )


def email_config_status() -> dict[str, Any]:
    env = load_local_env()
    return {
        "host": env.get("JOB_AI_SMTP_HOST", ""),
        "port": env.get("JOB_AI_SMTP_PORT", ""),
        "user": env.get("JOB_AI_SMTP_USER", ""),
        "from": env.get("JOB_AI_SMTP_FROM", ""),
        "to": env.get("JOB_AI_SMTP_TO", ""),
        "starttls": env.get("JOB_AI_SMTP_STARTTLS", "1"),
        "password_set": bool(env.get("JOB_AI_SMTP_PASSWORD")),
    }


def inbox_config_status() -> dict[str, Any]:
    env = load_local_env()
    return {
        "host": env.get("JOB_AI_IMAP_HOST", ""),
        "port": env.get("JOB_AI_IMAP_PORT", ""),
        "user": env.get("JOB_AI_IMAP_USER", ""),
        "ssl": env.get("JOB_AI_IMAP_SSL", "1"),
        "mailbox": env.get("JOB_AI_IMAP_MAILBOX", "INBOX"),
        "lookback_days": env.get("JOB_AI_IMAP_LOOKBACK_DAYS", "45"),
        "password_set": bool(env.get("JOB_AI_IMAP_PASSWORD")),
    }


def get_profile(conn: sqlite3.Connection) -> dict[str, str]:
    rows = conn.execute("select key, value from profile order by key").fetchall()
    return {row["key"]: row["value"] for row in rows}


def save_profile(conn: sqlite3.Connection, updates: dict[str, str]) -> None:
    for key, value in updates.items():
        if key in DEFAULT_PROFILE:
            conn.execute(
                "insert into profile(key, value) values(?, ?) "
                "on conflict(key) do update set value=excluded.value",
                (key, value),
            )
    conn.commit()


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def plain_text_from_html(value: str) -> str:
    value = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", value)
    value = re.sub(r"(?is)<br\s*/?>", "\n", value)
    value = re.sub(r"(?is)</p\s*>", "\n", value)
    value = re.sub(r"(?is)<.*?>", " ", value)
    value = html.unescape(value)
    return re.sub(r"\n{3,}", "\n\n", normalize_space(value).replace(". ", ".\n"))


def fetch_url(url: str, timeout: int = 20) -> tuple[int, str, str]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "JobApplicationAI/0.1 (+local supervised job search assistant)",
            "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
        },
    )
    def read_response(context: ssl.SSLContext | None = None) -> tuple[int, str, str]:
        kwargs: dict[str, Any] = {"timeout": timeout}
        if context is not None:
            kwargs["context"] = context
        with urllib.request.urlopen(req, **kwargs) as res:
            body = res.read(3_000_000)
            content_type = res.headers.get("content-type", "")
            charset = res.headers.get_content_charset() or "utf-8"
            return res.status, body.decode(charset, errors="replace"), content_type

    try:
        return read_response()
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", None)
        if isinstance(reason, ssl.SSLCertVerificationError):
            context = ssl._create_unverified_context()
            return read_response(context)
        raise
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace"), exc.headers.get("content-type", "")


def extract_title_company_from_html(doc: str, url: str) -> tuple[str, str]:
    title = ""
    company = ""
    title_match = re.search(r"(?is)<title[^>]*>(.*?)</title>", doc)
    if title_match:
        title = normalize_space(html.unescape(re.sub(r"<.*?>", " ", title_match.group(1))))
    og_site = re.search(r'(?is)<meta[^>]+property=["\']og:site_name["\'][^>]+content=["\']([^"\']+)["\']', doc)
    if og_site:
        company = normalize_space(html.unescape(og_site.group(1)))
    if not company:
        host = urllib.parse.urlparse(url).netloc.replace("www.", "")
        company = host.split(".")[0].replace("-", " ").title()
    return title[:180], company[:120]


def keyword_score(text: str, weights: dict[str, int]) -> tuple[int, list[str]]:
    lower = text.lower()
    score = 0
    hits: list[str] = []
    for term, weight in weights.items():
        if len(term) <= 3 and term.strip().isalnum():
            matched = re.search(rf"\b{re.escape(term)}\b", lower) is not None
        else:
            matched = term in lower
        if matched:
            score += weight
            hits.append(term)
    return score, hits


def parse_money_amount(value: str) -> float:
    value = value.replace(",", "").replace(" ", "").strip()
    multiplier = 1.0
    if value.lower().endswith("k"):
        multiplier = 1000.0
        value = value[:-1]
    try:
        return float(value) * multiplier
    except ValueError:
        return 0.0


def get_fx_to_zar(currency: str) -> float:
    code = FX_SYMBOL_TO_CODE.get(currency, currency.upper())
    if code == "ZAR":
        return 1.0
    if code in FX_CACHE:
        return FX_CACHE[code]
    fallback = FX_TO_ZAR_ESTIMATES.get(code, FX_TO_ZAR_ESTIMATES.get(currency, 1.0))
    try:
        status, body, _ = fetch_url(f"https://api.frankfurter.dev/v2/rate/{code}/ZAR", timeout=3)
        if status < 400:
            payload = json.loads(body)
            rate = float(payload.get("rate", fallback))
            if rate > 0:
                FX_CACHE[code] = rate
                return rate
    except Exception:
        pass
    FX_CACHE[code] = fallback
    return fallback


def salary_to_monthly_zar(amount: float, currency: str, context: str) -> float:
    rate = get_fx_to_zar(currency)
    monthly = amount * rate
    lower = context.lower()
    if any(term in lower for term in ["per annum", "per year", "annum", "annual", "/year", " p.a", " pa "]):
        monthly = monthly / 12.0
    elif any(term in lower for term in ["per hour", "hourly", "/hour", "/hr"]):
        monthly = monthly * 173.0
    elif any(term in lower for term in ["per week", "weekly", "/week"]):
        monthly = monthly * 4.33
    return monthly


def assess_salary_text(text: str, target_zar_monthly: float = 22000.0) -> tuple[str, str]:
    patterns = [
        r"(?P<currency>ZAR|R|USD|\$|GBP|£|EUR|€)\s*(?P<amount>\d[\d,\s]*(?:\.\d+)?\s*[kK]?)",
        r"(?P<amount>\d[\d,\s]*(?:\.\d+)?\s*[kK]?)\s*(?P<currency>ZAR|USD|GBP|EUR)",
    ]
    candidates: list[tuple[float, str, str]] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.I):
            currency = match.group("currency").upper()
            amount = parse_money_amount(match.group("amount"))
            if amount <= 0:
                continue
            start = max(0, match.start() - 80)
            end = min(len(text), match.end() + 120)
            context = text[start:end]
            monthly_zar = salary_to_monthly_zar(amount, currency, context)
            # Ignore tiny values that are unlikely to be salary figures.
            if monthly_zar >= 1000:
                candidates.append((monthly_zar, currency, normalize_space(context)))

    if not candidates:
        return "", "No salary found; assess compensation before applying."

    best = max(candidates, key=lambda item: item[0])
    monthly_zar, currency, context = best
    estimate = f"Estimated salary: about R{monthly_zar:,.0f}/month equivalent from {currency} figure."
    if monthly_zar >= target_zar_monthly:
        return estimate + f" This meets the R{target_zar_monthly:,.0f}/month target.", ""
    return "", estimate + f" This is below the R{target_zar_monthly:,.0f}/month target; assess before applying. Context: {context[:180]}"


def assess_role_level(title: str, text: str) -> tuple[int, list[str], list[str]]:
    lower_title = title.lower()
    lower_text = text.lower()
    delta = 0
    reasons: list[str] = []
    concerns: list[str] = []

    entry_hits = [term for term in ENTRY_LEVEL_SIGNALS if term in lower_title]
    if entry_hits:
        delta += min(18, 7 * len(entry_hits))
        reasons.append("Career-level fit: " + ", ".join(entry_hits[:4]))

    senior_hits = [
        term
        for term in SENIORITY_WARNINGS
        if term in lower_title or (term.endswith("+ years") and term in lower_text)
    ]
    manager_like = any(
        term in lower_title
        for term in ["manager", "director", "head of", "vice president", "vp ", "principal", "lead "]
    )
    if senior_hits:
        delta -= 34 if manager_like else 26
        concerns.append("Possible seniority mismatch: " + ", ".join(senior_hits[:4]))
    elif "manager" in lower_title and not any(term in lower_title for term in ["assistant", "junior", "intern", "trainee"]):
        delta -= 28
        concerns.append("Not an early-career role: manager title is above graduate/junior level.")

    hard_non_target_hits = [term for term in HARD_NON_TARGET_TITLE_SIGNALS if term in lower_title]
    if hard_non_target_hits:
        delta -= 45
        concerns.append("Role-title mismatch for marketing target: " + ", ".join(hard_non_target_hits[:4]))

    if any(term in lower_text for term in ["board-certified", "board eligible", "fellowship-trained", "clinical practice", "patient care"]):
        delta -= 50
        concerns.append("Role-title mismatch for marketing target: licensed medical/clinical role.")

    has_marketing_title = any(
        term in lower_title
        for term in [
            "marketing",
            "brand",
            "content",
            "social",
            "communications",
            "campaign",
            "advertising",
            "creative strategist",
            "copywriter",
            "content creator",
            "marketing coordinator",
            "marketing specialist",
            "marketing executive",
            "brand coordinator",
            "brand specialist",
            "social media coordinator",
            "social media specialist",
        ]
    )
    non_target_hits = [term for term in NON_TARGET_TITLE_SIGNALS if term in lower_title]
    if non_target_hits and not has_marketing_title:
        delta -= 35
        concerns.append("Role-title mismatch for marketing target: " + ", ".join(non_target_hits[:4]))

    return delta, reasons, concerns


def assess_location_fit(location: str, text: str) -> tuple[int, list[str], list[str]]:
    loc_lower = location.lower()
    lower = f"{location} {text}".lower()
    text_lower = text.lower()
    delta = 0
    reasons: list[str] = []
    concerns: list[str] = []
    location_has_local_presence = any(term in loc_lower for term in ["hybrid", "on-site", "onsite", "office", "in person", "in-person"])
    remote = (
        "remote" in loc_lower
        or "work from home" in loc_lower
        or (
            not location_has_local_presence
            and any(
                pattern in lower
                for pattern in [
                    "this role is remote",
                    "fully remote",
                    "remote role",
                    "remote position",
                    "work remotely",
                    "remote-first",
                ]
            )
        )
    )
    cape_town = any(term in loc_lower for term in ["cape town", "western cape"])
    south_africa = any(term in loc_lower for term in ["south africa", "cape town", "western cape", "johannesburg", "durban", "pretoria", "za "])
    non_cape_town_sa = south_africa and not cape_town and any(
        term in loc_lower
        for term in ["johannesburg", "durban", "pretoria", "gauteng", "kwazulu", "kwazulu-natal", "sandton"]
    )
    uk = any(term in loc_lower for term in ["united kingdom", " uk", "gb", "london", "wales", "england", "scotland"])
    europe = any(term in loc_lower for term in ["europe", "emea", "ireland", "dublin", "milan", "munich", "berlin", "amsterdam", "paris", "spain", "italy", "germany", "netherlands"])
    us = any(
        term in loc_lower
        for term in [
            "united states",
            " usa",
            " us",
            "new york",
            "san francisco",
            "california",
            "seattle",
            "boston",
            "chicago",
            "los angeles",
            "austin",
            "miami",
            "nyc",
            " ma",
            " ma,",
            " wa",
            " wa,",
            " ca ",
            " ca,",
            "ny ",
            "ny,",
            "nj",
        ]
    )
    outside_cape_physical = any(term in loc_lower for term in OUTSIDE_CAPE_PHYSICAL_TERMS)
    remote_location_allowed = any(term in f" {loc_lower} " for term in REMOTE_ALLOWED_LOCATION_TERMS)
    remote_location_restricted = any(term in loc_lower for term in REMOTE_RESTRICTED_LOCATION_TERMS)
    remote_tied_to_specific_city = (
        remote
        and (
            any(term in loc_lower for term in OUTSIDE_CAPE_PHYSICAL_TERMS)
            or loc_lower.startswith("remote - ")
        )
        and not any(term in loc_lower for term in ["worldwide", "anywhere", "global", "europe", "emea", "uk", "united kingdom", "usa", "united states", "south africa"])
    )
    text_remote_restricted = (
        remote
        and any(pattern in text_lower for pattern in REMOTE_RESTRICTION_PATTERNS)
        and not any(term in text_lower for term in ["work from anywhere", "anywhere in the world", "globally remote", "global remote"])
        and not any(term in text_lower for term in ["south africa", "cape town"])
    )
    remote_based_elsewhere = (
        remote
        and outside_cape_physical
        and not cape_town
        and "remote" not in loc_lower
        and any(pattern in lower for pattern in ["remote role based in", "remote position based in", "based in dublin", "based in ireland"])
    )

    if remote:
        delta += 14
        reasons.append("Remote-friendly location signal.")
    if remote_based_elsewhere:
        delta -= 24
        concerns.append("Remote role appears based in a physical location outside Cape Town; confirm South Africa eligibility before applying.")
    elif remote_tied_to_specific_city:
        delta -= 24
        concerns.append("Remote role is tied to a specific city/country; confirm South Africa eligibility before applying.")
    elif remote and remote_location_restricted and not remote_location_allowed:
        delta -= 20
        concerns.append("Remote role appears restricted to locations outside Phillip's Cape Town/USA/UK/Europe target; avoid unless eligibility is clear.")
    elif text_remote_restricted:
        delta -= 26
        concerns.append("Remote role text suggests geographic restrictions; confirm South Africa eligibility before applying.")
    if cape_town:
        delta += 18
        reasons.append("Cape Town in-person/hybrid location fit.")
    elif non_cape_town_sa and not remote:
        delta -= 28
        concerns.append("In-person South African role appears outside Cape Town; avoid unless Phillip approves it.")
    elif south_africa and remote:
        delta += 10
        reasons.append("South Africa remote location fit.")
    elif south_africa:
        delta -= 16
        concerns.append("South African role is not clearly Cape Town or remote; confirm before applying.")
    elif uk:
        if remote:
            delta += 8
            reasons.append("UK remote location may fit; confirm details.")
        else:
            delta -= 10
            concerns.append("UK in-person role would require relocation; avoid unless Phillip approves it.")
    elif europe and remote:
        delta += 7
        reasons.append("European remote location signal.")
    elif europe:
        delta -= 16
        concerns.append("Europe-based in-person role would require relocation or local authorization; avoid unless Phillip approves it.")
    elif us and not remote:
        delta -= 28
        concerns.append("US non-remote role does not fit Cape Town/remote preference.")
    elif any(term in loc_lower for term in ["dubai", "australia", "malaysia", "petaling jaya", "singapore", "cairo", "egypt"]) and not remote:
        delta -= 20
        concerns.append("Location appears outside Cape Town/remote target; assess before applying.")

    if "hybrid" in loc_lower and not cape_town:
        delta -= 18
        concerns.append("Hybrid role may require a local presence outside Cape Town.")
    elif "hybrid" in lower and not cape_town and not remote:
        delta -= 18
        concerns.append("Hybrid role may require a local presence outside Cape Town.")

    if loc_lower and not cape_town and not remote and not any("outside Cape Town/remote target" in concern for concern in concerns):
        delta -= 22
        concerns.append("Physical location is not Cape Town and the role is not clearly remote; avoid unless Phillip approves it.")

    return delta, reasons, concerns


def score_job(job: dict[str, Any]) -> tuple[int, str, str]:
    text = " ".join(
        [
            job.get("title", ""),
            job.get("company", ""),
            job.get("location", ""),
            job.get("description", ""),
        ]
    )
    base, marketing_hits = keyword_score(text, MARKETING_KEYWORDS)
    preferred, preferred_hits = keyword_score(text, PREFERRED_KEYWORDS)
    location, location_hits = keyword_score(text, LOCATION_KEYWORDS)
    total = min(100, base + preferred + location)

    reasons: list[str] = []
    concerns: list[str] = []
    if marketing_hits:
        reasons.append("Marketing fit: " + ", ".join(marketing_hits[:8]))
    if preferred_hits:
        reasons.append("Preferred industry signal: " + ", ".join(preferred_hits[:8]))
    if location_hits:
        reasons.append("Location/remote fit: " + ", ".join(location_hits[:6]))
    if not marketing_hits:
        concerns.append("Low marketing keyword match; review manually before spending time.")
    lower = text.lower()
    level_delta, level_reasons, level_concerns = assess_role_level(job.get("title", ""), text)
    total += level_delta
    reasons.extend(level_reasons)
    concerns.extend(level_concerns)
    location_delta, location_reasons, location_concerns = assess_location_fit(job.get("location", ""), text)
    total += location_delta
    reasons.extend(location_reasons)
    concerns.extend(location_concerns)
    scam = [term for term in SCAM_WARNINGS if term in lower]
    if scam:
        total -= 30
        concerns.append("Potential scam signal: " + ", ".join(scam[:4]))
    if not reasons:
        reasons.append("Needs manual review; limited match evidence found.")
    salary_reason, salary_concern = assess_salary_text(text)
    if salary_reason:
        reasons.append(salary_reason)
    if salary_concern:
        concerns.append(salary_concern)
        if "below the" in salary_concern.lower():
            total -= 25
    if int(job.get("too_senior") or 0):
        total -= 30
        concerns.append("Phillip marked this role as too senior for the current search.")
    prior_reject = str(job.get("reject_reason") or "").lower()
    if "not really marketing" in prior_reject:
        total -= 40
        concerns.append("Previously rejected as not really marketing; review before reconsidering.")
    elif "wrong location" in prior_reject:
        total -= 35
        concerns.append("Previously rejected due to wrong location; confirm eligibility before reconsidering.")
    total = max(0, min(100, total))
    return total, "\n".join(reasons), "\n".join(concerns)


def graduate_query_terms(query: str = "") -> list[str]:
    return query_terms_from_text(query or GRADUATE_MARKETING_DISCOVERY_QUERY, GRADUATE_MARKETING_DISCOVERY_QUERY)


def should_keep_discovered_role(title: str, company: str, description: str, query: str = "", location: str = "", url: str = "") -> bool:
    if url and is_paywalled_or_gated_source(url):
        return False
    lower_title = normalize_space(title).lower()
    lower_description = normalize_space(description).lower()
    lower_location = normalize_space(location).lower()
    combined = f"{lower_title} {normalize_space(company).lower()} {lower_description} {lower_location}"
    if not lower_title:
        return False
    if any(term in combined for term in ["werkstudent", "praktikant", "praktikum", "pflichtpraktikum", "m/w/d", "100 prozent im home-office", "100% homeoffice", "unpaid internship", "mandatory 6 months unpaid internship"]):
        return False
    if any(term in lower_title for term in HARD_NON_TARGET_TITLE_SIGNALS):
        return False
    if any(term in lower_title for term in ["engineer", "developer", "devops", "backend", "frontend", "designer"]):
        return False
    if any(term in lower_title for term in ["manager", "director", "head of", "vice president", "vp ", "principal"]) and not any(term in lower_title for term in ["assistant", "junior", "graduate", "associate", "coordinator", "specialist", "executive"]):
        return False
    _, _, location_concerns = assess_location_fit(location, f"{title}\n{description}")
    location_concerns_text = " ".join(location_concerns).lower()
    if any(
        term in location_concerns_text
        for term in [
            "physical location is not cape town",
            "outside cape town/remote target",
            "us non-remote",
            "would require relocation",
            "remote role appears based",
            "remote role is tied to a specific city/country",
            "remote role appears restricted",
            "remote role text suggests geographic restrictions",
            "location appears outside cape town/remote target",
        ]
    ):
        return False
    marketing_title = any(term in lower_title for term in MARKETING_TITLE_SIGNALS)
    entry_title = any(term in lower_title for term in ENTRY_LEVEL_SIGNALS)
    graduate_terms = graduate_query_terms(query)
    query_hit = any(term in combined for term in graduate_terms)
    description_marketing = any(term in combined for term in ["marketing", "brand", "content", "social media", "campaign", "community", "growth", "communications", "paid media", "copywriter"])
    if marketing_title and entry_title:
        return True
    if marketing_title and query_hit:
        return True
    if marketing_title and description_marketing and not any(term in lower_title for term in ["manager", "director", "head of", "vice president", "vp ", "principal"]):
        return True
    if marketing_title and query_hit and description_marketing and not any(term in lower_title for term in NON_TARGET_TITLE_SIGNALS):
        return True
    return False


def upsert_job(conn: sqlite3.Connection, job: dict[str, Any]) -> int:
    title = normalize_space(job.get("title", "")) or "Untitled role"
    company = normalize_space(job.get("company", "")) or "Unknown company"
    location = normalize_space(job.get("location", ""))
    url = normalize_space(job.get("url", ""))
    source = normalize_space(job.get("source", "")) or "manual"
    description = normalize_space(job.get("description", ""))
    raw_json = json.dumps(job.get("raw_json", {}), ensure_ascii=True)
    score, reasons, concerns = score_job(
        {
            "title": title,
            "company": company,
            "location": location,
            "description": description,
        }
    )
    timestamp = now_iso()
    if url:
        existing = conn.execute("select id, status from jobs where url = ?", (url,)).fetchone()
    else:
        existing = None
    if existing:
        # Never overwrite a job Phillip already rejected — it stays gone
        if str(existing["status"]) == "rejected":
            return int(existing["id"])
        conn.execute(
            """
            update jobs
            set title=?, company=?, location=?, source=?, description=?, raw_json=?,
                score=?, score_reasons=?, concerns=?, updated_at=?
            where id=?
            """,
            (title, company, location, source, description, raw_json, score, reasons, concerns, timestamp, existing["id"]),
        )
        conn.commit()
        return int(existing["id"])

    # Before inserting, check title+company fingerprint so the same role from a
    # different source URL doesn't re-surface after being rejected.
    title_fp = title.lower().strip()
    company_fp = company.lower().strip()
    dup_rejected = conn.execute(
        "select id from jobs where lower(trim(title))=? and lower(trim(company))=? and status='rejected'",
        (title_fp, company_fp),
    ).fetchone()
    if dup_rejected:
        return int(dup_rejected["id"])

    cur = conn.execute(
        """
        insert into jobs(title, company, location, url, source, description, raw_json,
                         score, score_reasons, concerns, created_at, updated_at)
        values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (title, company, location, url, source, description, raw_json, score, reasons, concerns, timestamp, timestamp),
    )
    conn.commit()
    return int(cur.lastrowid)


def discover_greenhouse(conn: sqlite3.Connection, board_token: str, query: str = "") -> dict[str, Any]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{urllib.parse.quote(board_token)}/jobs?content=true"
    status, body, _ = fetch_url(url)
    if status >= 400:
        raise RuntimeError(f"Greenhouse returned HTTP {status}")
    payload = json.loads(body)
    ids: list[int] = []
    for item in payload.get("jobs", []):
        offices = item.get("offices") or []
        location = ", ".join([office.get("name", "") for office in offices if office.get("name")])
        if not location:
            location = item.get("location", {}).get("name", "")
        job_url = item.get("absolute_url") or ""
        title = str(item.get("title", "") or "")
        company = str(payload.get("name", board_token) or board_token)
        description = plain_text_from_html(item.get("content", ""))
        if query and not should_keep_discovered_role(title, company, description, query, location):
            continue
        ids.append(
            upsert_job(
                conn,
                {
                    "title": title,
                    "company": company,
                    "location": location,
                    "url": job_url,
                    "source": f"greenhouse:{board_token}",
                    "description": description,
                    "raw_json": item,
                },
            )
        )
    return {"count": len(ids), "ids": ids}


def discover_lever(conn: sqlite3.Connection, site: str, query: str = "") -> dict[str, Any]:
    url = f"https://api.lever.co/v0/postings/{urllib.parse.quote(site)}?mode=json"
    status, body, _ = fetch_url(url)
    if status >= 400:
        raise RuntimeError(f"Lever returned HTTP {status}")
    payload = json.loads(body)
    ids: list[int] = []
    for item in payload:
        categories = item.get("categories") or {}
        description = "\n\n".join(
            [
                plain_text_from_html(item.get("descriptionPlain") or item.get("description", "")),
                "\n".join(
                    f"{lst.get('text', '')}\n" + "\n".join(lst.get("content", []))
                    for lst in item.get("lists", [])
                ),
            ]
        )
        title = str(item.get("text", "") or "")
        if query and not should_keep_discovered_role(title, site, description, query, categories.get("location", "")):
            continue
        ids.append(
            upsert_job(
                conn,
                {
                    "title": title,
                    "company": site,
                    "location": categories.get("location", ""),
                    "url": item.get("hostedUrl") or item.get("applyUrl") or "",
                    "source": f"lever:{site}",
                    "description": description,
                    "raw_json": item,
                },
            )
        )
    return {"count": len(ids), "ids": ids}


def discover_ashby(conn: sqlite3.Connection, board: str, query: str = "") -> dict[str, Any]:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{urllib.parse.quote(board)}?includeCompensation=true"
    status, body, _ = fetch_url(url)
    if status >= 400:
        raise RuntimeError(f"Ashby returned HTTP {status}")
    payload = json.loads(body)
    ids: list[int] = []
    for item in payload.get("jobs", []):
        location = item.get("location") or ""
        description = plain_text_from_html(item.get("descriptionHtml") or item.get("descriptionPlain") or "")
        job_url = item.get("jobUrl") or item.get("applyUrl") or ""
        title = str(item.get("title", "") or "")
        if query and not should_keep_discovered_role(title, board, description, query, location):
            continue
        ids.append(
            upsert_job(
                conn,
                {
                    "title": title,
                    "company": board,
                    "location": location,
                    "url": job_url,
                    "source": f"ashby:{board}",
                    "description": description,
                    "raw_json": item,
                },
            )
        )
    return {"count": len(ids), "ids": ids}


def discover_smartrecruiters(conn: sqlite3.Connection, company_identifier: str, query: str = "") -> dict[str, Any]:
    params = {"limit": "100"}
    if query:
        params["q"] = query
    url = (
        f"https://api.smartrecruiters.com/v1/companies/"
        f"{urllib.parse.quote(company_identifier)}/postings?{urllib.parse.urlencode(params)}"
    )
    status, body, _ = fetch_url(url)
    if status >= 400:
        raise RuntimeError(f"SmartRecruiters returned HTTP {status}")
    payload = json.loads(body)
    items = payload.get("content") or payload.get("postings") or []
    ids: list[int] = []
    for item in items:
        posting_id = item.get("id") or item.get("uuid") or ""
        detail = item
        description = ""
        if posting_id:
            try:
                detail_url = (
                    f"https://api.smartrecruiters.com/v1/companies/"
                    f"{urllib.parse.quote(company_identifier)}/postings/{urllib.parse.quote(str(posting_id))}"
                )
                detail_status, detail_body, _ = fetch_url(detail_url, timeout=12)
                if detail_status < 400:
                    detail = json.loads(detail_body)
            except Exception:
                detail = item
        location_data = detail.get("location") or item.get("location") or {}
        if isinstance(location_data, dict):
            location = ", ".join(
                str(location_data.get(key, ""))
                for key in ["city", "region", "country"]
                if location_data.get(key)
            )
        else:
            location = str(location_data or "")
        description_parts = [
            detail.get("jobAd", {}).get("sections", {}).get("jobDescription", {}).get("text", "")
            if isinstance(detail.get("jobAd"), dict)
            else "",
            detail.get("description", ""),
            detail.get("qualifications", ""),
        ]
        description = plain_text_from_html("\n\n".join(str(part) for part in description_parts if part))
        title = str(detail.get("name") or item.get("name") or "")
        if query and not should_keep_discovered_role(title, company_identifier, description, query, location):
            continue
        apply_url = detail.get("applyUrl") or item.get("applyUrl") or ""
        ref_url = detail.get("ref") or item.get("ref") or detail.get("postingUrl") or item.get("postingUrl") or ""
        if not apply_url and ref_url:
            sr_match = re.match(r"https?://(?:www\.)?smartrecruiters\.com/(.+)", ref_url)
            if sr_match:
                apply_url = f"https://jobs.smartrecruiters.com/{sr_match.group(1)}"
        job_url = apply_url or ref_url
        ids.append(
            upsert_job(
                conn,
                {
                    "title": title,
                    "company": company_identifier,
                    "location": location,
                    "url": job_url,
                    "source": f"smartrecruiters:{company_identifier}",
                    "description": description or json.dumps(detail, ensure_ascii=True)[:8000],
                    "raw_json": detail,
                },
            )
        )
    return {"count": len(ids), "ids": ids}


def discover_recruitee(conn: sqlite3.Connection, subdomain: str, query: str = "") -> dict[str, Any]:
    url = f"https://{urllib.parse.quote(subdomain)}.recruitee.com/api/offers/"
    status, body, _ = fetch_url(url)
    if status >= 400:
        raise RuntimeError(f"Recruitee returned HTTP {status}")
    payload = json.loads(body)
    offers = payload.get("offers") if isinstance(payload, dict) else payload
    if not isinstance(offers, list):
        offers = []
    ids: list[int] = []
    for item in offers:
        if not isinstance(item, dict):
            continue
        description = "\n\n".join(
            str(item.get(key, ""))
            for key in ["description", "requirements", "careers_description", "careers_requirements"]
            if item.get(key)
        )
        title = str(item.get("title", "") or "")
        if query and not should_keep_discovered_role(title, subdomain, plain_text_from_html(description or ""), query, location):
            continue
        location_data = item.get("location") or {}
        if isinstance(location_data, dict):
            location = ", ".join(str(location_data.get(key, "")) for key in ["city", "country"] if location_data.get(key))
        else:
            location = str(location_data or item.get("location_name") or "")
        job_url = item.get("careers_url") or item.get("careers_apply_url") or item.get("url") or ""
        if not job_url and item.get("slug"):
            job_url = f"https://{subdomain}.recruitee.com/o/{item.get('slug')}"
        ids.append(
            upsert_job(
                conn,
                {
                    "title": title,
                    "company": subdomain,
                    "location": location,
                    "url": job_url,
                    "source": f"recruitee:{subdomain}",
                    "description": plain_text_from_html(description or json.dumps(item, ensure_ascii=True)[:8000]),
                    "raw_json": item,
                },
            )
        )
    return {"count": len(ids), "ids": ids}


def discover_remotive(conn: sqlite3.Connection, category: str = "marketing", query: str = "") -> dict[str, Any]:
    params = {}
    if category:
        params["category"] = category
    if query:
        params["search"] = query
    url = "https://remotive.com/api/remote-jobs"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    status, body, _ = fetch_url(url, timeout=25)
    if status >= 400:
        raise RuntimeError(f"Remotive returned HTTP {status}")
    payload = json.loads(body)
    jobs = payload.get("jobs") if isinstance(payload, dict) else []
    if not isinstance(jobs, list):
        jobs = []
    ids: list[int] = []
    for item in jobs[:120]:
        if not isinstance(item, dict):
            continue
        title = normalize_space(str(item.get("title") or ""))
        description = plain_text_from_html(str(item.get("description") or ""))
        location = normalize_space(str(item.get("candidate_required_location") or "Remote"))
        if location and "remote" not in location.lower():
            location = f"Remote - {location}"
        else:
            location = location or "Remote"
        company = normalize_space(str(item.get("company_name") or item.get("company") or "Remotive company"))
        job_url = str(item.get("url") or "")
        if not job_url and item.get("id"):
            job_url = f"https://remotive.com/remote-jobs/{item.get('id')}"
        tags = item.get("tags") if isinstance(item.get("tags"), list) else []
        if not should_keep_discovered_role(title, company, description + " " + " ".join(str(tag) for tag in tags), query, location):
            continue
        ids.append(
            upsert_job(
                conn,
                {
                    "title": title,
                    "company": company,
                    "location": location,
                    "url": job_url,
                    "source": f"remotive:{category or 'all'}",
                    "description": "\n\n".join(
                        part
                        for part in [
                            description,
                            f"Category: {item.get('category', '')}",
                            f"Tags: {', '.join(str(tag) for tag in tags)}" if tags else "",
                            f"Source: Remotive. Link back to Remotive job URL: {job_url}",
                        ]
                        if part
                    ),
                    "raw_json": item,
                },
            )
        )
    return {"count": len(ids), "ids": ids, "mode": "remotive-public-api"}


def query_terms_from_text(value: str, fallback: str = "") -> list[str]:
    return [
        term.strip().lower()
        for term in re.split(r"[,|\s]+", value or fallback)
        if len(term.strip()) > 2
    ]


def discover_remoteok(conn: sqlite3.Connection, token: str = "", query: str = "") -> dict[str, Any]:
    status, body, _ = fetch_url("https://remoteok.com/api", timeout=25)
    if status >= 400:
        raise RuntimeError(f"Remote OK returned HTTP {status}")
    payload = json.loads(body)
    if not isinstance(payload, list):
        payload = []
    query_terms = query_terms_from_text(query or token, "marketing brand content social media community copywriter")
    ids: list[int] = []
    for item in payload[:300]:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        title = normalize_space(str(item.get("position") or item.get("title") or ""))
        company = normalize_space(str(item.get("company") or "Remote OK company"))
        tags = item.get("tags") if isinstance(item.get("tags"), list) else []
        description = plain_text_from_html(str(item.get("description") or ""))
        combined = " ".join([title, company, description, " ".join(str(tag) for tag in tags)]).lower()
        if query_terms and not any(term in combined for term in query_terms):
            continue
        if not should_keep_discovered_role(title, company, description + " " + " ".join(str(tag) for tag in tags), query or token, normalize_space(str(item.get("location") or "Remote - Worldwide")) or "Remote - Worldwide"):
            continue
        job_url = str(item.get("url") or "")
        if job_url and job_url.startswith("/"):
            job_url = urllib.parse.urljoin("https://remoteok.com", job_url)
        if not job_url:
            slug = str(item.get("slug") or item.get("id"))
            job_url = f"https://remoteok.com/remote-jobs/{slug}"
        ids.append(
            upsert_job(
                conn,
                {
                    "title": title,
                    "company": company,
                    "location": normalize_space(str(item.get("location") or "Remote - Worldwide")) or "Remote - Worldwide",
                    "url": job_url,
                    "source": "remoteok",
                    "description": "\n\n".join(
                        part
                        for part in [
                            description,
                            f"Tags: {', '.join(str(tag) for tag in tags)}" if tags else "",
                            f"Source: Remote OK. Link back to Remote OK job URL: {job_url}",
                        ]
                        if part
                    ),
                    "raw_json": item,
                },
            )
        )
    return {"count": len(ids), "ids": ids, "mode": "remoteok-public-api"}


def discover_arbeitnow(conn: sqlite3.Connection, token: str = "", query: str = "") -> dict[str, Any]:
    url = "https://www.arbeitnow.com/api/job-board-api"
    status, body, _ = fetch_url(url, timeout=25)
    if status >= 400:
        raise RuntimeError(f"Arbeitnow returned HTTP {status}")
    payload = json.loads(body)
    jobs = payload.get("data") if isinstance(payload, dict) else []
    if not isinstance(jobs, list):
        jobs = []
    query_terms = query_terms_from_text(query or token, "marketing brand content social media community copywriter growth")
    ids: list[int] = []
    for item in jobs[:100]:
        if not isinstance(item, dict):
            continue
        title = normalize_space(str(item.get("title") or ""))
        company = normalize_space(str(item.get("company_name") or item.get("company") or "Arbeitnow company"))
        description = plain_text_from_html(str(item.get("description") or ""))
        tags = item.get("tags") if isinstance(item.get("tags"), list) else []
        combined = " ".join([title, company, description, " ".join(str(tag) for tag in tags)]).lower()
        if query_terms and not any(term in combined for term in query_terms):
            continue
        if not should_keep_discovered_role(title, company, description + " " + " ".join(str(tag) for tag in tags), query or token, f"Remote - {normalize_space(str(item.get('location') or ''))}" if item.get('remote') and normalize_space(str(item.get('location') or '')) else (normalize_space(str(item.get('location') or '')) or ('Remote - Europe' if item.get('remote') else ''))):
            continue
        location = normalize_space(str(item.get("location") or ""))
        if item.get("remote"):
            location = f"Remote - {location}" if location else "Remote - Europe"
        job_url = str(item.get("url") or item.get("job_url") or item.get("slug") or "")
        ids.append(
            upsert_job(
                conn,
                {
                    "title": title,
                    "company": company,
                    "location": location,
                    "url": job_url,
                    "source": "arbeitnow",
                    "description": "\n\n".join(
                        part
                        for part in [
                            description,
                            f"Tags: {', '.join(str(tag) for tag in tags)}" if tags else "",
                            f"Source: Arbeitnow. Link back to job URL: {job_url}" if job_url else "Source: Arbeitnow.",
                        ]
                        if part
                    ),
                    "raw_json": item,
                },
            )
        )
    return {"count": len(ids), "ids": ids, "mode": "arbeitnow-public-api"}


def _parse_rss_items(body: str) -> list[ET.Element]:
    """Parse an RSS/Atom body and return the list of <item> elements."""
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        # Some feeds have a BOM or encoding declaration — strip it and retry
        body = body.lstrip("﻿").split("?>", 1)[-1]
        root = ET.fromstring(body)
    ns_strip = re.compile(r"\{[^}]*\}")
    channel = root.find("channel")
    if channel is None:
        # Atom feed fallback
        return root.findall("{http://www.w3.org/2005/Atom}entry")
    return channel.findall("item")


def _rss_text(item: ET.Element, tag: str, default: str = "") -> str:
    """Get text of a child tag from an RSS item, ignoring namespace."""
    el = item.find(tag)
    if el is not None and el.text:
        return normalize_space(el.text)
    # Try stripping namespace prefix from all children
    for child in item:
        local = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if local == tag and child.text:
            return normalize_space(child.text)
    return default


def discover_indeed_rss(conn: sqlite3.Connection, token: str = "", query: str = "") -> dict[str, Any]:
    """
    Scrape Indeed's public RSS feed for SA and remote marketing roles.
    token = location string, e.g. 'Cape Town, Western Cape' or 'remote'.
    Tries za.indeed.com first, falls back to www.indeed.com for remote.
    """
    location = token or "Cape Town, Western Cape"
    search_q = query or "marketing junior graduate"
    ids: list[int] = []
    endpoints = [
        f"https://za.indeed.com/rss?q={urllib.parse.quote_plus(search_q)}&l={urllib.parse.quote_plus(location)}&sort=date&fromage=30",
        f"https://www.indeed.com/rss?q={urllib.parse.quote_plus(search_q + ' remote')}&sort=date&fromage=14",
    ]
    seen_urls: set[str] = set()
    for feed_url in endpoints:
        try:
            status, body, _ = fetch_url(feed_url, timeout=25)
        except Exception:
            continue
        if status >= 400:
            continue
        try:
            items = _parse_rss_items(body)
        except Exception:
            continue
        for item in items[:60]:
            title = _rss_text(item, "title")
            job_url = _rss_text(item, "link") or _rss_text(item, "guid")
            description = plain_text_from_html(_rss_text(item, "description"))
            job_location = _rss_text(item, "location") or location
            # Indeed often puts "Role - Company" in the title
            company = ""
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                title = parts[0].strip()
                company = parts[1].strip()
            if not title or not job_url or job_url in seen_urls:
                continue
            seen_urls.add(job_url)
            if not should_keep_discovered_role(title, company, description, query, job_location, job_url):
                continue
            ids.append(upsert_job(conn, {
                "title": title,
                "company": company or "Indeed listing",
                "location": job_location,
                "url": job_url,
                "source": f"indeed_rss:{location}",
                "description": description,
                "raw_json": {"source": "indeed_rss", "feed": feed_url},
            }))
    return {"count": len(ids), "ids": ids, "mode": "indeed-rss"}


def discover_weworkremotely_rss(conn: sqlite3.Connection, token: str = "", query: str = "") -> dict[str, Any]:
    """
    Fetch WeWorkRemotely marketing RSS feed.
    token = WWR category slug, defaults to 'remote-marketing-jobs'.
    """
    category = token or "remote-marketing-jobs"
    feed_url = f"https://weworkremotely.com/categories/{urllib.parse.quote(category)}.rss"
    status, body, _ = fetch_url(feed_url, timeout=25)
    if status >= 400:
        # Fall back to the full jobs RSS
        feed_url = "https://weworkremotely.com/remote-jobs.rss"
        status, body, _ = fetch_url(feed_url, timeout=25)
        if status >= 400:
            raise RuntimeError(f"WeWorkRemotely RSS returned HTTP {status}")
    try:
        items = _parse_rss_items(body)
    except Exception as exc:
        raise RuntimeError(f"WeWorkRemotely RSS parse error: {exc}")
    ids: list[int] = []
    for item in items[:80]:
        title = _rss_text(item, "title")
        job_url = _rss_text(item, "link") or _rss_text(item, "guid")
        description = plain_text_from_html(_rss_text(item, "description"))
        region = _rss_text(item, "region") or "Worldwide"
        company = _rss_text(item, "company")
        # WWR title format: "Company: Role Title"
        if ": " in title and not company:
            parts = title.split(": ", 1)
            company = parts[0].strip()
            title = parts[1].strip()
        if not title or not job_url:
            continue
        job_location = f"Remote - {region}" if "remote" not in region.lower() else region
        if not should_keep_discovered_role(title, company, description, query, job_location, job_url):
            continue
        ids.append(upsert_job(conn, {
            "title": title,
            "company": company or "WeWorkRemotely listing",
            "location": job_location,
            "url": job_url,
            "source": "weworkremotely_rss",
            "description": description,
            "raw_json": {"source": "weworkremotely_rss", "region": region, "feed": feed_url},
        }))
    return {"count": len(ids), "ids": ids, "mode": "weworkremotely-rss"}


def discover_adzuna(conn: sqlite3.Connection, token: str = "", query: str = "") -> dict[str, Any]:
    """
    Adzuna job search API — has a South Africa endpoint.
    token = 'app_id:app_key'  OR set ADZUNA_APP_ID / ADZUNA_APP_KEY in .env.
    Free tier: 250 calls/day. Covers Cape Town, Johannesburg, remote SA roles.
    Sign up at: https://developer.adzuna.com/
    """
    app_id = ""
    app_key = ""
    if ":" in token:
        parts = token.split(":", 1)
        app_id = parts[0].strip()
        app_key = parts[1].strip()
    app_id = app_id or os.environ.get("ADZUNA_APP_ID", "")
    app_key = app_key or os.environ.get("ADZUNA_APP_KEY", "")
    if not app_id or not app_key:
        raise RuntimeError(
            "Adzuna needs credentials. Add ADZUNA_APP_ID and ADZUNA_APP_KEY to your .env file "
            "— free tier at https://developer.adzuna.com/"
        )
    search_q = query or "marketing junior graduate"
    params = urllib.parse.urlencode({
        "app_id": app_id,
        "app_key": app_key,
        "results_per_page": 50,
        "what": search_q,
        "where": "Cape Town",
        "sort_by": "date",
        "distance": 50,
    })
    feed_url = f"https://api.adzuna.com/v1/api/jobs/za/search/1?{params}"
    status, body, _ = fetch_url(feed_url, timeout=25)
    if status >= 400:
        raise RuntimeError(f"Adzuna API returned HTTP {status}: {body[:200]}")
    payload = json.loads(body)
    results = payload.get("results", [])
    ids: list[int] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        title = normalize_space(str(item.get("title") or ""))
        company_obj = item.get("company") or {}
        company = normalize_space(str(company_obj.get("display_name") or ""))
        location_obj = item.get("location") or {}
        location = normalize_space(str(location_obj.get("display_name") or "Cape Town, South Africa"))
        description = normalize_space(str(item.get("description") or ""))
        job_url = normalize_space(str(item.get("redirect_url") or ""))
        if not title or not job_url:
            continue
        if not should_keep_discovered_role(title, company, description, query, location, job_url):
            continue
        ids.append(upsert_job(conn, {
            "title": title,
            "company": company or "Adzuna listing",
            "location": location,
            "url": job_url,
            "source": "adzuna",
            "description": description,
            "raw_json": item,
        }))
    return {"count": len(ids), "ids": ids, "mode": "adzuna-api"}


def discover_jobicy_rss(conn: sqlite3.Connection, token: str = "", query: str = "") -> dict[str, Any]:
    """
    Jobicy remote jobs RSS feed — reliably returns real job data.
    token = category slug, e.g. 'marketing' (default) or 'copywriting'.
    Free, no API key needed. https://jobicy.com
    """
    category = token or "marketing"
    feed_url = (
        f"https://jobicy.com/?feed=job_feed"
        f"&job_categories={urllib.parse.quote(category)}"
        f"&job_types=full-time"
    )
    status, body, _ = fetch_url(feed_url, timeout=25)
    if status >= 400:
        raise RuntimeError(f"Jobicy RSS returned HTTP {status}")
    try:
        items = _parse_rss_items(body)
    except Exception as exc:
        raise RuntimeError(f"Jobicy RSS parse error: {exc}")
    JOBICY_NS = "https://jobicy.com"
    ids: list[int] = []
    for item in items[:60]:
        title = _rss_text(item, "title")
        job_url = _rss_text(item, "link") or _rss_text(item, "guid")
        description = plain_text_from_html(
            _rss_text(item, f"{{{JOBICY_NS}}}description")
            or _rss_text(item, "{http://purl.org/rss/1.0/modules/content/}encoded")
            or _rss_text(item, "description")
        )
        location = _rss_text(item, f"{{{JOBICY_NS}}}location") or "Remote"
        company = _rss_text(item, f"{{{JOBICY_NS}}}company") or ""
        job_type = _rss_text(item, f"{{{JOBICY_NS}}}job_type") or ""
        if "remote" not in location.lower():
            location = f"Remote - {location}"
        if not title or not job_url:
            continue
        if not should_keep_discovered_role(title, company, description, query, location, job_url):
            continue
        ids.append(upsert_job(conn, {
            "title": title,
            "company": company or "Jobicy listing",
            "location": location,
            "url": job_url,
            "source": f"jobicy:{category}",
            "description": "\n\n".join(p for p in [description, f"Type: {job_type}" if job_type else ""] if p),
            "raw_json": {"source": "jobicy_rss", "category": category},
        }))
    return {"count": len(ids), "ids": ids, "mode": "jobicy-rss"}


def discover_workable_public(conn: sqlite3.Connection, token_or_url: str, query: str = "") -> dict[str, Any]:
    account = workable_account_from_token(token_or_url)
    if not account:
        return discover_careers_page(conn, token_or_url, query)
    url = f"https://www.workable.com/api/accounts/{urllib.parse.quote(account)}?details=true"
    status, body, _ = fetch_url(url)
    if status >= 400:
        return discover_careers_page(conn, token_or_url, query)
    payload = json.loads(body)
    jobs = workable_jobs_from_payload(payload)
    ids: list[int] = []
    query_terms = [term.strip().lower() for term in re.split(r"[,| ]+", query or "") if len(term.strip()) > 2]
    for item in jobs:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("full_title") or item.get("name") or "")
        description = plain_text_from_html(
            "\n\n".join(
                str(item.get(key, ""))
                for key in ["description", "description_html", "full_description", "requirements", "benefits"]
                if item.get(key)
            )
        )
        combined = f"{title} {description}".lower()
        if query_terms and not any(term in combined for term in query_terms + ["marketing", "brand", "content"]):
            continue
        location = workable_location_text(item)
        job_url = (
            item.get("url")
            or item.get("application_url")
            or item.get("shortlink")
            or item.get("apply_url")
            or ""
        )
        if not job_url and item.get("shortcode"):
            job_url = f"https://apply.workable.com/{account}/j/{item.get('shortcode')}/"
        ids.append(
            upsert_job(
                conn,
                {
                    "title": title,
                    "company": item.get("company") or item.get("account_name") or account,
                    "location": location,
                    "url": str(job_url),
                    "source": f"workable:{account}",
                    "description": description or json.dumps(item, ensure_ascii=True)[:8000],
                    "raw_json": item,
                },
            )
        )
    return {"count": len(ids), "ids": ids, "mode": "workable-public-api", "account": account}


def workable_account_from_token(token_or_url: str) -> str:
    value = normalize_space(token_or_url)
    if not value:
        return ""
    if "://" not in value and "/" not in value and "." not in value:
        return value.strip("/")
    parsed = urllib.parse.urlparse(value if "://" in value else f"https://{value}")
    host = parsed.netloc.lower().replace("www.", "")
    parts = [part for part in parsed.path.split("/") if part]
    if host == "apply.workable.com" and parts:
        return parts[0]
    if host.endswith(".workable.com") and not host.startswith("www."):
        return host.split(".")[0]
    if host == "workable.com" and "accounts" in parts:
        idx = parts.index("accounts")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    return ""


def workable_jobs_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ["jobs", "results", "positions"]:
        if isinstance(payload.get(key), list):
            return [item for item in payload[key] if isinstance(item, dict)]
    account = payload.get("account") or payload.get("data")
    if isinstance(account, dict):
        return workable_jobs_from_payload(account)
    return []


def workable_location_text(item: dict[str, Any]) -> str:
    location = item.get("location") or item.get("locations") or item.get("location_str") or ""
    if isinstance(location, str):
        return location
    if isinstance(location, dict):
        return normalize_space(
            ", ".join(
                str(location.get(key, ""))
                for key in ["location_str", "city", "region", "country", "country_name"]
                if location.get(key)
            )
        )
    if isinstance(location, list):
        bits = []
        for entry in location:
            if isinstance(entry, str):
                bits.append(entry)
            elif isinstance(entry, dict):
                bits.append(
                    ", ".join(
                        str(entry.get(key, ""))
                        for key in ["city", "region", "country", "country_name"]
                        if entry.get(key)
                    )
                )
        return normalize_space("; ".join(bit for bit in bits if bit))
    return ""


def discover_teamtailor_public(conn: sqlite3.Connection, token_or_url: str, query: str = "") -> dict[str, Any]:
    url = normalize_space(token_or_url)
    if not url:
        raise RuntimeError("Teamtailor URL or subdomain is required.")
    if "://" not in url:
        url = f"https://{url}.teamtailor.com/jobs"
    result = discover_careers_page(conn, url, query or "marketing")
    if result.get("count", 0) == 1 and result.get("mode") == "single-page" and not url.rstrip("/").endswith("/jobs"):
        jobs_url = urllib.parse.urljoin(url.rstrip("/") + "/", "jobs")
        try:
            retry = discover_careers_page(conn, jobs_url, query or "marketing")
            if retry.get("count", 0) >= result.get("count", 0):
                return {**retry, "mode": f"{retry.get('mode', 'linked-jobs')}:teamtailor"}
        except Exception:
            pass
    return {**result, "mode": f"{result.get('mode', 'linked-jobs')}:teamtailor"}


def save_job_source(conn: sqlite3.Connection, data: dict[str, Any]) -> int:
    source_id = int(data.get("id") or 0)
    name = normalize_space(str(data.get("name", "")))
    source_type = normalize_space(str(data.get("source_type", ""))).lower()
    token = normalize_space(str(data.get("token", "")))
    query = normalize_space(str(data.get("query", "")))
    if not query and source_type in {"greenhouse", "lever", "ashby", "smartrecruiters", "recruitee", "remotive", "remoteok", "arbeitnow", "workable", "teamtailor", "careers", "url", "indeed_rss", "weworkremotely_rss", "adzuna", "jobicy_rss"}:
        query = GRADUATE_MARKETING_DISCOVERY_QUERY
    enabled = 1 if data.get("enabled", True) else 0
    if not source_type or not token:
        raise RuntimeError("Source type and token/URL are required.")
    if not name:
        name = f"{source_type}:{token}"
    timestamp = now_iso()
    if source_id:
        conn.execute(
            """
            update job_sources
            set name=?, source_type=?, token=?, query=?, enabled=?, updated_at=?
            where id=?
            """,
            (name, source_type, token, query, enabled, timestamp, source_id),
        )
        conn.commit()
        return source_id
    cur = conn.execute(
        """
        insert into job_sources(name, source_type, token, query, enabled, created_at, updated_at)
        values(?, ?, ?, ?, ?, ?, ?)
        on conflict(source_type, token, query) do update set
            name=excluded.name,
            enabled=excluded.enabled,
            updated_at=excluded.updated_at
        """,
        (name, source_type, token, query, enabled, timestamp, timestamp),
    )
    conn.commit()
    if cur.lastrowid:
        return int(cur.lastrowid)
    existing = conn.execute(
        "select id from job_sources where source_type=? and token=? and query=?",
        (source_type, token, query),
    ).fetchone()
    return int(existing["id"])


def run_job_source(conn: sqlite3.Connection, source: dict[str, Any]) -> dict[str, Any]:
    source_type = str(source.get("source_type", "")).lower()
    token = str(source.get("token", ""))
    query = str(source.get("query", ""))
    if not query and source_type in {"greenhouse", "lever", "ashby", "smartrecruiters", "recruitee", "remotive", "remoteok", "arbeitnow", "workable", "teamtailor", "careers", "url", "indeed_rss", "weworkremotely_rss", "adzuna", "jobicy_rss"}:
        query = GRADUATE_MARKETING_DISCOVERY_QUERY
    if source_type == "greenhouse":
        result = discover_greenhouse(conn, token, query)
    elif source_type == "lever":
        result = discover_lever(conn, token, query)
    elif source_type == "ashby":
        result = discover_ashby(conn, token, query)
    elif source_type == "smartrecruiters":
        result = discover_smartrecruiters(conn, token, query)
    elif source_type == "recruitee":
        result = discover_recruitee(conn, token, query)
    elif source_type == "remotive":
        result = discover_remotive(conn, token or "marketing", query)
    elif source_type == "remoteok":
        raise RuntimeError("RemoteOK is disabled — jobs there require account signup before applying.")
    elif source_type == "arbeitnow":
        result = discover_arbeitnow(conn, token, query)
    elif source_type == "indeed_rss":
        result = discover_indeed_rss(conn, token, query)
    elif source_type == "weworkremotely_rss":
        result = discover_weworkremotely_rss(conn, token, query)
    elif source_type == "adzuna":
        result = discover_adzuna(conn, token, query)
    elif source_type == "jobicy_rss":
        result = discover_jobicy_rss(conn, token, query)
    elif source_type == "workable":
        result = discover_workable_public(conn, token, query)
    elif source_type == "teamtailor":
        result = discover_teamtailor_public(conn, token, query)
    elif source_type == "url":
        result = discover_careers_page(conn, token, query)
    elif source_type in {"careers"}:
        result = discover_careers_page(conn, token, query or source_type)
    else:
        raise RuntimeError(f"Unsupported source type: {source_type}")
    timestamp = now_iso()
    conn.execute(
        "update job_sources set last_run=?, last_result=?, updated_at=? where id=?",
        (timestamp, json.dumps(result, ensure_ascii=True), timestamp, int(source["id"])),
    )
    conn.commit()
    return result


def run_enabled_sources(force: bool = False) -> dict[str, Any]:
    summary = {"ran": 0, "imported": 0, "errors": []}
    today = dt.date.today().isoformat()
    with connect() as conn:
        rows = conn.execute("select * from job_sources where enabled=1 order by id").fetchall()
        for row in rows:
            source = row_to_dict(row) or {}
            last_run = str(source.get("last_run", ""))
            if not force and last_run.startswith(today):
                continue
            try:
                result = run_job_source(conn, source)
                summary["ran"] += 1
                summary["imported"] += int(result.get("count", 0))
            except Exception as exc:
                summary["errors"].append(f"{source.get('name') or source.get('token')}: {exc}")
                conn.execute(
                    "update job_sources set last_run=?, last_result=?, updated_at=? where id=?",
                    (now_iso(), json.dumps({"error": str(exc)}, ensure_ascii=True), now_iso(), int(source["id"])),
                )
                conn.commit()
    return summary


def shortlist_top_jobs(conn: sqlite3.Connection, limit: int = 5) -> dict[str, Any]:
    conn.execute(
        "update jobs set status='new', updated_at=? where status='shortlisted'",
        (now_iso(),),
    )
    rows = conn.execute(
        """
        select id, company, title, score
        from jobs
        where status in ('new', 'drafted', 'shortlisted')
          and coalesce(too_senior, 0) = 0
          and score >= 35
          and lower(concerns) not like '%role-title mismatch%'
          and lower(concerns) not like '%potential scam%'
          and lower(concerns) not like '%below the r22,000/month target%'
          and lower(concerns) not like '%outside south africa/uk/remote target%'
          and lower(concerns) not like '%outside cape town%'
          and lower(concerns) not like '%not clearly cape town or remote%'
          and lower(concerns) not like '%cape town/remote preference%'
          and lower(concerns) not like '%cape town/remote target%'
          and lower(concerns) not like '%physical location is not cape town%'
          and lower(concerns) not like '%listed physical location is not cape town%'
          and lower(concerns) not like '%remote role appears based%'
          and lower(concerns) not like '%remote role is tied to a specific city/country%'
          and lower(concerns) not like '%remote role appears restricted%'
          and lower(concerns) not like '%remote role text suggests geographic restrictions%'
          and lower(concerns) not like '%marked this role as too senior%'
          and lower(concerns) not like '%not an early-career role%'
          and lower(concerns) not like '%would require relocation%'
          and lower(concerns) not like '%local/eu work authorization%'
          and lower(concerns) not like '%us non-remote%'
          and lower(concerns) not like '%hybrid role may require%'
        order by
          (score
            + case when lower(location) like '%cape town%' or lower(location) like '%western cape%' then 6 else 0 end
            - case when lower(concerns) like '%manager title may be above graduate/junior level%' then 4 else 0 end
            - case when lower(concerns) like '%not an early-career role%' then 18 else 0 end
            - case when lower(concerns) like '%possible seniority mismatch%' then 8 else 0 end
          ) desc,
          case when lower(location) like '%cape town%' or lower(location) like '%western cape%' then 1 else 0 end desc,
          case when lower(location) like '%remote%' then 1 else 0 end desc,
          score desc,
          updated_at desc
        limit ?
        """,
        (max(limit * 5, limit),),
    ).fetchall()
    ids: list[int] = []
    seen_roles: set[tuple[str, str]] = set()
    for row in rows:
        key = (
            re.sub(r"\W+", " ", str(row["company"] or "").lower()).strip(),
            re.sub(r"\W+", " ", str(row["title"] or "").lower()).strip(),
        )
        if key in seen_roles:
            continue
        seen_roles.add(key)
        ids.append(int(row["id"]))
        if len(ids) >= limit:
            break
    if ids:
        placeholders = ",".join("?" for _ in ids)
        conn.execute(
            f"update jobs set status='shortlisted', updated_at=? where id in ({placeholders})",
            [now_iso()] + ids,
        )
        conn.commit()
    return {"count": len(ids), "ids": ids}


def shortlist_fresh_jobs(conn: sqlite3.Connection, limit: int = 5) -> dict[str, Any]:
    conn.execute(
        "update jobs set status='new', updated_at=? where status='shortlisted'",
        (now_iso(),),
    )
    rows = conn.execute(
        """
        select jobs.id, jobs.company, jobs.title, jobs.score
        from jobs
        left join applications on applications.job_id = jobs.id
        where jobs.status in ('new', 'drafted', 'shortlisted')
          and applications.id is null
          and coalesce(jobs.too_senior, 0) = 0
          and jobs.score >= 35
          and lower(jobs.concerns) not like '%role-title mismatch%'
          and lower(jobs.concerns) not like '%potential scam%'
          and lower(jobs.concerns) not like '%below the r22,000/month target%'
          and lower(jobs.concerns) not like '%outside south africa/uk/remote target%'
          and lower(jobs.concerns) not like '%outside cape town%'
          and lower(jobs.concerns) not like '%not clearly cape town or remote%'
          and lower(jobs.concerns) not like '%cape town/remote preference%'
          and lower(jobs.concerns) not like '%cape town/remote target%'
          and lower(jobs.concerns) not like '%physical location is not cape town%'
          and lower(jobs.concerns) not like '%listed physical location is not cape town%'
          and lower(jobs.concerns) not like '%remote role appears based%'
          and lower(jobs.concerns) not like '%remote role is tied to a specific city/country%'
          and lower(jobs.concerns) not like '%remote role appears restricted%'
          and lower(jobs.concerns) not like '%remote role text suggests geographic restrictions%'
          and lower(jobs.concerns) not like '%marked this role as too senior%'
          and lower(jobs.concerns) not like '%not an early-career role%'
          and lower(jobs.concerns) not like '%would require relocation%'
          and lower(jobs.concerns) not like '%local/eu work authorization%'
          and lower(jobs.concerns) not like '%us non-remote%'
          and lower(jobs.concerns) not like '%hybrid role may require%'
        order by
          (jobs.score
            + case when lower(jobs.location) like '%cape town%' or lower(jobs.location) like '%western cape%' then 6 else 0 end
            - case when lower(jobs.concerns) like '%manager title may be above graduate/junior level%' then 4 else 0 end
            - case when lower(jobs.concerns) like '%not an early-career role%' then 18 else 0 end
            - case when lower(jobs.concerns) like '%possible seniority mismatch%' then 8 else 0 end
          ) desc,
          case when lower(jobs.location) like '%cape town%' or lower(jobs.location) like '%western cape%' then 1 else 0 end desc,
          case when lower(jobs.location) like '%remote%' then 1 else 0 end desc,
          jobs.score desc,
          jobs.updated_at desc
        limit ?
        """,
        (max(limit * 5, limit),),
    ).fetchall()
    ids: list[int] = []
    seen_roles: set[tuple[str, str]] = set()
    for row in rows:
        key = (
            re.sub(r"\W+", " ", str(row["company"] or "").lower()).strip(),
            re.sub(r"\W+", " ", str(row["title"] or "").lower()).strip(),
        )
        if key in seen_roles:
            continue
        seen_roles.add(key)
        ids.append(int(row["id"]))
        if len(ids) >= limit:
            break
    if ids:
        placeholders = ",".join("?" for _ in ids)
        conn.execute(
            f"update jobs set status='shortlisted', updated_at=? where id in ({placeholders})",
            [now_iso()] + ids,
        )
        conn.commit()
    return {"count": len(ids), "ids": ids}


def next_fresh_job_ids(conn: sqlite3.Connection, limit: int = 1) -> list[int]:
    rows = conn.execute(
        """
        select jobs.id, jobs.company, jobs.title, jobs.score
        from jobs
        left join applications on applications.job_id = jobs.id
        where jobs.status in ('new', 'drafted', 'shortlisted')
          and applications.id is null
          and coalesce(jobs.too_senior, 0) = 0
          and jobs.score >= 35
          and lower(jobs.concerns) not like '%role-title mismatch%'
          and lower(jobs.concerns) not like '%potential scam%'
          and lower(jobs.concerns) not like '%below the r22,000/month target%'
          and lower(jobs.concerns) not like '%outside south africa/uk/remote target%'
          and lower(jobs.concerns) not like '%outside cape town%'
          and lower(jobs.concerns) not like '%not clearly cape town or remote%'
          and lower(jobs.concerns) not like '%cape town/remote preference%'
          and lower(jobs.concerns) not like '%cape town/remote target%'
          and lower(jobs.concerns) not like '%physical location is not cape town%'
          and lower(jobs.concerns) not like '%listed physical location is not cape town%'
          and lower(jobs.concerns) not like '%remote role appears based%'
          and lower(jobs.concerns) not like '%remote role is tied to a specific city/country%'
          and lower(jobs.concerns) not like '%remote role appears restricted%'
          and lower(jobs.concerns) not like '%remote role text suggests geographic restrictions%'
          and lower(jobs.concerns) not like '%marked this role as too senior%'
          and lower(jobs.concerns) not like '%not an early-career role%'
          and lower(jobs.concerns) not like '%would require relocation%'
          and lower(jobs.concerns) not like '%local/eu work authorization%'
          and lower(jobs.concerns) not like '%us non-remote%'
          and lower(jobs.concerns) not like '%hybrid role may require%'
        order by
          (jobs.score
            + case when lower(jobs.location) like '%cape town%' or lower(jobs.location) like '%western cape%' then 6 else 0 end
            - case when lower(jobs.concerns) like '%manager title may be above graduate/junior level%' then 4 else 0 end
            - case when lower(jobs.concerns) like '%not an early-career role%' then 18 else 0 end
            - case when lower(jobs.concerns) like '%possible seniority mismatch%' then 8 else 0 end
          ) desc,
          case when lower(jobs.location) like '%cape town%' or lower(jobs.location) like '%western cape%' then 1 else 0 end desc,
          case when lower(jobs.location) like '%remote%' then 1 else 0 end desc,
          jobs.score desc,
          jobs.updated_at desc
        limit ?
        """,
        (max(limit * 5, limit),),
    ).fetchall()
    ids: list[int] = []
    seen_roles: set[tuple[str, str]] = set()
    for row in rows:
        key = (
            re.sub(r"\W+", " ", str(row["company"] or "").lower()).strip(),
            re.sub(r"\W+", " ", str(row["title"] or "").lower()).strip(),
        )
        if key in seen_roles:
            continue
        seen_roles.add(key)
        ids.append(int(row["id"]))
        if len(ids) >= limit:
            break
    return ids


def rescore_all_jobs(conn: sqlite3.Connection) -> dict[str, Any]:
    rows = conn.execute("select * from jobs").fetchall()
    timestamp = now_iso()
    for row in rows:
        job = row_to_dict(row) or {}
        score, reasons, concerns = score_job(job)
        conn.execute(
            "update jobs set score=?, score_reasons=?, concerns=?, updated_at=? where id=?",
            (score, reasons, concerns, timestamp, int(job["id"])),
        )
    conn.commit()
    return {"count": len(rows)}


def generate_drafts_for_jobs(conn: sqlite3.Connection, status: str = "shortlisted", limit: int = 5, batch_id: str = "") -> dict[str, Any]:
    rows = conn.execute(
        """
        select jobs.id
        from jobs
        left join applications on applications.job_id = jobs.id
        where jobs.status = ?
          and applications.id is null
        order by jobs.score desc, jobs.updated_at desc
        limit ?
        """,
        (status, limit),
    ).fetchall()
    ids: list[int] = []
    app_ids: list[int] = []
    for row in rows:
        job_id = int(row["id"])
        app_id = generate_application(conn, job_id, batch_id=batch_id)
        ids.append(job_id)
        app_ids.append(app_id)
    return {"count": len(ids), "job_ids": ids, "application_ids": app_ids}


def run_daily_workflow(limit: int = 5) -> dict[str, Any]:
    discovery = run_enabled_sources(force=True)
    with connect() as conn:
        rescored = rescore_all_jobs(conn)
        shortlisted = shortlist_top_jobs(conn, limit)
        drafts = generate_drafts_for_jobs(conn, "shortlisted", limit)
        assessed = assess_application_queue(conn)
    return {
        "discovery": discovery,
        "rescored": rescored,
        "shortlisted": shortlisted,
        "drafts": drafts,
        "assessed": assessed,
    }


def refresh_application_queue(limit: int = 5) -> dict[str, Any]:
    batch_id = now_iso()
    with connect() as conn:
        rescored = rescore_all_jobs(conn)
        shortlisted = shortlist_fresh_jobs(conn, limit)
        drafts = generate_drafts_for_jobs(conn, "shortlisted", limit, batch_id=batch_id)
        assessed = assess_application_queue(conn)
    return {
        "batch_id": batch_id,
        "rescored": rescored,
        "shortlisted": shortlisted,
        "drafts": drafts,
        "assessed": assessed,
    }


def set_application_queue_state(application_id: int, queue_state: str) -> dict[str, Any]:
    allowed = {"review", "approved", "hold"}
    normalized = normalize_space(queue_state).lower() or "review"
    if normalized not in allowed:
        raise RuntimeError("Invalid queue state.")
    with connect() as conn:
        row = conn.execute("select id from applications where id=?", (application_id,)).fetchone()
        if not row:
            raise RuntimeError("Application not found")
        conn.execute(
            "update applications set queue_state=?, updated_at=? where id=?",
            (normalized, now_iso(), application_id),
        )
        conn.commit()
    return {"id": application_id, "queue_state": normalized}


def stale_application_reason(job: dict[str, Any]) -> str:
    concerns = str(job.get("concerns", "")).lower()
    title = str(job.get("title", "")).lower()
    if "not an early-career role" in concerns or "possible seniority mismatch" in concerns or any(term in title for term in ["director", "vice president", "vp ", "head of", "manager"]):
        return "too senior"
    if "role-title mismatch" in concerns:
        return "not really marketing"
    if "outside cape town" in concerns or "physical location is not cape town" in concerns or "us non-remote" in concerns or "would require relocation" in concerns:
        return "wrong location"
    if "remote role appears restricted" in concerns or "remote role text suggests geographic restrictions" in concerns:
        return "remote eligibility unclear"
    return "poor fit"


def cleanup_stale_applications() -> dict[str, Any]:
    with connect() as conn:
        rows = conn.execute(
            """
            select applications.id as application_id, applications.status, applications.queue_state,
                   jobs.id as job_id, jobs.title, jobs.company, jobs.score, jobs.concerns, jobs.description
            from applications
            join jobs on jobs.id = applications.job_id
            where applications.status in ('draft', 'ready')
            """
        ).fetchall()
        cleaned: list[dict[str, Any]] = []
        timestamp = now_iso()
        for row in rows:
            item = row_to_dict(row) or {}
            concerns = str(item.get("concerns", "")).lower()
            score = int(item.get("score") or 0)
            keep_role = should_keep_discovered_role(
                str(item.get("title", "")),
                str(item.get("company", "")),
                str(item.get("description", "")),
                GRADUATE_MARKETING_DISCOVERY_QUERY,
                str(item.get("location", "")),
            )
            if (
                score < 35
                or "not an early-career role" in concerns
                or "possible seniority mismatch" in concerns
                or "role-title mismatch" in concerns
                or "outside cape town" in concerns
                or "physical location is not cape town" in concerns
                or "us non-remote" in concerns
                or "would require relocation" in concerns
                or not keep_role
            ):
                reason = "not really marketing" if not keep_role else stale_application_reason(item)
                too_senior = 1 if reason == "too senior" else int("too_senior" in concerns)
                conn.execute(
                    "update applications set status='rejected', reject_reason=?, updated_at=? where id=?",
                    (reason, timestamp, int(item["application_id"])),
                )
                conn.execute(
                    "update jobs set status='rejected', reject_reason=?, too_senior=?, updated_at=? where id=?",
                    (reason, too_senior, timestamp, int(item["job_id"])),
                )
                cleaned.append(
                    {
                        "application_id": int(item["application_id"]),
                        "job_id": int(item["job_id"]),
                        "company": str(item.get("company", "")),
                        "title": str(item.get("title", "")),
                        "reason": reason,
                    }
                )
        conn.commit()
    return {"count": len(cleaned), "items": cleaned}


def reject_application_and_replace(application_id: int, reason: str = "", notes: str = "") -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute(
            """
            select applications.*, jobs.id as job_id_value, jobs.company, jobs.title, jobs.too_senior as job_too_senior
            from applications
            join jobs on jobs.id = applications.job_id
            where applications.id=?
            """,
            (application_id,),
        ).fetchone()
        if not row:
            raise RuntimeError("Application not found")
        app = row_to_dict(row) or {}
        batch_id = str(app.get("batch_id", "") or now_iso())
        timestamp = now_iso()
        normalized_reason = normalize_space(reason).lower()
        normalized_notes = normalize_space(notes)
        too_senior = 1 if "senior" in normalized_reason or "manager" in normalized_reason else int(app.get("job_too_senior") or 0)
        conn.execute(
            "update applications set status='rejected', reject_reason=?, reject_notes=?, updated_at=? where id=?",
            (normalized_reason, normalized_notes, timestamp, application_id),
        )
        conn.execute(
            "update jobs set status='rejected', reject_reason=?, too_senior=?, updated_at=? where id=?",
            (normalized_reason, too_senior, timestamp, int(app.get("job_id_value") or app.get("job_id") or 0)),
        )
        replacement_ids = next_fresh_job_ids(conn, 1)
        replacement_app_ids: list[int] = []
        if replacement_ids:
            placeholders = ",".join("?" for _ in replacement_ids)
            conn.execute(
                f"update jobs set status='shortlisted', updated_at=? where id in ({placeholders})",
                [timestamp] + replacement_ids,
            )
            for job_id in replacement_ids:
                replacement_app_ids.append(generate_application(conn, int(job_id), batch_id=batch_id))
        assessed = assess_application_queue(conn)
    return {
        "rejected_id": application_id,
        "reason": normalized_reason,
        "replacement_job_ids": replacement_ids,
        "replacement_application_ids": replacement_app_ids,
        "assessed": assessed,
    }


def run_automatic_mode(limit: int = 5) -> dict[str, Any]:
    summary: dict[str, Any] = {"started_at": now_iso(), "safe_stop": "No final submissions or emails are sent automatically."}
    with connect() as conn:
        summary["seeded_targets"] = seed_starter_targets(conn)
        summary["target_sources"] = convert_ready_targets_to_sources(conn)
    summary["discovery"] = run_enabled_sources(force=True)
    with connect() as conn:
        summary["rescored"] = rescore_all_jobs(conn)
        summary["shortlisted"] = shortlist_top_jobs(conn, limit)
        summary["drafts"] = generate_drafts_for_jobs(conn, "shortlisted", limit)
        summary["researched"] = research_application_queue(conn, limit=limit)
        summary["humanized"] = humanize_application_queue(conn, limit=limit)
        summary["assessed"] = assess_application_queue(conn)
        weekly_report = build_weekly_report(conn)
        reminders = export_reminders_calendar(conn)
        summary["notifications"] = notify_due_reminders(conn)
        checklist_path = write_project_checklists()
        run_id = log_automation_run(conn, "auto-mode", summary, weekly_report)
    summary["weekly_report"] = str(weekly_report)
    summary["reminders"] = reminders
    summary["checklist"] = str(checklist_path)
    summary["run_id"] = run_id
    if inbox_config_status().get("password_set"):
        summary["inbox_scan"] = scan_inbox_for_replies(limit=80)
    return summary


def convert_ready_targets_to_sources(conn: sqlite3.Connection) -> dict[str, Any]:
    rows = conn.execute(
        """
        select * from target_companies
        where coalesce(source_id, 0)=0
          and status != 'paused'
          and source_type != ''
          and source_token != ''
        order by priority desc, updated_at desc
        limit 20
        """
    ).fetchall()
    converted: list[int] = []
    errors: list[str] = []
    for row in rows:
        target = row_to_dict(row) or {}
        try:
            result = target_company_to_source(conn, int(target["id"]))
            converted.append(int(result["source_id"]))
        except Exception as exc:
            errors.append(f"{target.get('company')}: {exc}")
    return {"count": len(converted), "source_ids": converted, "errors": errors}


def research_application_queue(conn: sqlite3.Connection, limit: int = 10) -> dict[str, Any]:
    rows = conn.execute(
        """
        select applications.*, jobs.company, jobs.title, jobs.description, jobs.url, jobs.source
        from applications
        join jobs on jobs.id = applications.job_id
        where applications.status in ('draft', 'ready')
          and applications.research_notes = ''
        order by applications.updated_at desc
        limit ?
        """,
        (limit,),
    ).fetchall()
    count = 0
    for row in rows:
        app = row_to_dict(row) or {}
        job = row_to_dict(conn.execute("select * from jobs where id=?", (app["job_id"],)).fetchone()) or {}
        notes, sources, saved_url = generate_application_research(job, app, app.get("research_url", ""))
        conn.execute(
            """
            update applications
            set research_notes=?, research_sources=?, research_url=?, updated_at=?
            where id=?
            """,
            (notes, sources, saved_url, now_iso(), int(app["id"])),
        )
        refreshed = row_to_dict(conn.execute("select * from applications where id=?", (int(app["id"]),)).fetchone()) or {}
        write_application_documents(job, refreshed)
        count += 1
    conn.commit()
    return {"count": count}


def humanize_application_queue(conn: sqlite3.Connection, limit: int = 10) -> dict[str, Any]:
    rows = conn.execute(
        """
        select * from applications
        where status in ('draft', 'ready')
        order by updated_at desc
        limit ?
        """,
        (limit,),
    ).fetchall()
    count = 0
    for row in rows:
        app = row_to_dict(row) or {}
        cover = phillip_voice_text(str(app.get("cover_letter", "")), "cover_letter")
        answers = phillip_voice_text(str(app.get("answers", "")), "answers")
        follow_up = phillip_voice_text(str(app.get("follow_up", "")), "follow_up")
        conn.execute(
            """
            update applications set cover_letter=?, answers=?, follow_up=?, updated_at=?
            where id=?
            """,
            (cover, answers, follow_up, now_iso(), int(app["id"])),
        )
        job = row_to_dict(conn.execute("select * from jobs where id=?", (app["job_id"],)).fetchone()) or {}
        refreshed = row_to_dict(conn.execute("select * from applications where id=?", (int(app["id"]),)).fetchone()) or {}
        write_application_documents(job, refreshed)
        count += 1
    conn.commit()
    return {"count": count}


def assess_application_queue(conn: sqlite3.Connection) -> dict[str, Any]:
    rows = conn.execute(
        """
        select applications.*, jobs.score, jobs.concerns, jobs.description, jobs.source, jobs.location, jobs.company, jobs.title
        from applications
        join jobs on jobs.id = applications.job_id
        where applications.status in ('draft', 'ready', 'submitted')
        """
    ).fetchall()
    for row in rows:
        app = row_to_dict(row) or {}
        job = row_to_dict(conn.execute("select * from jobs where id=?", (app["job_id"],)).fetchone()) or {}
        assessment = assess_application(job, app, get_profile(conn))
        conn.execute(
            """
            update applications
            set quality_score=?, quality_notes=?, checklist=?, truthfulness_flags=?,
                recommended_cv_version=?, updated_at=?
            where id=?
            """,
            (
                assessment["quality_score"],
                assessment["quality_notes"],
                assessment["checklist"],
                assessment["truthfulness_flags"],
                assessment["recommended_cv_version"],
                now_iso(),
                int(app["id"]),
            ),
        )
    conn.commit()
    return {"count": len(rows)}


def assess_application(job: dict[str, Any], app: dict[str, Any], profile: dict[str, str]) -> dict[str, Any]:
    score = 100
    notes: list[str] = []
    checklist: list[str] = []
    flags = truthfulness_flags(job, app, profile)

    required = [
        ("cover letter", app.get("cover_letter")),
        ("questionnaire answers", app.get("answers")),
        ("follow-up email", app.get("follow_up")),
        ("company research", app.get("research_notes")),
        ("job URL", job.get("url")),
    ]
    for label, value in required:
        if value:
            checklist.append(f"[x] {label}")
        else:
            checklist.append(f"[ ] {label}")
            score -= 10
            notes.append(f"Missing {label}.")

    optional = [
        ("personalization notes", app.get("company_notes")),
        ("contact email", app.get("contact_email")),
        ("contact name", app.get("contact_name")),
    ]
    for label, value in optional:
        checklist.append(f"[{'x' if value else ' '}] {label} if available")
        if not value:
            score -= 3

    concerns = str(job.get("concerns", ""))
    if concerns:
        score -= min(30, len([line for line in concerns.splitlines() if line.strip()]) * 8)
        notes.append("Review fit concerns before applying.")
        checklist.append("[ ] fit concerns reviewed")
    else:
        checklist.append("[x] fit concerns reviewed")

    if flags:
        score -= min(35, len(flags) * 10)
        notes.append("Truthfulness/work-authorization flags need review.")
        checklist.append("[ ] truthfulness/work authorization reviewed")
    else:
        checklist.append("[x] truthfulness/work authorization reviewed")

    if voice_check(str(app.get("cover_letter", ""))).get("status") != "natural enough":
        score -= 5
        notes.append("Cover letter may still sound generic.")
    if voice_check(str(app.get("follow_up", ""))).get("status") != "natural enough":
        score -= 5
        notes.append("Follow-up may still sound generic.")

    checklist.extend(
        [
            "[ ] CV uploaded during form fill",
            "[ ] salary answer checked",
            "[ ] start date checked",
            "[ ] demographic answers reviewed",
            "[ ] final submit clicked manually by Phillip",
        ]
    )
    return {
        "quality_score": max(0, min(100, score)),
        "quality_notes": "\n".join(notes) or "Ready for manual review.",
        "checklist": "\n".join(checklist),
        "truthfulness_flags": "\n".join(flags),
        "recommended_cv_version": recommend_cv_version(conn=None, job=job),
    }


def truthfulness_flags(job: dict[str, Any], app: dict[str, Any], profile: dict[str, str]) -> list[str]:
    text = "\n".join(str(app.get(field, "")) for field in ["cover_letter", "answers", "follow_up"])
    lower = text.lower()
    flags = []
    if re.search(r"\b[4-9]\+?\s+years|\b1[0-9]\+?\s+years", lower):
        flags.append("Check years-of-experience claim; Phillip is early-career.")
    if "expert" in lower or "extensive experience" in lower:
        flags.append("Avoid expert/extensive-experience wording unless specifically true.")
    if "managed large budgets" in lower or "$30k" in lower or "30k+" in lower:
        flags.append("Check paid-media budget claims; do not imply ownership of large budgets unless true.")
    if "authorized to work in the united states" in lower or "us citizen" in lower:
        flags.append("Do not claim US work authorization.")
    if "eu citizen" in lower:
        flags.append("Do not claim EU citizenship unless confirmed.")
    if "immediately available" in lower and "2027" not in lower:
        flags.append("Start-date wording may conflict with full-time availability from 2027-01-01.")
    if "relocate" in lower and "case by case" not in lower:
        flags.append("Relocation should be case-by-case, not unconditional.")
    return flags


def recommend_cv_version(conn: sqlite3.Connection | None, job: dict[str, Any]) -> str:
    text = f"{job.get('title', '')} {job.get('company', '')} {job.get('description', '')}".lower()
    if any(term in text for term in ["fitness", "sport", "athlete", "running", "cycling", "outdoor", "wellness"]):
        return "Sports and fitness marketing CV"
    if any(term in text for term in ["content", "social", "tiktok", "instagram", "creative", "copy"]):
        return "Content and social media CV"
    if any(term in text for term in ["analytics", "research", "insight", "survey", "data"]):
        return "Research and analytics CV"
    if any(term in text for term in ["startup", "growth", "product", "ai", "automation", "app"]):
        return "Startup and growth CV"
    return "General marketing CV"


def build_weekly_report(conn: sqlite3.Connection) -> Path:
    jobs = [row_to_dict(row) for row in conn.execute("select * from jobs").fetchall()]
    apps = [
        row_to_dict(row)
        for row in conn.execute(
            """
            select applications.*, jobs.title, jobs.company, jobs.source, jobs.score
            from applications join jobs on jobs.id = applications.job_id
            """
        ).fetchall()
    ]
    sources = [row_to_dict(row) for row in conn.execute("select * from job_sources").fetchall()]
    submitted = [app for app in apps if app.get("status") in {"submitted", "interview", "offer"}]
    responses = [app for app in apps if app.get("status") in {"interview", "offer"}]
    source_counts: dict[str, int] = {}
    for job in jobs:
        source_counts[str(job.get("source", "unknown"))] = source_counts.get(str(job.get("source", "unknown")), 0) + 1
    top_sources = sorted(source_counts.items(), key=lambda item: item[1], reverse=True)[:8]
    top_source_lines = [f"- {source}: {count}" for source, count in top_sources] or ["- No source data yet."]
    report_lines = [
        "# Weekly Job Search Report",
        "",
        f"Generated: {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## Snapshot",
        "",
        f"- Jobs tracked: {len(jobs)}",
        f"- Applications/drafts tracked: {len(apps)}",
        f"- Submitted/interview/offer: {len(submitted)}",
        f"- Responses/interviews/offers: {len(responses)}",
        f"- Response rate: {round((len(responses) / max(1, len(submitted))) * 100)}%",
        f"- Sources configured: {len(sources)}",
        "",
        "## Top Sources By Jobs",
        "",
        *top_source_lines,
        "",
        "## Next Recommendations",
        "",
        "- Review the Daily Review cards and only submit applications with strong quality scores.",
        "- Add contact/person/company notes before sending follow-ups or outreach.",
        "- Convert priority target companies into sources where the careers URL is valid.",
        "- Keep final submit and final email send manual.",
    ]
    report = "\n".join(report_lines)
    path = DOCS_DIR / "weekly-job-search-report.md"
    path.write_text(report + "\n", encoding="utf-8")
    return path


def pending_reminder_events(conn: sqlite3.Connection) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    apps = conn.execute(
        """
        select applications.*, jobs.title, jobs.company, jobs.url
        from applications
        join jobs on jobs.id = applications.job_id
        where applications.next_follow_up != ''
          and applications.follow_up_sent_at = ''
          and applications.status in ('submitted', 'interview', 'offer')
        """
    ).fetchall()
    for row in apps:
        app = row_to_dict(row) or {}
        events.append(
            {
                "id": f"application:{app.get('id')}:{app.get('next_follow_up')}",
                "type": "application",
                "date": str(app.get("next_follow_up", "")),
                "summary": f"Follow up: {app.get('company')} - {app.get('title')}",
                "description": f"Review and send follow-up email for {app.get('title')} at {app.get('company')}. {app.get('url') or ''}",
            }
        )
    leads = conn.execute(
        """
        select * from company_leads
        where next_follow_up != ''
          and status = 'sent'
          and do_not_contact = 0
        """
    ).fetchall()
    for row in leads:
        lead = row_to_dict(row) or {}
        events.append(
            {
                "id": f"outreach:{lead.get('id')}:{lead.get('next_follow_up')}",
                "type": "outreach",
                "date": str(lead.get("next_follow_up", "")),
                "summary": f"Outreach follow-up: {lead.get('company')}",
                "description": f"Review outreach follow-up for {lead.get('company')}. Contact: {lead.get('contact_email') or 'not saved'}",
            }
        )
    return events


def export_reminders_calendar(conn: sqlite3.Connection) -> dict[str, Any]:
    events = pending_reminder_events(conn)
    path = REMINDERS_DIR / "job-application-reminders.ics"
    path.write_text(render_ics(events), encoding="utf-8")
    summary_path = REMINDERS_DIR / "job-application-reminders.md"
    summary_path.write_text(render_reminder_summary(events), encoding="utf-8")
    return {"count": len(events), "ics_path": str(path), "summary_path": str(summary_path)}


def render_ics(events: list[dict[str, str]]) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Job Application AI//Reminders//EN",
        "CALSCALE:GREGORIAN",
    ]
    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")
    for index, event in enumerate(events, start=1):
        date_text = re.sub(r"[^0-9-]", "", event.get("date", ""))[:10]
        try:
            start = dt.date.fromisoformat(date_text)
        except ValueError:
            continue
        end = start + dt.timedelta(days=1)
        uid = f"job-ai-{date_text}-{index}@local"
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{stamp}",
                f"DTSTART;VALUE=DATE:{start.strftime('%Y%m%d')}",
                f"DTEND;VALUE=DATE:{end.strftime('%Y%m%d')}",
                f"SUMMARY:{ics_escape(event.get('summary', 'Job application reminder'))}",
                f"DESCRIPTION:{ics_escape(event.get('description', ''))}",
                "BEGIN:VALARM",
                "TRIGGER:-PT9H",
                "ACTION:DISPLAY",
                f"DESCRIPTION:{ics_escape(event.get('summary', 'Job application reminder'))}",
                "END:VALARM",
                "END:VEVENT",
            ]
        )
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def ics_escape(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def render_reminder_summary(events: list[dict[str, str]]) -> str:
    if not events:
        return "# Job Application Reminders\n\nNo pending reminders.\n"
    lines = ["# Job Application Reminders", ""]
    for event in sorted(events, key=lambda item: item.get("date", "")):
        lines.append(f"- {event.get('date')}: {event.get('summary')}")
    return "\n".join(lines) + "\n"


def notify_due_reminders(conn: sqlite3.Connection) -> dict[str, Any]:
    today = dt.date.today()
    due_events = []
    for event in pending_reminder_events(conn):
        date_text = re.sub(r"[^0-9-]", "", event.get("date", ""))[:10]
        try:
            event_date = dt.date.fromisoformat(date_text)
        except ValueError:
            continue
        if event_date <= today:
            due_events.append(event)

    notified = read_notified_reminders()
    sent: list[str] = []
    errors: list[str] = []
    for event in due_events[:5]:
        key = f"{event.get('id')}:notified:{today.isoformat()}"
        if notified.get(key):
            continue
        try:
            send_macos_notification(
                "Job Application Follow-up",
                f"{event.get('summary', 'Follow-up due')} is due. Open Job Application AI to review and send.",
            )
            notified[key] = now_iso()
            sent.append(str(event.get("summary", "Follow-up due")))
        except Exception as exc:
            errors.append(str(exc))
    if sent:
        NOTIFIED_REMINDERS_PATH.write_text(json.dumps(notified, indent=2, ensure_ascii=True), encoding="utf-8")
    return {"due": len(due_events), "sent": len(sent), "sent_summaries": sent, "errors": errors}


def read_notified_reminders() -> dict[str, str]:
    try:
        return json.loads(NOTIFIED_REMINDERS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def send_macos_notification(title: str, message: str) -> None:
    script = (
        "display notification "
        f"{applescript_string(message[:220])} "
        "with title "
        f"{applescript_string(title[:80])}"
    )
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=8)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "macOS notification failed").strip())


def applescript_string(value: str) -> str:
    cleaned = normalize_space(str(value)).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{cleaned}"'


def write_project_checklists() -> Path:
    content = textwrap.dedent(
        """
        # Automation Checklists

        ## Phillip Checklist

        - [x] Add a real writing sample in Profile.
        - [ ] Review the 20 starter target companies and pause/remove any that do not fit.
        - [ ] Convert the best target companies into sources.
        - [x] Run automatic mode.
        - [ ] Review Daily Review cards from top to bottom.
        - [ ] Check work authorization, salary, start date, and CV version before each submit.
        - [ ] Review the tailored CV brief in each generated application pack before attaching a CV.
        - [ ] Use Prepare form, inspect every field, then manually click final submit.
        - [ ] Mark submitted after applying so follow-ups are scheduled.
        - [ ] Export or refresh the reminder calendar after marking applications submitted.
        - [ ] Scan inbox replies after sending applications or outreach.
        - [ ] Send follow-up emails only after reviewing the final text.

        ## Codex Checklist

        - [x] Improve company research extraction from about/careers/product pages.
        - [x] Improve Workable and Teamtailor support where public access allows it.
        - [x] Add tailored CV brief exports to generated application packs.
        - [x] Add browser fill feedback capture after Prepare form.
        - [x] Add reminder calendar export.
        - [x] Add native local notification support.
        - [x] Add inbox/reply tracking if Phillip approves a safe email integration.
        - [x] Improve Workable and Teamtailor public discovery support.
        - [x] Tune Phillip voice using real writing sample.
        - [x] Keep final submission and email send review-first.
        """
    ).strip()
    path = ROOT / "AUTOMATION_CHECKLIST.md"
    path.write_text(content + "\n", encoding="utf-8")
    return path


def log_automation_run(conn: sqlite3.Connection, kind: str, summary: dict[str, Any], report_path: Path) -> int:
    human_summary = (
        f"Automatic mode completed: {summary.get('discovery', {}).get('imported', 0)} jobs imported, "
        f"{summary.get('drafts', {}).get('count', 0)} drafts generated, "
        f"{summary.get('researched', {}).get('count', 0)} researched, "
        f"{summary.get('assessed', {}).get('count', 0)} assessed. Report: {report_path}"
    )
    cur = conn.execute(
        "insert into automation_runs(kind, summary, details, created_at) values(?, ?, ?, ?)",
        (kind, human_summary, json.dumps(summary, ensure_ascii=True, default=str), now_iso()),
    )
    conn.commit()
    return int(cur.lastrowid)


def save_form_fill_feedback(conn: sqlite3.Connection, data: dict[str, Any]) -> int:
    app_id = int(data.get("application_id") or data.get("id") or 0)
    if not app_id:
        raise RuntimeError("Application id is required.")
    existing = conn.execute("select id from applications where id=?", (app_id,)).fetchone()
    if not existing:
        raise RuntimeError("Application not found.")
    cur = conn.execute(
        """
        insert into form_fill_feedback(application_id, worked, missed, wrong, notes, created_at)
        values(?, ?, ?, ?, ?, ?)
        """,
        (
            app_id,
            normalize_space(str(data.get("worked", ""))),
            normalize_space(str(data.get("missed", ""))),
            normalize_space(str(data.get("wrong", ""))),
            normalize_space(str(data.get("notes", ""))),
            now_iso(),
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def feedback_recommendations(feedback_rows: list[dict[str, Any]]) -> list[str]:
    text = "\n".join(
        f"{row.get('missed', '')}\n{row.get('wrong', '')}\n{row.get('notes', '')}"
        for row in feedback_rows
    ).lower()
    recs: list[str] = []
    checks = [
        ("work authorization", "Add clearer mapping for work authorization fields."),
        ("visa", "Add safer visa/sponsorship field handling."),
        ("salary", "Improve salary expectation field detection."),
        ("linkedin", "Improve LinkedIn/profile URL selectors."),
        ("resume", "Improve CV upload detection."),
        ("cv", "Improve CV upload detection."),
        ("cover", "Improve cover letter textarea detection."),
        ("location", "Improve location/country field handling."),
        ("phone", "Improve phone field handling."),
    ]
    for token, rec in checks:
        if token in text and rec not in recs:
            recs.append(rec)
    if not recs and feedback_rows:
        recs.append("Review latest feedback manually and add selectors for repeated misses.")
    return recs[:8]


def _source_key_for_record(source: dict[str, Any]) -> str:
    source_type = str(source.get("source_type", "")).lower()
    token = str(source.get("token", ""))
    if source_type in {"careers", "url"}:
        return f"careers:{company_from_url(token)}"
    return f"{source_type}:{token.lower()}"


def source_cleanup_recommendations(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rejection_stats: dict[str, dict[str, int]] = {}
    for row in conn.execute(
        """
        select source,
          count(*) as total,
          sum(case when reject_reason != '' then 1 else 0 end) as rejected,
          sum(case when reject_reason = 'not really marketing' then 1 else 0 end) as not_marketing,
          sum(case when reject_reason = 'wrong location' then 1 else 0 end) as wrong_location
        from jobs
        where source != '' and source != 'manual'
        group by source
        """
    ).fetchall():
        rejection_stats[str(row["source"])] = {
            "total": int(row["total"] or 0),
            "rejected": int(row["rejected"] or 0),
            "not_marketing": int(row["not_marketing"] or 0),
            "wrong_location": int(row["wrong_location"] or 0),
        }
    rows = conn.execute("select * from job_sources order by enabled desc, updated_at desc").fetchall()
    recs: list[dict[str, Any]] = []
    for row in rows:
        source = row_to_dict(row) or {}
        last_result = str(source.get("last_result", ""))
        reason = ""
        action = ""
        if '"error"' in last_result.lower() or "http error" in last_result.lower():
            reason = f"Last run failed: {last_result[:220]}"
            action = "pause-or-fix"
        elif last_result:
            try:
                payload = json.loads(last_result)
                if source.get("source_type") == "url" and payload.get("mode") == "no-visible-jobs":
                    reason = "Public careers page produced no visible job links; low-yield source."
                    action = "pause-low-yield"
                elif int(payload.get("count", 0)) == 0:
                    reason = "Last run imported 0 jobs."
                    action = "review-query"
            except Exception:
                pass
        if not reason:
            key = _source_key_for_record(source)
            stats = rejection_stats.get(key) or {}
            total = stats.get("total", 0)
            rejected = stats.get("rejected", 0)
            not_marketing = stats.get("not_marketing", 0)
            wrong_location = stats.get("wrong_location", 0)
            if total >= 5 and rejected > 0:
                rate = int(rejected * 100 / total)
                if not_marketing >= 3 and rate >= 60:
                    reason = (
                        f"High rejection rate ({rate}% of {total} jobs): "
                        f"{not_marketing} rejected as 'not really marketing'. "
                        "Tighten the source query or pause this source."
                    )
                    action = "review-query"
                elif wrong_location >= 2 and rate >= 60:
                    reason = (
                        f"High rejection rate ({rate}% of {total} jobs): "
                        f"{wrong_location} rejected as 'wrong location'. "
                        "This source may not produce Cape Town/remote-eligible roles."
                    )
                    action = "review-query"
        if reason:
            recs.append(
                {
                    "id": source.get("id"),
                    "name": source.get("name"),
                    "source_type": source.get("source_type"),
                    "token": source.get("token"),
                    "enabled": source.get("enabled"),
                    "reason": reason,
                    "action": action,
                }
            )
    return recs[:20]


def pause_failing_sources(conn: sqlite3.Connection) -> dict[str, Any]:
    recs = source_cleanup_recommendations(conn)
    ids = [
        int(rec["id"])
        for rec in recs
        if rec.get("action") in {"pause-or-fix", "pause-low-yield"} and rec.get("enabled")
    ]
    if ids:
        placeholders = ",".join("?" for _ in ids)
        conn.execute(
            f"update job_sources set enabled=0, updated_at=? where id in ({placeholders})",
            [now_iso()] + ids,
        )
        conn.commit()
    return {"count": len(ids), "ids": ids}


def seed_starter_sources(conn: sqlite3.Connection) -> dict[str, Any]:
    ids: list[int] = []
    for source in STARTER_JOB_SOURCES:
        payload = dict(source)
        payload["enabled"] = True
        ids.append(save_job_source(conn, payload))
    return {"count": len(ids), "ids": ids}


def import_job_alert_text(conn: sqlite3.Connection, text: str, source: str = "email-alert") -> dict[str, Any]:
    cleaned = text.strip()
    if not cleaned:
        raise RuntimeError("Paste a job alert email or saved-search text first.")
    urls = []
    for match in re.finditer(r"https?://[^\s<>\"]+", cleaned):
        url = match.group(0).rstrip(").,;]'\"")
        if should_skip_alert_url(url):
            continue
        if url not in urls:
            urls.append(url)
    if not urls:
        raise RuntimeError("No usable job URLs were found in that alert text.")

    lines = [normalize_space(line) for line in cleaned.splitlines()]
    ids: list[int] = []
    for url in urls[:40]:
        title, company, location = guess_alert_job_fields(url, lines)
        context = alert_context_for_url(url, cleaned)
        ids.append(
            upsert_job(
                conn,
                {
                    "title": title,
                    "company": company,
                    "location": location,
                    "url": url,
                    "source": source or "email-alert",
                    "description": context or cleaned[:6000],
                    "raw_json": {"imported_from": "job_alert_text"},
                },
            )
        )
    return {"count": len(ids), "ids": ids, "urls": urls[:40], "skipped": max(0, len(urls) - 40)}


def should_skip_alert_url(url: str) -> bool:
    lower = url.lower()
    skip_terms = [
        "unsubscribe",
        "privacy",
        "terms",
        "preferences",
        "settings",
        "help",
        "support",
        "utm_medium=email_footer",
        "mailto:",
    ]
    if any(term in lower for term in skip_terms):
        return True
    return not any(term in lower for term in ["jobs", "careers", "greenhouse", "lever", "ashby", "workable", "linkedin", "indeed", "smartrecruiters", "recruitee"])


def guess_alert_job_fields(url: str, lines: list[str]) -> tuple[str, str, str]:
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    company = company_from_url(host)
    title = ""
    location = ""
    for index, line in enumerate(lines):
        if url in line:
            candidates = []
            for offset in range(-3, 4):
                pos = index + offset
                if 0 <= pos < len(lines):
                    candidate = lines[pos]
                    if candidate and "http" not in candidate.lower() and len(candidate) < 140:
                        candidates.append(candidate)
            for candidate in candidates:
                lower = candidate.lower()
                if not title and any(term in lower for term in MARKETING_TITLE_SIGNALS + ENTRY_LEVEL_SIGNALS):
                    title = candidate
                elif not location and any(term in lower for term in LOCATION_KEYWORDS):
                    location = candidate
                elif not title and len(candidate.split()) <= 9:
                    title = candidate
            break
    if not title:
        slug = Path(parsed.path.rstrip("/")).name.replace("-", " ").replace("_", " ")
        title = normalize_space(slug).title() if slug else "Job alert role"
    if "linkedin." in host:
        company = "LinkedIn alert"
    elif "indeed." in host:
        company = "Indeed alert"
    return title[:180], company[:120], location[:120]


def alert_context_for_url(url: str, text: str) -> str:
    index = text.find(url)
    if index < 0:
        return text[:6000]
    start = max(0, index - 1200)
    end = min(len(text), index + len(url) + 1200)
    return text[start:end].strip()


def discovery_scheduler() -> None:
    # Local-only scheduler: it runs while this app process is open.
    time.sleep(15)
    while True:
        try:
            with connect() as conn:
                notify_due_reminders(conn)
            run_enabled_sources(force=False)
        except Exception as exc:
            print(f"[scheduler] task failed: {exc}")
        time.sleep(DISCOVERY_CHECK_SECONDS)


def add_job_from_url(conn: sqlite3.Connection, url: str) -> int:
    status, body, content_type = fetch_url(url)
    if status >= 400:
        raise RuntimeError(f"URL returned HTTP {status}")
    if "json" in content_type:
        payload = json.loads(body)
        text = json.dumps(payload, indent=2)
        title = payload.get("title") or payload.get("text") or "Imported JSON job"
        company = payload.get("company") or payload.get("organization") or urllib.parse.urlparse(url).netloc
    else:
        title, company = extract_title_company_from_html(body, url)
        text = plain_text_from_html(body)
    return upsert_job(
        conn,
        {
            "title": title,
            "company": company,
            "location": "",
            "url": url,
            "source": "url",
            "description": text[:20000],
            "raw_json": {"http_status": status, "content_type": content_type},
        },
    )


def discover_careers_page(conn: sqlite3.Connection, url: str, query: str = "") -> dict[str, Any]:
    url = normalize_space(url)
    if not url:
        raise RuntimeError("Careers URL is required.")
    status, body, content_type = fetch_url(url)
    if status >= 400:
        raise RuntimeError(f"Careers URL returned HTTP {status}")
    structured_jobs = extract_structured_jobs_from_page(url, body, query)
    if structured_jobs:
        ids = []
        for job in structured_jobs[:60]:
            ids.append(
                upsert_job(
                    conn,
                    {
                        "title": job.get("title", ""),
                        "company": job.get("company") or company_from_url(url),
                        "location": job.get("location", ""),
                        "url": job.get("url") or url,
                        "source": f"careers:{company_from_url(url) or urllib.parse.urlparse(url).netloc}",
                        "description": job.get("description", ""),
                        "raw_json": {"source_page": url, "structured": job},
                    },
                )
            )
        return {"count": len(ids), "ids": ids, "mode": "structured-jobs", "found_links": len(structured_jobs)}
    links = extract_job_links_from_page(url, body, query)
    if not links:
        page_title, _ = extract_title_company_from_html(body, url)
        page_text = plain_text_from_html(body)
        if looks_like_generic_careers_url(url) or looks_like_generic_careers_page(url, page_title, page_text):
            return {"count": 0, "ids": [], "mode": "no-visible-jobs"}
        job_id = add_job_from_url(conn, url)
        return {"count": 1, "ids": [job_id], "mode": "single-page"}
    ids: list[int] = []
    for link in links[:40]:
        ids.append(
            upsert_job(
                conn,
                {
                    "title": link["title"],
                    "company": company_from_url(link["url"]) or company_from_url(url),
                    "location": extract_location_hint(link.get("context", "")),
                    "url": link["url"],
                    "source": f"careers:{company_from_url(url) or urllib.parse.urlparse(url).netloc}",
                    "description": link.get("context", "") or plain_text_from_html(body)[:3000],
                    "raw_json": {"source_page": url, "anchor": link.get("title", "")},
                },
            )
        )
    return {"count": len(ids), "ids": ids, "mode": "linked-jobs", "found_links": len(links)}


def looks_like_generic_careers_page(url: str, title: str, text: str) -> bool:
    lower_url = url.lower()
    lower_title = title.lower()
    lower_text = text.lower()[:5000]
    generic_url = any(term in lower_url for term in ["/careers", "/career", "/jobs", "/vacancies"])
    generic_title = any(term in lower_title for term in ["careers", "jobs", "work with us", "join us", "vacancies"])
    role_terms = MARKETING_TITLE_SIGNALS + ENTRY_LEVEL_SIGNALS
    role_signal_count = sum(1 for term in role_terms if term in lower_text)
    apply_signal = any(term in lower_text for term in ["apply now", "view job", "job details", "open positions", "current vacancies"])
    return (generic_url or generic_title) and role_signal_count < 2 and not apply_signal


def looks_like_generic_careers_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    path = parsed.path.lower().strip("/")
    if not path:
        return False
    generic_paths = {
        "careers",
        "career",
        "jobs",
        "job",
        "vacancies",
        "work-with-us",
        "join-us",
        "za/careers",
        "corporate/careers",
    }
    return path in generic_paths or path.endswith("/careers") or path.endswith("/jobs")


def extract_location_hint(text: str) -> str:
    lower = text.lower()
    if any(term in lower for term in ["cape town", "western cape"]):
        return "Cape Town, Western Cape"
    if "remote" in lower or "work from home" in lower or "work remotely" in lower:
        return "Remote"
    if "johannesburg" in lower or "sandton" in lower or "gauteng" in lower:
        return "Johannesburg, Gauteng"
    if "durban" in lower or "kwazulu" in lower:
        return "Durban, KwaZulu-Natal"
    return ""


def extract_structured_jobs_from_page(base_url: str, html_value: str, query: str = "") -> list[dict[str, str]]:
    jobs: list[dict[str, str]] = []
    query_terms = [term.strip().lower() for term in re.split(r"[,| ]+", query or "") if len(term.strip()) > 2]
    for script in re.finditer(r'(?is)<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html_value):
        raw = html.unescape(script.group(1)).strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for item in flatten_jsonld(payload):
            type_value = item.get("@type") or item.get("type") or ""
            if isinstance(type_value, list):
                is_job = any(str(value).lower() == "jobposting" for value in type_value)
            else:
                is_job = str(type_value).lower() == "jobposting"
            if not is_job:
                continue
            title = normalize_space(str(item.get("title") or item.get("name") or ""))
            description = plain_text_from_html(str(item.get("description") or ""))
            combined = f"{title} {description}".lower()
            if query_terms and not any(term in combined for term in query_terms + ["marketing", "brand", "content"]):
                continue
            jobs.append(
                {
                    "title": title or "Careers page role",
                    "company": jsonld_org_name(item.get("hiringOrganization")) or company_from_url(base_url),
                    "location": jsonld_location_text(item.get("jobLocation")),
                    "url": str(item.get("url") or item.get("sameAs") or base_url),
                    "description": description[:12000],
                }
            )
    for url in extract_embedded_ats_urls(base_url, html_value):
        title = title_from_url(url) or "Careers page role"
        combined = f"{url} {title}".lower()
        if query_terms and not any(term in combined for term in query_terms + ["marketing", "brand", "content", "job"]):
            continue
        jobs.append(
            {
                "title": title,
                "company": company_from_url(url) or company_from_url(base_url),
                "location": "",
                "url": url,
                "description": nearby_text_for_url(html_value, url)[:2500],
            }
        )
    return dedupe_structured_jobs(jobs)


def flatten_jsonld(payload: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        found.append(payload)
        graph = payload.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                found.extend(flatten_jsonld(item))
    elif isinstance(payload, list):
        for item in payload:
            found.extend(flatten_jsonld(item))
    return found


def jsonld_org_name(value: Any) -> str:
    if isinstance(value, dict):
        return normalize_space(str(value.get("name") or ""))
    if isinstance(value, list):
        for item in value:
            name = jsonld_org_name(item)
            if name:
                return name
    return normalize_space(str(value or ""))


def jsonld_location_text(value: Any) -> str:
    if isinstance(value, dict):
        address = value.get("address")
        if isinstance(address, dict):
            return normalize_space(
                ", ".join(
                    str(address.get(key, ""))
                    for key in ["addressLocality", "addressRegion", "addressCountry"]
                    if address.get(key)
                )
            )
        return normalize_space(str(value.get("name") or ""))
    if isinstance(value, list):
        return "; ".join(filter(None, (jsonld_location_text(item) for item in value)))
    return normalize_space(str(value or ""))


def extract_embedded_ats_urls(base_url: str, html_value: str) -> list[str]:
    urls: list[str] = []
    patterns = [
        r'https?:\\?/\\?/[^"\'<>\s]+teamtailor\.com/jobs/[0-9][^"\'<>\s]*',
        r'https?:\\?/\\?/[^"\'<>\s]+workable\.com/[^"\'<>\s]*(?:jobs|j)/[^"\'<>\s]*',
        r'["\'](/jobs/[0-9][^"\']*)["\']',
        r'["\'](/j/[A-Za-z0-9][^"\']*)["\']',
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, html_value):
            raw = match.group(1) if match.lastindex else match.group(0)
            raw = html.unescape(raw).replace("\\/", "/").strip('"\'')
            absolute = urllib.parse.urljoin(base_url, raw)
            if is_probable_job_link(absolute, title_from_url(absolute)):
                urls.append(absolute)
    deduped: list[str] = []
    seen = set()
    for url in urls:
        key = url.split("?")[0].rstrip("/")
        if key not in seen:
            seen.add(key)
            deduped.append(url)
    return deduped


def nearby_text_for_url(html_value: str, url: str) -> str:
    needle = url.replace("/", "\\/")
    index = html_value.find(url)
    if index < 0:
        index = html_value.find(needle)
    if index < 0:
        return ""
    return nearby_html_text(html_value, index, index + len(url))


def dedupe_structured_jobs(jobs: list[dict[str, str]]) -> list[dict[str, str]]:
    deduped: list[dict[str, str]] = []
    seen = set()
    for job in jobs:
        key = (job.get("url", "").split("?")[0].rstrip("/"), job.get("title", "").lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(job)
    return deduped


def extract_job_links_from_page(base_url: str, html_value: str, query: str = "") -> list[dict[str, str]]:
    query_terms = [term.strip().lower() for term in re.split(r"[,| ]+", query or "") if len(term.strip()) > 2]
    links: list[dict[str, str]] = []
    for match in re.finditer(r'(?is)<a\b([^>]*?)href=["\'](.*?)["\']([^>]*)>(.*?)</a>', html_value):
        href = html.unescape(match.group(2).strip())
        if not href or href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
            continue
        absolute = urllib.parse.urljoin(base_url, href)
        anchor = normalize_space(plain_text_from_html(match.group(4)))
        if not is_probable_job_link(absolute, anchor):
            continue
        combined = f"{absolute} {anchor}".lower()
        if query_terms and not any(term in combined for term in query_terms + ["job", "career", "opening", "position", "marketing", "brand", "content"]):
            continue
        context = nearby_html_text(html_value, match.start(), match.end())
        title = anchor or title_from_url(absolute) or "Careers page role"
        links.append({"url": absolute, "title": title[:180], "context": context[:2500]})
    deduped: list[dict[str, str]] = []
    seen = set()
    for link in links:
        key = link["url"].split("?")[0].rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        deduped.append(link)
    return deduped


def is_probable_job_link(url: str, anchor: str) -> bool:
    lower = f"{url} {anchor}".lower()
    reject = ["privacy", "terms", "cookie", "linkedin.com/company", "facebook.com", "instagram.com", "youtube.com", "twitter.com", "x.com/"]
    if any(term in lower for term in reject):
        return False
    if is_specific_job_url(url):
        return True
    if looks_like_generic_careers_link(url, anchor):
        return False
    strong = [
        "greenhouse.io",
        "lever.co",
        "ashbyhq.com",
        "workable.com",
        "teamtailor.com",
        "smartrecruiters.com",
        "recruitee.com",
    ]
    if any(term in lower for term in strong):
        return True
    title_terms = MARKETING_TITLE_SIGNALS + ENTRY_LEVEL_SIGNALS
    return any(term in lower for term in title_terms) and any(term in lower for term in ["role", "job", "career", "position", "vacancy", "apply"])


def is_specific_job_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    if any(host.endswith(domain) for domain in ["greenhouse.io", "lever.co", "ashbyhq.com", "smartrecruiters.com", "recruitee.com"]):
        return True
    if "workable.com" in host and re.search(r"/j/[a-z0-9-]{5,}", path):
        return True
    if "teamtailor.com" in host and re.search(r"/jobs/[0-9]+", path):
        return True
    if re.search(r"/jobs?/[0-9][a-z0-9-]*", path):
        return True
    if re.search(r"/(?:positions?|openings?|vacancies?)/[a-z0-9-]{5,}", path):
        return True
    if re.search(r"/(?:jobs?|careers?)/[a-z0-9-]*(marketing|brand|content|social|copywriter|growth|campaign)[a-z0-9-]*", path):
        return True
    return False


def detect_application_platform(url: str, source: str = "") -> str:
    host = normalize_domain(url)
    lower_source = normalize_space(source).lower()
    if host.endswith("linkedin.com") or lower_source.startswith("linkedin"):
        return "linkedin"
    if host.endswith("indeed.com") or host.endswith("indeed.co.za") or lower_source.startswith("indeed"):
        return "indeed"
    if host.endswith("greenhouse.io") or lower_source.startswith("greenhouse:"):
        return "greenhouse"
    if host.endswith("lever.co") or lower_source.startswith("lever:"):
        return "lever"
    if host.endswith("ashbyhq.com") or lower_source.startswith("ashby:"):
        return "ashby"
    if host.endswith("smartrecruiters.com") or lower_source.startswith("smartrecruiters:"):
        return "smartrecruiters"
    if "workable.com" in host or lower_source.startswith("workable:"):
        return "workable"
    if "teamtailor.com" in host or lower_source.startswith("teamtailor:"):
        return "teamtailor"
    if host.endswith("recruitee.com") or lower_source.startswith("recruitee:"):
        return "recruitee"
    return "custom"


MANUAL_FIRST_PLATFORMS = {"smartrecruiters", "workday", "ashby", "greenhouse", "lever", "workable", "teamtailor", "recruitee"}
DOMAIN_RESTRICTION_COOLDOWN_HOURS = {
    "smartrecruiters": 12,
    "workday": 12,
    "greenhouse": 6,
    "lever": 6,
    "ashby": 6,
    "default": 6,
}
DOMAIN_PREP_RATE_LIMIT_MINUTES = {
    "smartrecruiters": 45,
    "workday": 45,
    "greenhouse": 15,
    "lever": 15,
    "ashby": 15,
    "workable": 15,
    "teamtailor": 15,
    "recruitee": 15,
    "default": 5,
}


def looks_like_generic_careers_link(url: str, anchor: str) -> bool:
    cleaned_anchor = normalize_space(anchor).lower().strip(" .:-")
    title = title_from_url(url).lower().strip(" .:-")
    labels = {cleaned_anchor, title}
    generic_exact = {
        "",
        "careers",
        "career",
        "jobs",
        "job",
        "view",
        "view jobs",
        "view all",
        "overview",
        "blog",
        "events",
        "life at luno",
        "life at",
        "benefits",
        "our culture",
        "our company",
        "faqs",
        "retail",
        "manufacturing",
        "technology",
        "specialist & support services",
        "omnichannel",
        "sport lifestyle",
        "ladies and family",
        "men's fashion",
        "value",
        "speciality",
        "learning & development opportunities",
        "youth workplace opportunities",
        "product design & trend",
        "non-merchandise procurement",
        "logistics",
        "contact centres",
        "human resources",
        "finance",
        "property management & store design",
        "assurance, forensics & security",
        "get started",
    }
    if labels & generic_exact:
        return True
    parsed = urllib.parse.urlparse(url)
    path = parsed.path.lower().strip("/")
    if path in {"careers", "career", "jobs", "job", "vacancies"}:
        return True
    if len(cleaned_anchor.split()) <= 3 and any(term in cleaned_anchor for term in ["overview", "benefits", "culture", "company", "blog", "faq"]):
        return True
    return False


def nearby_html_text(html_value: str, start: int, end: int) -> str:
    chunk = html_value[max(0, start - 800) : min(len(html_value), end + 1200)]
    return normalize_space(plain_text_from_html(chunk))


def title_from_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    slug = Path(parsed.path.rstrip("/")).name
    if not slug:
        return ""
    return normalize_space(re.sub(r"[-_]+", " ", slug)).title()


def generate_cover_letter(profile: dict[str, str], job: dict[str, Any]) -> str:
    name = profile.get("full_name", "Phillip")
    title = job.get("title") or "the role"
    company = job.get("company") or "your team"
    company_hook = company_hook_from_job(job)
    role_priorities = summarize_role_priorities(job.get("description", ""))
    fit_line = fit_summary_for_job(profile, job)

    return phillip_voice_text(textwrap.dedent(
        f"""
        Dear {company} hiring team,

        I am applying for the {title} role because {company_hook}

        What stands out to me in the role is the focus on {role_priorities}

        {fit_line}

        I would welcome the chance to discuss how I could support {company}'s marketing work in a practical, commercially useful way.

        Kind regards,
        {name}
        """
    ).strip(), "cover_letter")


def summarize_profile_evidence(cv_text: str) -> str:
    if not cv_text:
        return (
            "I have kept this draft conservative because the app does not yet have parsed CV text. "
            "Paste your CV/profile notes into the Profile tab and regenerate this for stronger evidence."
        )
    sentences = re.split(r"(?<=[.!?])\s+", cv_text)
    useful = [
        sentence.strip()
        for sentence in sentences
        if any(term in sentence.lower() for term in MARKETING_KEYWORDS)
    ][:3]
    if not useful:
        useful = [sentence.strip() for sentence in sentences[:3] if len(sentence.strip()) > 30]
    if not useful:
        return ""
    return "Evidence from my background includes: " + " ".join(useful)


def company_hook_from_job(job: dict[str, Any]) -> str:
    company = normalize_space(str(job.get("company", ""))) or "the company"
    description = normalize_space(str(job.get("description", "")))
    lower = description.lower()
    if "event" in lower and "saas" in lower:
        return f"{company} is building a product around live events and customer experience, which is the kind of practical marketing environment I want to work in."
    if "supplement" in lower or "wellness brand" in lower or "health and wellness" in lower:
        return f"{company} is operating in a health and wellness space that matches my interest in fitness-adjacent consumer brands."
    if "seo" in lower and "content" in lower:
        return f"the role combines writing, research, SEO, and brand messaging in a way that fits the work I want to build on."
    if "media" in lower and "analytics" in lower:
        return f"the role sits at the point where media strategy, analytics, and client-facing communication meet, which is a strong fit for how I like to work."
    return f"it sits close to the kind of marketing work I am targeting: practical brand, content, campaign, and growth work."


def summarize_role_priorities(description: str) -> str:
    priorities = job_priority_points(description)
    if priorities:
        return ", ".join(priorities[:4])
    return company_angle_from_job(description)


def fit_summary_for_job(profile: dict[str, str], job: dict[str, Any]) -> str:
    strengths = profile_strengths_for_job(profile, job)
    role_priorities = summarize_role_priorities(str(job.get("description", "")))
    return (
        f"My background is strongest around {strengths}. That gives me a good base to contribute across {role_priorities}, "
        "while bringing a grounded, early-career perspective and a willingness to do the work properly."
    )


def company_angle_from_job(description: str) -> str:
    lower = description.lower()
    angles: list[str] = []
    checks = [
        ("brand", "brand positioning"),
        ("content", "content planning"),
        ("social", "social media execution"),
        ("campaign", "campaign delivery"),
        ("community", "community growth"),
        ("analytics", "performance measurement"),
        ("partnership", "partnership development"),
        ("event", "events or activations"),
        ("seo", "search visibility"),
        ("email", "email/CRM communication"),
    ]
    for token, label in checks:
        if token in lower:
            angles.append(label)
    if not angles:
        return "understanding the audience, communicating the offer clearly, and improving marketing execution"
    return ", ".join(angles[:5])


def job_priority_points(description: str) -> list[str]:
    lower = normalize_space(description).lower()
    priorities: list[str] = []
    checks = [
        ("hubspot", "HubSpot ownership"),
        ("seo", "SEO execution"),
        ("lifecycle", "lifecycle email"),
        ("email", "email/CRM work"),
        ("newsletter", "newsletter and content work"),
        ("landing page", "landing page messaging"),
        ("copy", "copy and messaging"),
        ("social", "social content"),
        ("tiktok", "TikTok strategy"),
        ("tiktok shop", "TikTok Shop growth"),
        ("paid ads", "paid ads"),
        ("meta", "Meta ads"),
        ("partnership", "partnership marketing"),
        ("influencer", "influencer work"),
        ("analytics", "analytics and reporting"),
        ("reporting", "performance reporting"),
        ("media planning", "media planning"),
        ("forecast", "forecasting"),
        ("client", "client communication"),
        ("e-commerce", "e-commerce growth"),
        ("ecommerce", "e-commerce growth"),
        ("event", "event-focused marketing"),
        ("saas", "SaaS product marketing"),
    ]
    for token, label in checks:
        if token in lower and label not in priorities:
            priorities.append(label)
    return priorities[:6]


def profile_strengths_for_job(profile: dict[str, str], job: dict[str, Any]) -> str:
    lower = f"{job.get('title', '')} {job.get('description', '')}".lower()
    strengths: list[str] = []
    if any(token in lower for token in ["seo", "copy", "content", "blog", "landing page"]):
        strengths.append("writing clear content and adapting tone to different audiences")
    if any(token in lower for token in ["analytics", "reporting", "data", "research"]):
        strengths.append("market research and using data to support decisions")
    if any(token in lower for token in ["social", "tiktok", "creative", "campaign"]):
        strengths.append("hands-on content and campaign execution")
    if any(token in lower for token in ["brand", "consumer", "community", "events", "fitness", "wellness"]):
        strengths.append("brand-aware work with a genuine interest in sport, fitness, and consumer audiences")
    if any(token in lower for token in ["media", "paid", "performance", "growth"]):
        strengths.append("commercially focused marketing thinking with a willingness to measure what is working")
    if not strengths:
        strengths.append("marketing fundamentals, practical execution, and a willingness to learn quickly")
    return ", ".join(dedupe_keep_order(strengths)[:3])


def generate_cv_notes(profile: dict[str, str], job: dict[str, Any]) -> str:
    description = job.get("description", "").lower()
    matches = []
    for term in list(MARKETING_KEYWORDS) + list(PREFERRED_KEYWORDS):
        if term in description:
            matches.append(term)
    if not matches:
        matches.append("role-specific marketing experience")
    return textwrap.dedent(
        f"""
        CV tailoring notes for {job.get('title')} at {job.get('company')}:

        - Keep the original CV truthful; do not add unverified claims.
        - Move the most relevant marketing, brand, content, campaign, social, or partnership work into the top third.
        - Mirror these job keywords where they are genuinely supported by your experience: {", ".join(matches[:14])}.
        - Add a short profile summary aimed at marketing roles in outdoor, sports, fitness, lifestyle, or consumer brands when relevant.
        - Keep metrics only where they are real and defensible.
        """
    ).strip()


AI_SOUNDING_PHRASES = [
    "I hope you are well",
    "I am reaching out",
    "I would welcome the chance",
    "I bring a focused marketing mindset",
    "customer-facing growth",
    "measurable customer engagement",
    "practical, audience-focused marketing work",
    "brand consistency across the customer journey",
    "I would approach this by focusing on",
]


def phillip_voice_text(text: str, kind: str = "email") -> str:
    """Make generated copy sound more like Phillip without adding new facts."""
    if not text:
        return ""
    out = text.strip()
    replacements = {
        "I hope you are well.": "Hope you're well.",
        "I am reaching out because": "I'm reaching out because",
        "I have been following": "I've been following",
        "I was drawn to": "I liked",
        "I recently applied for": "I applied for",
        "and wanted to follow up on my application.": "and just wanted to follow up.",
        "I would welcome the chance to discuss": "I'd really appreciate the chance to discuss",
        "I would appreciate the chance to introduce myself properly.": "I'd appreciate the chance to introduce myself properly.",
        "I am applying for": "I'm applying for",
        "I am interested in": "I'm interested in",
        "I bring a focused marketing mindset, strong interest in sports/fitness/outdoor and consumer brands, and a practical approach to turning ideas into useful campaigns, content, and customer engagement.": "I think my strongest fit is the mix of marketing training, hands-on content work, research experience, and a real interest in sport, fitness, and consumer brands.",
        "I would keep the work commercially grounded, brand-aware, and measurable.": "I'd try to keep the work practical, brand-aware, and measured properly.",
        "My background combines a UCT Business Science Marketing degree, Google Analytics certification, hands-on social content work, market research, and a strong personal connection to sport and endurance training.": "By way of background, I studied Business Science Marketing at UCT, have done hands-on content work and market research, and I also have a strong personal link to sport through coaching and Ironman 70.3 training.",
        "The role stood out because it connects with practical, audience-focused marketing work and brand execution.": "The role stood out because it sits close to the kind of marketing work I'm trying to build my career around: content, brand, community, and practical campaign execution.",
        "particularly around content, brand, community, campaign execution, and measurable customer engagement.": "especially on the content, brand, community, and campaign side.",
        "Kind regards,": "Kind regards,",
    }
    for old, new in replacements.items():
        out = out.replace(old, new)

    out = re.sub(r"\n[ \t]+", "\n", out)
    out = re.sub(r" {2,}", " ", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    out = apply_writing_sample_voice(out, kind)
    if kind in {"email", "outreach", "follow_up"}:
        out = tighten_email(out)
    return out.strip()


def apply_writing_sample_voice(text: str, kind: str) -> str:
    """Use Phillip's saved writing sample as a light style guide without copying it."""
    notes = current_writing_style_notes()
    if not notes:
        return text
    out = text
    lower_notes = notes.lower()
    if "contractions seen: none obvious" in lower_notes:
        contraction_replacements = {
            "I'm ": "I am ",
            "I've ": "I have ",
            "I'd ": "I would ",
            "you're ": "you are ",
            "You're ": "You are ",
        }
        # Keep follow-ups warm, but make formal application material closer to the sample.
        if kind in {"cover_letter", "answers", "outreach"}:
            for old, new in contraction_replacements.items():
                out = out.replace(old, new)
    if "longer reflective sentences" in lower_notes and kind in {"cover_letter", "answers"}:
        out = out.replace(
            "The role stood out because it sits close to the kind of marketing work I am trying to build my career around: content, brand, community, and practical campaign execution.",
            "The role stood out to me because it connects closely with the kind of marketing work I am trying to build my career around, especially content, brand, community, and practical campaign execution.",
        )
        out = out.replace(
            "I think my strongest fit is the mix of marketing training, hands-on content work, research experience, and a real interest in sport, fitness, and consumer brands.",
            "I think my strongest fit is the way my marketing training, hands-on content work, research experience, and genuine interest in sport, fitness, and consumer brands work together.",
        )
    return out


_STYLE_NOTES_CACHE: dict[str, str] = {"notes": "", "loaded_at": ""}


def current_writing_style_notes() -> str:
    # Cache briefly because this function runs for every generated text block.
    now = time.time()
    loaded_at = float(_STYLE_NOTES_CACHE.get("loaded_at") or 0)
    if _STYLE_NOTES_CACHE.get("notes") and now - loaded_at < 60:
        return _STYLE_NOTES_CACHE["notes"]
    try:
        with connect() as conn:
            row = conn.execute("select value from profile where key='writing_style_notes'").fetchone()
            notes = str(row["value"] if row else "")
    except Exception:
        notes = ""
    _STYLE_NOTES_CACHE["notes"] = notes
    _STYLE_NOTES_CACHE["loaded_at"] = str(now)
    return notes


def tighten_email(text: str) -> str:
    paragraphs = [paragraph.strip() for paragraph in text.split("\n\n") if paragraph.strip()]
    tightened: list[str] = []
    for paragraph in paragraphs:
        if len(paragraph) > 700 and ". " in paragraph:
            sentences = re.split(r"(?<=[.!?])\s+", paragraph)
            paragraph = " ".join(sentences[:4]).strip()
        tightened.append(paragraph)
    return "\n\n".join(tightened)


def voice_check(text: str) -> dict[str, Any]:
    lower = text.lower()
    flags = [phrase for phrase in AI_SOUNDING_PHRASES if phrase.lower() in lower]
    long_sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", text)
        if len(sentence.split()) > 34
    ]
    return {
        "flags": flags[:10],
        "long_sentence_count": len(long_sentences),
        "status": "needs review" if flags or long_sentences else "natural enough",
    }


def generate_answers(profile: dict[str, str], job: dict[str, Any]) -> str:
    company = job.get("company") or "the company"
    title = job.get("title") or "this role"
    priorities = summarize_role_priorities(str(job.get("description", "")))
    strengths = profile_strengths_for_job(profile, job)
    return phillip_voice_text(textwrap.dedent(
        f"""
        Why are you interested in this role?
        I am interested in the {title} role because it combines {priorities}, which is the kind of practical marketing work I want to build my career around. I like roles where the work is close to the audience, the message, and the commercial result, and that comes through clearly in this role.

        Why should we hire you?
        I would bring {strengths}. I am early-career, but I take the work seriously, I am comfortable learning fast, and I would approach the role with a mix of curiosity, discipline, and practicality rather than trying to sound more senior than I am.

        What is your work authorization?
        {profile.get("work_authorization", "Confirm before submitting.")}

        Salary expectation:
        {profile.get("salary_expectation", "Ask before answering.")}

        Availability / start date:
        {profile.get("availability", profile.get("notice_period", "Ask before answering."))}

        Notice period:
        {profile.get("notice_period", "Ask before answering.")}

        References:
        {profile.get("references_policy", "Available on request.")}

        Demographic questions:
        {profile.get("demographics_policy", "Prefer not to answer unless configured otherwise.")}
        """
    ).strip(), "answers")


def generate_follow_up(profile: dict[str, str], job: dict[str, Any]) -> str:
    return compose_follow_up(profile, job, {})


def generate_application_research(job: dict[str, Any], application: dict[str, Any] | None = None, research_url: str = "") -> tuple[str, str, str]:
    application = application or {}
    company = normalize_space(str(job.get("company", ""))) or "the company"
    title = normalize_space(str(job.get("title", ""))) or "the role"
    description = normalize_space(str(job.get("description", "")))
    sources: list[str] = []
    notes: list[str] = [f"Company research notes for {company} - {title}", ""]

    if job.get("url"):
        sources.append(f"Job posting: {job.get('url')}")
    if description:
        notes.extend(
            [
                f"- Role/business angle from posting: {company_angle_from_job(description)}.",
                f"- Relevant signals found in the posting: {', '.join(research_signals(description)) or 'none obvious'}.",
            ]
        )
    else:
        notes.append("- Job posting description was not available in the local database.")

    research_urls = company_research_url_candidates(job, application, research_url)
    researched_url = research_urls[0] if research_urls else ""
    if research_urls:
        fetched_count = 0
        failed_urls: list[str] = []
        combined_signals: list[str] = []
        notes.append("")
        notes.append("Fetched public research pages:")
        for candidate_url in research_urls[:4]:
            if fetched_count >= 3:
                break
            page_result = fetch_research_page(candidate_url)
            if page_result.get("error"):
                failed_urls.append(f"{candidate_url} ({page_result['error']})")
                continue
            fetched_count += 1
            extracted = page_result["facts"]
            combined_signals.extend(page_result.get("signals", []))
            notes.append(f"- Source: {candidate_url}")
            if extracted.get("title"):
                notes.append(f"  - Page title: {extracted['title']}.")
            if extracted.get("description"):
                notes.append(f"  - Page description: {extracted['description']}.")
            if extracted.get("headings"):
                notes.append(f"  - Useful headings: {', '.join(extracted['headings'][:5])}.")
            for fact in extracted.get("facts", [])[:4]:
                notes.append(f"  - Evidence: {fact}")
            sources.append(f"Research page: {candidate_url}")
        if combined_signals:
            notes.append(f"- Combined company/page signals: {', '.join(dedupe_keep_order(combined_signals)[:8])}.")
        if failed_urls:
            notes.append(f"- Some research pages could not be fetched: {'; '.join(failed_urls[:3])}.")
    else:
        notes.append("- No company/about page was provided or inferred. Add a company website or about/careers URL for stronger research.")

    company_notes = normalize_space(str(application.get("company_notes", "")))
    if company_notes:
        notes.append(f"- Phillip's saved personalization notes: {company_notes}")

    notes.extend(
        [
            "",
            "Suggested application angle:",
            f"- Connect Phillip's UCT marketing background, analytics certification, content work, market research, and sport/fitness interests to {company}'s visible priorities.",
            "- Keep claims grounded in the CV and the cited sources above.",
        ]
    )
    return "\n".join(notes), "\n".join(sources), researched_url


def fetch_research_page(researched_url: str) -> dict[str, Any]:
    try:
        try:
            status, body, content_type = fetch_url(researched_url)
            if status >= 400:
                return {"error": f"HTTP {status}"}
            page_text = plain_text_from_html(body if "html" in content_type.lower() else body)
            return {"facts": extract_research_page_facts(body), "signals": research_signals(page_text)}
        except Exception as exc:
            return {"error": str(exc)}
    except Exception as exc:
        return {"error": str(exc)}


def company_research_url_candidates(
    job: dict[str, Any],
    application: dict[str, Any] | None = None,
    research_url: str = "",
) -> list[str]:
    application = application or {}
    candidates: list[str] = []
    company_key = normalize_space(str(job.get("company", ""))).lower()
    if company_key in KNOWN_COMPANY_RESEARCH_URLS:
        candidates.append(KNOWN_COMPANY_RESEARCH_URLS[company_key])
    for value in [research_url, str(application.get("research_url", ""))]:
        value = normalize_space(value)
        if value:
            candidates.append(value)
    raw_json = str(job.get("raw_json", ""))
    description = str(job.get("description", ""))
    company_tokens = company_url_tokens(str(job.get("company", "")))
    for url in extract_research_urls_from_text("\n".join([description, raw_json])):
        if url_matches_company_tokens(url, company_tokens):
            candidates.append(url)
    job_url = normalize_space(str(job.get("url", "")))
    if job_url and is_useful_company_url(job_url) and not is_job_board_url(job_url):
        parsed = urllib.parse.urlparse(job_url)
        root = f"{parsed.scheme}://{parsed.netloc}"
        candidates.extend([root, urllib.parse.urljoin(root, "/about"), urllib.parse.urljoin(root, "/careers")])
    return dedupe_keep_order([url for url in candidates if is_useful_company_url(url)])[:6]


def extract_research_urls_from_text(text: str) -> list[str]:
    urls = []
    for match in re.finditer(r"https?://[^\s\"'<>]+", text):
        url = html.unescape(match.group(0)).replace("\\/", "/").replace("\\", "").rstrip(").,;]")
        if is_useful_company_url(url):
            urls.append(url)
    return dedupe_keep_order(urls)


def is_job_board_url(url: str) -> bool:
    lower = url.lower()
    blocked = [
        "remoteok.com",
        "remoteok.io",
        "remotive.com",
        "arbeitnow.com",
        "linkedin.com/jobs",
        "indeed.com",
        "greenhouse.io",
        "lever.co",
        "ashbyhq.com",
        "smartrecruiters.com",
        "recruitee.com",
        "workable.com",
        "teamtailor.com",
    ]
    return any(term in lower for term in blocked)


# Platforms that require paid membership, forced account creation before viewing
# the application, or CAPTCHA-gated signups — jobs from these are filtered out.
BLOCKED_JOB_PLATFORMS = [
    "remoteok.com",
    "indeed.com",
    "indeed.co.za",
    "linkedin.com",
    "ziprecruiter.com",
    "monster.com",
    "careerbuilder.com",
    "glassdoor.com",
    "simplyhired.com",
    "jobvite.com/apply-redirect",
    "jobs.com",
]


def is_board_prep_blocked_url(url: str) -> bool:
    lower = normalize_space(url).lower()
    if not lower:
        return False
    for platform in BLOCKED_JOB_PLATFORMS:
        if platform in lower:
            return True
    return False


def is_paywalled_or_gated_source(url: str) -> bool:
    """Returns True for job board URLs that require signup/payment to apply."""
    lower = normalize_space(url).lower()
    for platform in BLOCKED_JOB_PLATFORMS:
        if platform in lower:
            return True
    return False


ATS_APPLY_HOSTS = [
    "boards.greenhouse.io",
    "jobs.lever.co",
    "ashbyhq.com",
    "jobs.smartrecruiters.com",
    "jobvite.com",
    "myworkdayjobs.com",
    "icims.com",
    "taleo.net",
    "breezy.hr",
    "recruitee.com",
    "apply.workable.com",
    "careers.smartrecruiters.com",
]


def resolve_board_apply_url(conn: sqlite3.Connection, job_id: int) -> dict[str, Any]:
    """
    For board listing URLs (e.g. RemoteOK), fetch the page and extract the real
    company or ATS apply URL, then save it back to the job record.
    """
    job = row_to_dict(conn.execute("select * from jobs where id=?", (job_id,)).fetchone())
    if not job:
        return {"ok": False, "error": "Job not found."}
    current_url = str(job.get("url") or "")
    if not is_board_prep_blocked_url(current_url):
        return {"ok": True, "url": current_url, "changed": False}

    # Try raw_json first — some APIs include the real apply URL
    raw = {}
    try:
        raw = json.loads(str(job.get("raw_json") or "{}"))
    except Exception:
        pass
    for key in ("apply_url", "applyUrl", "applicationUrl", "externalUrl"):
        candidate = str(raw.get(key) or "")
        if candidate and candidate.startswith("http") and not is_board_prep_blocked_url(candidate):
            conn.execute("update jobs set url=?, updated_at=? where id=?", (candidate, now_iso(), job_id))
            conn.commit()
            return {"ok": True, "url": candidate, "changed": True}

    # Fetch the listing page and look for external apply links
    try:
        status, body, _ = fetch_url(current_url, timeout=15)
    except Exception as exc:
        return {"ok": False, "error": f"Could not fetch listing page: {exc}"}
    if status >= 400:
        return {"ok": False, "error": f"Listing page returned HTTP {status}."}

    # Extract all hrefs from the page
    found: list[str] = []
    for href_match in re.finditer(r'href=["\']([^"\']{10,})["\']', body):
        href = href_match.group(1)
        if not href.startswith("http"):
            continue
        parsed = urllib.parse.urlparse(href)
        host = parsed.netloc.lower().replace("www.", "")
        if any(ats in host for ats in ATS_APPLY_HOSTS):
            found.append(href)
        elif any(kw in href.lower() for kw in ["/apply", "/application", "/job-application"]):
            if "remoteok.com" not in href and "linkedin.com" not in href and "indeed.com" not in href:
                found.append(href)

    if found:
        best = found[0]
        conn.execute("update jobs set url=?, updated_at=? where id=?", (best, now_iso(), job_id))
        conn.commit()
        return {"ok": True, "url": best, "changed": True}

    return {"ok": False, "error": "Could not find a direct apply link on this listing page. Please paste it manually."}


def is_useful_company_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.lower().replace("www.", "")
    if not parsed.scheme.startswith("http") or not host:
        return False
    if is_job_board_url(url):
        return False
    reject_hosts = [
        "linkedin.com",
        "facebook.com",
        "instagram.com",
        "twitter.com",
        "x.com",
        "youtube.com",
        "greenhouse.io",
        "lever.co",
        "ashbyhq.com",
        "workable.com",
        "teamtailor.com",
        "smartrecruiters.com",
        "recruitee.com",
        "customer.io",
        "mailchimp.com",
        "hubspot.com",
        "salesforce.com",
        "google.com",
        "meta.com",
    ]
    if any(host == reject or host.endswith("." + reject) for reject in reject_hosts):
        return False
    reject_paths = ["/privacy", "/terms", "/cookie", "/login", "/signin", "/apply"]
    return not any(parsed.path.lower().startswith(path) for path in reject_paths)


def company_url_tokens(company: str) -> list[str]:
    tokens = []
    for token in re.split(r"[^a-z0-9]+", company.lower()):
        if len(token) >= 4 and token not in {"group", "company", "limited", "marketing", "careers"}:
            tokens.append(token)
    compact = re.sub(r"[^a-z0-9]+", "", company.lower())
    if len(compact) >= 4:
        tokens.append(compact)
    return dedupe_keep_order(tokens)


def url_matches_company_tokens(url: str, tokens: list[str]) -> bool:
    if not tokens:
        return False
    host = urllib.parse.urlparse(url).netloc.lower().replace("www.", "")
    host_compact = re.sub(r"[^a-z0-9]+", "", host)
    return any(token in host_compact for token in tokens)


def research_signals(text: str) -> list[str]:
    lower = f" {text.lower()} "
    groups = [
        ("sports/fitness/outdoor", ["sport", "fitness", "wellness", "athlete", "outdoor", "running", "cycling", "training"]),
        ("content/social", ["content", "social media", "instagram", "tiktok", "creative", "copy"]),
        ("performance marketing", ["paid media", "performance marketing", "meta", "google ads", "roas", "cac", "conversion"]),
        ("events/community", ["event", "community", "activation", "ambassador", "partnership"]),
        ("analytics/research", ["analytics", "research", "insight", "data", "dashboard", "measurement"]),
        ("AI/technology", [" ai ", "artificial intelligence", "automation", "platform", "software", "app"]),
        ("consumer brand", ["consumer", "brand", "retail", "apparel", "customer", "campaign"]),
    ]
    found = []
    for label, terms in groups:
        if any(term in lower for term in terms):
            found.append(label)
    return found[:6]


def extract_html_title(value: str) -> str:
    match = re.search(r"(?is)<title[^>]*>(.*?)</title>", value)
    if not match:
        return ""
    return normalize_space(plain_text_from_html(match.group(1)))[:160]


def extract_research_page_facts(html_value: str) -> dict[str, Any]:
    title = extract_html_title(html_value)
    description = ""
    desc_match = re.search(
        r'(?is)<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
        html_value,
    ) or re.search(
        r'(?is)<meta[^>]+content=["\'](.*?)["\'][^>]+name=["\']description["\']',
        html_value,
    )
    if desc_match:
        description = normalize_space(html.unescape(desc_match.group(1)))[:260]
    headings = [
        normalize_space(plain_text_from_html(match.group(1)))
        for match in re.finditer(r"(?is)<h[1-3][^>]*>(.*?)</h[1-3]>", html_value)
    ]
    headings = [heading for heading in headings if 4 <= len(heading) <= 120]
    page_text = plain_text_from_html(html_value)
    sentences = [
        normalize_space(sentence)
        for sentence in re.split(r"(?<=[.!?])\s+", page_text)
        if 40 <= len(sentence.strip()) <= 240
    ]
    priority_terms = [
        "mission",
        "brand",
        "community",
        "sport",
        "fitness",
        "outdoor",
        "wellness",
        "career",
        "marketing",
        "campaign",
        "sustainability",
        "athlete",
        "customer",
        "product",
    ]
    facts = []
    for sentence in sentences:
        lower = sentence.lower()
        if any(term in lower for term in priority_terms):
            facts.append(sentence)
        if len(facts) >= 8:
            break
    return {
        "title": title,
        "description": description,
        "headings": dedupe_keep_order(headings)[:8],
        "facts": dedupe_keep_order(facts)[:8],
    }


def dedupe_keep_order(values: list[str]) -> list[str]:
    seen = set()
    out = []
    for value in values:
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def compose_follow_up(profile: dict[str, str], job: dict[str, Any], application: dict[str, Any]) -> str:
    sender_name = profile.get("full_name", "Phillip de Nobrega")
    company = normalize_space(str(job.get("company") or application.get("company") or "your team"))
    title = normalize_space(str(job.get("title") or application.get("title") or "the role"))
    contact_name = normalize_space(str(application.get("contact_name", "")))
    contact_role = normalize_space(str(application.get("contact_role", "")))
    company_notes = normalize_space(str(application.get("company_notes", "")))
    greeting = f"Hi {contact_name}," if contact_name else f"Hi {company} team,"
    role_context = f" I noticed your work as {contact_role}, so I wanted to reach out directly." if contact_role else ""
    if company_notes:
        company_line = f"What stood out to me about {company} was {company_notes}."
    else:
        company_line = f"The role stood out because of its focus on {summarize_role_priorities(str(job.get('description', '')))}."
    background_line = (
        f"My background combines a UCT Business Science Marketing degree, Google Analytics certification, and {profile_strengths_for_job(profile, job)}."
    )
    return phillip_voice_text(textwrap.dedent(
        f"""
        {greeting}

        I hope you are well. I recently applied for the {title} role at {company} and wanted to follow up on my application.{role_context}

        {company_line} {background_line}

        I would welcome the chance to discuss how I could support {company}'s marketing work, particularly around content, brand, community, campaign execution, and measurable customer engagement.

        Kind regards,
        {sender_name}
        """
    ).strip(), "follow_up")


def compose_cold_outreach(profile: dict[str, str], company: str, contact_name: str = "", company_notes: str = "", style: str = "intro") -> str:
    sender_name = profile.get("full_name", "Phillip de Nobrega")
    greeting = f"Hi {contact_name}," if contact_name else f"Hi {company} team,"
    reason = normalize_space(company_notes).rstrip(".")
    if reason:
        brand_line = f"What stands out to me is {reason}."
    else:
        brand_line = "What stands out to me is the way the brand connects with its audience."
    style_key = normalize_space(style).lower() or "intro"
    if style_key == "proposal":
        return phillip_voice_text(textwrap.dedent(
            f"""
            {greeting}

            I wanted to send a slightly more direct note because {company} is exactly the kind of brand I would be excited to work with. {brand_line}

            I am a UCT Business Science Marketing graduate with hands-on experience across content creation, market research, brand thinking, Google Analytics, Meta Ads Manager, Canva, and AI-assisted product work. I am still early-career, but I think I could add value quickly in the kind of practical marketing work that often needs consistent support rather than inflated senior claims.

            The main areas where I think I could help are:
            - content planning and day-to-day social support
            - brand and audience research
            - campaign execution support
            - reporting, analytics, and marketing admin
            - community, partnerships, and general junior marketing support

            If there is any space for a junior marketer, a short trial, or project-based support, I would really value the chance to introduce myself properly and show how I could contribute.

            Kind regards,
            {sender_name}
            """
        ).strip(), "outreach")
    return phillip_voice_text(textwrap.dedent(
        f"""
        {greeting}

        I wanted to reach out because I have been following {company} for a while. {brand_line} I am a UCT Business Science Marketing graduate with hands-on experience across content creation, market research, brand thinking, Google Analytics, Meta Ads Manager, Canva, and AI-assisted product work.

        I am especially interested in outdoor, sport, fitness, wellness, and consumer brands where marketing work can actually strengthen community, customer engagement, and brand feel. I think I would be a strong junior-level fit for practical support across content, campaign execution, social, research, reporting, and day-to-day brand work.

        If there is room for someone early-career but hardworking, sharp, and genuinely excited about the brand, I would really value the chance to introduce myself properly. I would also be open to a junior role, a short trial period, or project-based support if that is more useful.

        Kind regards,
        {sender_name}
        """
    ).strip(), "outreach")


def compose_lead_outreach(profile: dict[str, str], lead: dict[str, Any]) -> str:
    company = normalize_space(str(lead.get("company", ""))) or "your company"
    contact_name = normalize_space(str(lead.get("contact_name", "")))
    contact_role = normalize_space(str(lead.get("contact_role", "")))
    company_notes = normalize_space(str(lead.get("company_notes", "")))
    industry = normalize_space(str(lead.get("industry", "")))
    style = normalize_space(str(lead.get("outreach_style", ""))) or "intro"
    body = compose_cold_outreach(profile, company, contact_name, company_notes, style)
    if contact_role:
        body = body.replace(
            "I wanted to reach out because",
            f"I noticed your work as {contact_role}. I wanted to reach out because",
            1,
        )
    if industry:
        body = body.replace(
            "I am especially interested in outdoor, sport, fitness, wellness, and consumer brands",
            f"I am especially interested in {industry} brands and in outdoor, sport, fitness, wellness, and consumer work",
            1,
        )
    return phillip_voice_text(body, "outreach")


def lead_subject(lead: dict[str, Any]) -> str:
    company = normalize_space(str(lead.get("company", ""))) or "your company"
    return f"Quick introduction - marketing support for {company}"


def outreach_documents_folder(lead: dict[str, Any]) -> Path:
    return DOCS_DIR / f"outreach-{safe_filename(str(lead.get('company', 'company')))}-{lead.get('id') or 'draft'}"


def render_outreach_proposal_text(profile: dict[str, str], lead: dict[str, Any]) -> str:
    company = normalize_space(str(lead.get("company", ""))) or "the company"
    industry = normalize_space(str(lead.get("industry", ""))) or "consumer"
    brand_fit = normalize_space(str(lead.get("company_notes", ""))) or "a strong brand fit and real overlap with Phillip's interests."
    sender_name = normalize_space(str(profile.get("full_name", ""))) or "Phillip de Nobrega"
    return "\n".join([
        f"Outreach Proposal - {company}",
        "",
        f"Prepared for: {company}",
        f"Prepared by: {sender_name}",
        f"Category: {industry}",
        "",
        "Why this brand stands out",
        brand_fit,
        "",
        "What Phillip could help with",
        "- Content planning and social support",
        "- Brand and audience research",
        "- Campaign execution support",
        "- Reporting, analytics, and day-to-day marketing admin",
        "- Junior-level support across community, partnerships, and digital work",
        "",
        "Working style",
        "Phillip is looking for an early-career marketing role and is open to a junior position, a short trial period, or project-based support where it makes sense.",
        "",
        "Contact approach",
        "Use the outreach email as the main first-touch message. Keep the tone warm, specific, and personal.",
    ]).strip()


def render_outreach_proposal_rtf(profile: dict[str, str], lead: dict[str, Any]) -> str:
    body = render_outreach_proposal_text(profile, lead)
    return (
        "{\\rtf1\\ansi\\deff0\n"
        "{\\fonttbl{\\f0 Arial;}}\n"
        "\\fs24\n"
        f"{rtf_escape(body)}\n"
        "}\n"
    )


def outreach_readiness(lead: dict[str, Any]) -> dict[str, Any]:
    issues: list[str] = []
    if not normalize_space(str(lead.get("company", ""))):
        issues.append("missing company")
    if not normalize_space(str(lead.get("website", ""))):
        issues.append("missing website")
    if not normalize_space(str(lead.get("company_notes", ""))):
        issues.append("missing brand-fit notes")
    if not normalize_space(str(lead.get("outreach_email", ""))):
        issues.append("missing draft email")
    if not normalize_space(str(lead.get("contact_email", ""))):
        issues.append("missing contact email")
    return {
        "ready_to_send": not issues,
        "needs_contact": "missing contact email" in issues,
        "needs_notes": "missing brand-fit notes" in issues,
        "needs_draft": "missing draft email" in issues,
        "issues": issues,
    }


def lead_contact_search_links(lead: dict[str, Any]) -> dict[str, str]:
    company = normalize_space(str(lead.get("company", "")))
    website = normalize_space(str(lead.get("website", "")))
    query = urllib.parse.quote(f"{company} founder owner marketing contact email linkedin")
    links = {
        "Google contact search": f"https://www.google.com/search?q={query}" if company else "",
        "LinkedIn people search": f"https://www.linkedin.com/search/results/people/?keywords={urllib.parse.quote(company)}" if company else "",
        "Company website": website,
    }
    if website:
        host = normalize_domain(website)
        if host:
            links["Google site search"] = f"https://www.google.com/search?q={urllib.parse.quote(company)}+site%3A{urllib.parse.quote(host)}"
    return {label: url for label, url in links.items() if url}


def write_outreach_documents(profile: dict[str, str], lead: dict[str, Any]) -> None:
    folder = outreach_documents_folder(lead)
    folder.mkdir(parents=True, exist_ok=True)
    email_body = normalize_space(str(lead.get("outreach_email", "")))
    if not email_body:
        email_body = compose_lead_outreach(profile, lead)
    parts = {
        "outreach-email.txt": email_body,
        "brand-fit-notes.txt": str(lead.get("company_notes", "") or "").strip(),
        "proposal-summary.txt": render_outreach_proposal_text(profile, lead),
        "contact-details.txt": "\n".join([
            f"Company: {lead.get('company', '')}",
            f"Website: {lead.get('website', '')}",
            f"Contact name: {lead.get('contact_name', '')}",
            f"Contact role: {lead.get('contact_role', '')}",
            f"Contact email: {lead.get('contact_email', '')}",
            f"Source URL: {lead.get('source_url', '')}",
        ]).strip(),
    }
    for filename, body in parts.items():
        (folder / filename).write_text(body + ("\n" if body and not body.endswith("\n") else ""), encoding="utf-8")
    (folder / "proposal-summary.rtf").write_text(render_outreach_proposal_rtf(profile, lead), encoding="utf-8")


def build_outreach_artifacts(lead: dict[str, Any]) -> dict[str, str]:
    folder = outreach_documents_folder(lead)
    artifact_files = {
        "outreach_email": folder / "outreach-email.txt",
        "brand_fit_notes": folder / "brand-fit-notes.txt",
        "proposal_summary": folder / "proposal-summary.txt",
        "proposal_rtf": folder / "proposal-summary.rtf",
        "contact_details": folder / "contact-details.txt",
    }
    artifacts: dict[str, str] = {}
    for key, artifact_path in artifact_files.items():
        if artifact_path.exists():
            artifacts[key] = str(artifact_path)
    return artifacts


def save_company_lead(conn: sqlite3.Connection, data: dict[str, Any]) -> int:
    fields = [
        "company",
        "website",
        "industry",
        "contact_name",
        "contact_role",
        "contact_email",
        "source_url",
        "company_notes",
        "contact_search_notes",
        "outreach_style",
        "status",
        "outreach_email",
        "next_follow_up",
    ]
    values = {field: normalize_space(str(data.get(field, ""))) for field in fields}
    values["status"] = values["status"] or "found"
    values["outreach_style"] = values["outreach_style"] or "intro"
    lead_id = int(data.get("id") or 0)
    timestamp = now_iso()
    if lead_id:
        assignments = ", ".join([f"{field}=?" for field in fields])
        conn.execute(
            f"update company_leads set {assignments}, updated_at=? where id=?",
            [values[field] for field in fields] + [timestamp, lead_id],
        )
        conn.commit()
        return lead_id
    cur = conn.execute(
        """
        insert into company_leads(company, website, industry, contact_name, contact_role,
                                  contact_email, source_url, company_notes, status,
                                  outreach_email, next_follow_up, created_at, updated_at)
        values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [values[field] for field in fields] + [timestamp, timestamp],
    )
    conn.commit()
    return int(cur.lastrowid)


def save_target_company(conn: sqlite3.Connection, data: dict[str, Any]) -> int:
    target_id = int(data.get("id") or 0)
    company = normalize_space(str(data.get("company", "")))
    website = normalize_space(str(data.get("website", "")))
    careers_url = normalize_space(str(data.get("careers_url", "")))
    industry = normalize_space(str(data.get("industry", "")))
    source_type = normalize_space(str(data.get("source_type", ""))).lower()
    source_token = normalize_space(str(data.get("source_token", "")))
    source_query = normalize_space(str(data.get("source_query", ""))) or "marketing"
    notes = normalize_space(str(data.get("notes", "")))
    status = normalize_space(str(data.get("status", ""))) or "target"
    try:
        priority = max(1, min(5, int(data.get("priority") or 3)))
    except ValueError:
        priority = 3
    if not company:
        company = company_from_url(website or careers_url)
    if not company:
        raise RuntimeError("Company name is required.")
    timestamp = now_iso()
    fields = [
        "company",
        "website",
        "careers_url",
        "industry",
        "priority",
        "source_type",
        "source_token",
        "source_query",
        "notes",
        "status",
    ]
    values = {
        "company": company,
        "website": website,
        "careers_url": careers_url,
        "industry": industry,
        "priority": priority,
        "source_type": source_type,
        "source_token": source_token,
        "source_query": source_query,
        "notes": notes,
        "status": status,
    }
    if target_id:
        assignments = ", ".join([f"{field}=?" for field in fields])
        conn.execute(
            f"update target_companies set {assignments}, updated_at=? where id=?",
            [values[field] for field in fields] + [timestamp, target_id],
        )
        conn.commit()
        return target_id
    existing = conn.execute(
        "select id from target_companies where lower(company)=lower(?) limit 1",
        (company,),
    ).fetchone()
    if existing:
        existing_id = int(existing["id"])
        assignments = ", ".join([f"{field}=?" for field in fields])
        conn.execute(
            f"update target_companies set {assignments}, updated_at=? where id=?",
            [values[field] for field in fields] + [timestamp, existing_id],
        )
        conn.commit()
        return existing_id
    cur = conn.execute(
        """
        insert into target_companies(company, website, careers_url, industry, priority,
                                     source_type, source_token, source_query, notes,
                                     status, created_at, updated_at)
        values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [values[field] for field in fields] + [timestamp, timestamp],
    )
    conn.commit()
    return int(cur.lastrowid)


def company_from_url(value: str) -> str:
    if not value:
        return ""
    parsed = urllib.parse.urlparse(value if "://" in value else f"https://{value}")
    host = parsed.netloc or parsed.path
    host = host.lower().removeprefix("www.")
    if not host:
        return ""
    return host.split(".")[0].replace("-", " ").title()


def normalize_domain(value: str) -> str:
    raw = normalize_space(value).lower()
    if not raw:
        return ""
    parsed = urllib.parse.urlparse(raw if "://" in raw else f"https://{raw}")
    host = (parsed.netloc or parsed.path or "").strip().lower()
    if "@" in host:
        host = host.split("@", 1)[-1]
    host = host.removeprefix("www.").strip("/")
    host = host.split(":", 1)[0]
    return host


def domain_variants_for_url(url: str) -> list[str]:
    host = normalize_domain(url)
    if not host:
        return []
    parts = host.split(".")
    variants = [host]
    generic_roots = {"co", "com", "org", "net", "ac", "gov"}
    for index in range(1, len(parts) - 1):
        candidate = ".".join(parts[index:])
        candidate_parts = candidate.split(".")
        if len(candidate_parts) < 2:
            continue
        if len(candidate_parts) == 2 and candidate_parts[0] in generic_roots:
            continue
        variants.append(candidate)
    unique: list[str] = []
    seen: set[str] = set()
    for item in variants:
        if item and item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def parse_iso_datetime(value: str) -> dt.datetime | None:
    text = normalize_space(value)
    if not text:
        return None
    try:
        parsed = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed


def cooldown_hours_for_platform(platform: str) -> int:
    key = normalize_space(platform).lower()
    return int(DOMAIN_RESTRICTION_COOLDOWN_HOURS.get(key, DOMAIN_RESTRICTION_COOLDOWN_HOURS["default"]))


def prep_rate_limit_minutes_for_platform(platform: str) -> int:
    key = normalize_space(platform).lower()
    return int(DOMAIN_PREP_RATE_LIMIT_MINUTES.get(key, DOMAIN_PREP_RATE_LIMIT_MINUTES["default"]))


def active_domain_blockers(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    now = dt.datetime.now(dt.timezone.utc)
    blockers: dict[str, dict[str, Any]] = {}
    rows = conn.execute(
        """
        select applications.id as application_id, applications.form_prep_report_path,
               applications.updated_at as application_updated_at,
               jobs.company, jobs.title, jobs.url, jobs.source
        from applications
        join jobs on jobs.id = applications.job_id
        where applications.form_prep_report_path != ''
        order by applications.updated_at desc
        """
    ).fetchall()
    for row in rows:
        app = row_to_dict(row) or {}
        url = str(app.get("url", ""))
        domain = normalize_domain(url)
        if not domain or domain in blockers:
            continue
        report = read_json_file(str(app.get("form_prep_report_path", "")))
        if not isinstance(report, dict):
            continue
        blocker = report.get("blocker") or {}
        if str(blocker.get("kind", "")) != "platform-restriction":
            continue
        blocked_until = parse_iso_datetime(str(blocker.get("blocked_until", "")))
        if not blocked_until or blocked_until <= now:
            continue
        platform = str(report.get("platform") or detect_application_platform(url, str(app.get("source", ""))))
        blockers[domain] = {
            "domain": domain,
            "platform": platform,
            "company": str(app.get("company", "")),
            "title": str(app.get("title", "")),
            "application_id": int(app.get("application_id") or 0),
            "url": url,
            "message": str(blocker.get("message", "")),
            "blocked_until": blocked_until.isoformat(),
            "cooldown_hours": cooldown_hours_for_platform(platform),
            "manual_first": platform in MANUAL_FIRST_PLATFORMS,
        }
    return list(blockers.values())


def active_domain_rate_limits(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    now = dt.datetime.now(dt.timezone.utc)
    limited: dict[str, dict[str, Any]] = {}
    rows = conn.execute(
        """
        select applications.id as application_id,
               applications.form_prep_started_at,
               applications.updated_at as application_updated_at,
               jobs.company, jobs.title, jobs.url, jobs.source
        from applications
        join jobs on jobs.id = applications.job_id
        where applications.form_prep_started_at != ''
        order by applications.form_prep_started_at desc, applications.updated_at desc
        """
    ).fetchall()
    for row in rows:
        app = row_to_dict(row) or {}
        url = str(app.get("url", ""))
        domain = normalize_domain(url)
        if not domain or domain in limited:
            continue
        started_at = parse_iso_datetime(str(app.get("form_prep_started_at", "")))
        if not started_at:
            continue
        platform = str(detect_application_platform(url, str(app.get("source", ""))))
        window_minutes = prep_rate_limit_minutes_for_platform(platform)
        next_allowed = started_at + dt.timedelta(minutes=window_minutes)
        if next_allowed <= now:
            continue
        limited[domain] = {
            "domain": domain,
            "platform": platform,
            "company": str(app.get("company", "")),
            "title": str(app.get("title", "")),
            "application_id": int(app.get("application_id") or 0),
            "url": url,
            "message": f"Recent form preparation attempt detected. Wait before trying {domain} again.",
            "started_at": started_at.isoformat(),
            "next_allowed_at": next_allowed.isoformat(),
            "window_minutes": window_minutes,
            "manual_first": platform in MANUAL_FIRST_PLATFORMS,
        }
    return list(limited.values())


def ats_prep_stats(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = {}
    rows = conn.execute(
        """
        select applications.id as application_id,
               applications.status as application_status,
               applications.form_prep_started_at,
               applications.form_prep_report_path,
               jobs.url, jobs.source
        from applications
        join jobs on jobs.id = applications.job_id
        order by applications.updated_at desc
        """
    ).fetchall()
    for row in rows:
        item = row_to_dict(row) or {}
        platform = detect_application_platform(str(item.get("url", "")), str(item.get("source", ""))) or "custom"
        bucket = stats.setdefault(
            platform,
            {
                "platform": platform,
                "applications": 0,
                "started": 0,
                "reports": 0,
                "completed": 0,
                "waiting": 0,
                "restrictions": 0,
                "manual_prompts": 0,
                "errors": 0,
                "fields_seen": 0,
                "fields_filled": 0,
                "submitted": 0,
            },
        )
        bucket["applications"] += 1
        if str(item.get("application_status", "")) in {"submitted", "interview", "offer"}:
            bucket["submitted"] += 1
        if str(item.get("form_prep_started_at", "")):
            bucket["started"] += 1
        report = read_json_file(str(item.get("form_prep_report_path", "")))
        if not isinstance(report, dict):
            continue
        bucket["reports"] += 1
        status = str(report.get("status", ""))
        if status == "completed":
            bucket["completed"] += 1
        elif status == "waiting-user-action":
            bucket["waiting"] += 1
        blocker = report.get("blocker") or {}
        blocker_kind = str(blocker.get("kind", ""))
        if blocker_kind == "platform-restriction":
            bucket["restrictions"] += 1
        elif blocker_kind:
            bucket["manual_prompts"] += 1
        bucket["errors"] += len(report.get("errors") or [])
        bucket["fields_seen"] += int(report.get("field_count") or 0)
        bucket["fields_filled"] += len(report.get("filled_fields") or [])
    for bucket in stats.values():
        reports = max(1, int(bucket["reports"]))
        fields_seen = max(1, int(bucket["fields_seen"]))
        bucket["completion_rate"] = round((int(bucket["completed"]) / reports) * 100)
        bucket["fill_rate"] = min(100, round((int(bucket["fields_filled"]) / fields_seen) * 100))
    return sorted(
        stats.values(),
        key=lambda item: (
            -int(item.get("completion_rate", 0)),
            -int(item.get("fill_rate", 0)),
            -int(item.get("reports", 0)),
            str(item.get("platform", "")),
        ),
    )


def rejection_reason_stats(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        select reject_reason, count(*) as count
        from applications
        where reject_reason != ''
        group by reject_reason
        order by count desc, reject_reason asc
        """
    ).fetchall()
    return [{"reason": str(row["reject_reason"]), "count": int(row["count"])} for row in rows]


def active_domain_blocker_for_url(conn: sqlite3.Connection, url: str) -> dict[str, Any] | None:
    variants = domain_variants_for_url(url)
    if not variants:
        return None
    for blocker in active_domain_blockers(conn):
        domain = normalize_domain(str(blocker.get("domain", "")))
        for variant in variants:
            if domain and (variant == domain or variant.endswith(f".{domain}") or domain.endswith(f".{variant}")):
                return blocker
    return None


def active_domain_rate_limit_for_url(conn: sqlite3.Connection, url: str) -> dict[str, Any] | None:
    variants = domain_variants_for_url(url)
    if not variants:
        return None
    for limited in active_domain_rate_limits(conn):
        domain = normalize_domain(str(limited.get("domain", "")))
        for variant in variants:
            if domain and (variant == domain or variant.endswith(f".{domain}") or domain.endswith(f".{variant}")):
                return limited
    return None


def keychain_service_name(domain: str) -> str:
    normalized = normalize_domain(domain)
    if not normalized:
        raise RuntimeError("A site credential domain is required.")
    return f"JobApplicationAI:{normalized}"


def run_security_command(args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    if not shutil.which("security"):
        raise RuntimeError("macOS Keychain access is not available on this machine.")
    result = subprocess.run(
        ["security", *args],
        capture_output=True,
        text=True,
        timeout=12,
    )
    if check and result.returncode != 0:
        stderr = normalize_space(result.stderr or result.stdout or "Keychain command failed.")
        raise RuntimeError(stderr)
    return result


def save_keychain_password(domain: str, username: str, password: str) -> None:
    if not password:
        return
    service = keychain_service_name(domain)
    user = normalize_space(username)
    if not user:
        raise RuntimeError("A username is required before saving a Keychain password.")
    run_security_command(
        [
            "add-generic-password",
            "-a",
            user,
            "-s",
            service,
            "-w",
            password,
            "-U",
        ]
    )


def read_keychain_password(domain: str, username: str) -> str:
    service = keychain_service_name(domain)
    user = normalize_space(username)
    if not user:
        return ""
    result = run_security_command(
        [
            "find-generic-password",
            "-a",
            user,
            "-s",
            service,
            "-w",
        ],
        check=False,
    )
    if result.returncode != 0:
        return ""
    return (result.stdout or "").strip()


def delete_keychain_password(domain: str, username: str) -> None:
    service = keychain_service_name(domain)
    user = normalize_space(username)
    if not user:
        return
    run_security_command(
        [
            "delete-generic-password",
            "-a",
            user,
            "-s",
            service,
        ],
        check=False,
    )


def password_is_saved_for_credential(credential: dict[str, Any]) -> bool:
    if not credential:
        return False
    try:
        return bool(read_keychain_password(str(credential.get("domain", "")), str(credential.get("username", ""))))
    except Exception:
        return False


def save_site_credential(conn: sqlite3.Connection, payload: dict[str, Any]) -> int:
    timestamp = now_iso()
    domain = normalize_domain(str(payload.get("domain") or payload.get("login_url") or payload.get("job_url") or ""))
    if not domain:
        raise RuntimeError("A site credential needs a domain or login URL.")
    login_url = normalize_space(str(payload.get("login_url", "")))
    username = normalize_space(str(payload.get("username", "")))
    notes = normalize_space(str(payload.get("notes", "")))
    enabled = 1 if payload.get("enabled", True) else 0
    password = str(payload.get("password", ""))
    credential_id = int(payload.get("id") or 0)
    existing = conn.execute("select * from site_credentials where domain=? limit 1", (domain,)).fetchone()
    if existing and credential_id and int(existing["id"]) != credential_id:
        raise RuntimeError("That domain already has saved credentials. Edit the existing row instead.")
    if credential_id:
        current = conn.execute("select * from site_credentials where id=?", (credential_id,)).fetchone()
        if not current:
            raise RuntimeError("Site credential not found.")
        current_dict = row_to_dict(current) or {}
        old_domain = str(current_dict.get("domain", ""))
        old_username = str(current_dict.get("username", ""))
        conn.execute(
            """
            update site_credentials
            set domain=?, login_url=?, username=?, notes=?, enabled=?, updated_at=?
            where id=?
            """,
            (domain, login_url, username, notes, enabled, timestamp, credential_id),
        )
        if password:
            save_keychain_password(domain, username, password)
            if (old_domain, old_username) != (domain, username):
                delete_keychain_password(old_domain, old_username)
        elif (old_domain, old_username) != (domain, username):
            old_password = read_keychain_password(old_domain, old_username)
            if old_password and username:
                save_keychain_password(domain, username, old_password)
            delete_keychain_password(old_domain, old_username)
        conn.commit()
        return credential_id

    if existing:
        credential_id = int(existing["id"])
        conn.execute(
            """
            update site_credentials
            set login_url=?, username=?, notes=?, enabled=?, updated_at=?
            where id=?
            """,
            (login_url, username, notes, enabled, timestamp, credential_id),
        )
        if password:
            save_keychain_password(domain, username, password)
        conn.commit()
        return credential_id

    cur = conn.execute(
        """
        insert into site_credentials(domain, login_url, username, notes, enabled, created_at, updated_at)
        values(?, ?, ?, ?, ?, ?, ?)
        """,
        (domain, login_url, username, notes, enabled, timestamp, timestamp),
    )
    credential_id = int(cur.lastrowid)
    if password:
        save_keychain_password(domain, username, password)
    conn.commit()
    return credential_id


def delete_site_credential(conn: sqlite3.Connection, credential_id: int) -> None:
    row = conn.execute("select * from site_credentials where id=?", (credential_id,)).fetchone()
    if not row:
        raise RuntimeError("Site credential not found.")
    credential = row_to_dict(row) or {}
    conn.execute("delete from site_credentials where id=?", (credential_id,))
    conn.commit()
    delete_keychain_password(str(credential.get("domain", "")), str(credential.get("username", "")))


def find_site_credential_for_url(conn: sqlite3.Connection, url: str) -> dict[str, Any] | None:
    variants = domain_variants_for_url(url)
    if not variants:
        return None
    rows = [
        row_to_dict(row) or {}
        for row in conn.execute(
            "select * from site_credentials where enabled=1 order by length(domain) desc, updated_at desc"
        ).fetchall()
    ]
    for variant in variants:
        for row in rows:
            domain = normalize_domain(str(row.get("domain", "")))
            if domain and (variant == domain or variant.endswith(f".{domain}")):
                row["password_set"] = password_is_saved_for_credential(row)
                row["keychain_service"] = keychain_service_name(domain)
                return row
    return None


def read_json_file(path_value: str) -> Any:
    path_text = normalize_space(path_value)
    if not path_text:
        return None
    path = Path(path_text)
    if not path.exists() or not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def form_prep_report_for_app(application: dict[str, Any]) -> dict[str, Any] | None:
    report = read_json_file(str(application.get("form_prep_report_path", "")))
    if not isinstance(report, dict):
        return None
    return report


def parse_form_prep_overrides(raw: str) -> dict[str, str]:
    text = str(raw or "").strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    result: dict[str, str] = {}
    for key, value in payload.items():
        clean_key = normalize_space(str(key))
        if not clean_key:
            continue
        result[clean_key] = str(value or "")
    return result


def import_target_companies(conn: sqlite3.Connection, text: str) -> dict[str, Any]:
    ids: list[int] = []
    skipped: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [part.strip() for part in line.split("|")]
        if not parts[0]:
            skipped.append(line)
            continue
        payload = {
            "company": parts[0],
            "website": parts[1] if len(parts) > 1 else "",
            "industry": parts[2] if len(parts) > 2 else "",
            "careers_url": parts[3] if len(parts) > 3 else "",
            "notes": parts[4] if len(parts) > 4 else "",
            "priority": 3,
            "source_query": "marketing",
        }
        ids.append(save_target_company(conn, payload))
    return {"count": len(ids), "ids": ids, "skipped": skipped}


def seed_starter_targets(conn: sqlite3.Connection) -> dict[str, Any]:
    ids: list[int] = []
    for target in STARTER_TARGET_COMPANIES:
        payload = {
            "company": target.get("company", ""),
            "website": target.get("website", ""),
            "careers_url": target.get("careers_url", ""),
            "industry": target.get("industry", ""),
            "priority": target.get("priority", 3),
            "source_type": target.get("source_type", ""),
            "source_token": target.get("source_token", ""),
            "source_query": target.get("source_query", "marketing"),
            "notes": target.get("notes", ""),
            "status": "target",
        }
        ids.append(save_target_company(conn, payload))
    return {"count": len(ids), "ids": ids}


def target_company_to_source(conn: sqlite3.Connection, target_id: int) -> dict[str, Any]:
    target = row_to_dict(conn.execute("select * from target_companies where id=?", (target_id,)).fetchone())
    if not target:
        raise RuntimeError("Target company not found.")
    source_type = str(target.get("source_type", "")).lower()
    token = str(target.get("source_token", ""))
    if not source_type:
        source_type = "url"
    if not token:
        if source_type == "url":
            token = str(target.get("careers_url") or target.get("website") or "")
        else:
            raise RuntimeError("Add the ATS source token before creating this source.")
    if not token:
        raise RuntimeError("Add a careers URL, website, or ATS token before creating this source.")
    source_id = save_job_source(
        conn,
        {
            "name": f"{target.get('company')} careers",
            "source_type": source_type,
            "token": token,
            "query": target.get("source_query") or "marketing",
            "enabled": True,
        },
    )
    conn.execute(
        "update target_companies set source_id=?, status='sourcing', updated_at=? where id=?",
        (source_id, now_iso(), target_id),
    )
    conn.commit()
    return {"source_id": source_id}


def target_company_to_lead(conn: sqlite3.Connection, target_id: int) -> dict[str, Any]:
    target = row_to_dict(conn.execute("select * from target_companies where id=?", (target_id,)).fetchone())
    if not target:
        raise RuntimeError("Target company not found.")
    lead_id = int(target.get("lead_id") or 0)
    notes = str(target.get("notes", ""))
    if not notes:
        notes = f"Target company for Phillip's marketing search. Industry: {target.get('industry') or 'not specified'}."
    payload = {
        "id": lead_id,
        "company": target.get("company", ""),
        "website": target.get("website", ""),
        "industry": target.get("industry", ""),
        "source_url": target.get("website") or target.get("careers_url") or "",
        "company_notes": notes,
        "contact_search_notes": "Start with founder/owner/marketing lead search, then confirm the best public work email before sending.",
        "outreach_style": "intro",
        "status": "found",
    }
    lead_id = save_company_lead(conn, payload)
    conn.execute(
        "update target_companies set lead_id=?, status='outreach-ready', updated_at=? where id=?",
        (lead_id, now_iso(), target_id),
    )
    conn.commit()
    return {"lead_id": lead_id}


def read_session_memory() -> str:
    if not SESSION_MEMORY_PATH.exists():
        return ""
    return SESSION_MEMORY_PATH.read_text(encoding="utf-8")


def write_session_memory(content: str) -> None:
    SESSION_MEMORY_PATH.write_text(content.rstrip() + "\n", encoding="utf-8")


def generate_session_memory_draft(existing: str) -> str:
    state = get_state()
    jobs = state.get("jobs", [])
    apps = state.get("applications", [])
    sources = state.get("sources", [])
    leads = state.get("leads", [])
    targets = state.get("targets", [])
    source_errors = []
    for source in sources:
        last_result = str(source.get("last_result") or "")
        if "error" in last_result.lower():
            source_errors.append(f"{source.get('name') or source.get('token')}: {last_result[:220]}")
    latest_apps = apps[:5]
    note = [
        f"## Session Note - {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "### Current App Snapshot",
        "",
        f"- Jobs tracked: {len(jobs)}.",
        f"- Application drafts/tracked applications: {len(apps)}.",
        f"- Automatic sources: {len(sources)} total, {sum(1 for source in sources if source.get('enabled'))} enabled.",
        f"- Target companies: {len(targets)}.",
        f"- Outreach leads: {len(leads)}.",
        f"- Email configured: {'yes' if state.get('email', {}).get('password_set') else 'settings saved, password not confirmed'}; secrets are stored only in `.env`.",
        "",
        "### Latest Application Drafts",
        "",
    ]
    if latest_apps:
        for app in latest_apps:
            note.append(f"- {app.get('company') or 'Unknown'} - {app.get('title') or 'Unknown'} ({app.get('status') or 'draft'}).")
    else:
        note.append("- No application drafts currently tracked.")
    note.extend(["", "### Source Issues", ""])
    if source_errors:
        note.extend(f"- {error}" for error in source_errors[:8])
    else:
        note.append("- No source errors visible in the current app state.")
    note.extend(
        [
            "",
            "### Next Recommended Actions",
            "",
            "1. Add 20-50 target companies in the Targets tab, then convert their careers pages into enabled sources.",
            "2. Run the daily workflow and review the generated drafts before opening form preparation.",
            "3. Use Prepare form on one draft, check which fields filled correctly, then improve mappings based on the result.",
            "4. Add contact names/emails and personalization notes before sending follow-ups or outreach.",
            "",
            "### Files Changed In This Session",
            "",
            "- Update this list before saving if code or docs changed outside the app.",
        ]
    )
    base = existing.rstrip() or "# Session Memory\n"
    return base + "\n\n" + "\n".join(note) + "\n"


def send_smtp_message(to_address: str, subject: str, body: str) -> None:
    env = load_local_env()
    host = env.get("JOB_AI_SMTP_HOST", "")
    port = int(env.get("JOB_AI_SMTP_PORT", "587"))
    user = env.get("JOB_AI_SMTP_USER", "")
    password = env.get("JOB_AI_SMTP_PASSWORD", "")
    from_address = env.get("JOB_AI_SMTP_FROM", user)
    starttls = env.get("JOB_AI_SMTP_STARTTLS", "1").lower() in {"1", "true", "yes", "on"}
    if not host or not user or not password or not from_address:
        raise RuntimeError("Email is not configured. Add SMTP settings and password first.")
    if not to_address or "@" not in to_address:
        raise RuntimeError("A valid recipient email address is required.")

    message = EmailMessage()
    message["From"] = from_address
    message["To"] = to_address
    message["Subject"] = subject
    message.set_content(body)

    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=25) as smtp:
            smtp.login(user, password)
            smtp.send_message(message)
    else:
        with smtplib.SMTP(host, port, timeout=25) as smtp:
            smtp.ehlo()
            if starttls:
                smtp.starttls()
                smtp.ehlo()
            smtp.login(user, password)
            smtp.send_message(message)


def scan_inbox_for_replies(limit: int = 80) -> dict[str, Any]:
    env = load_local_env()
    host = env.get("JOB_AI_IMAP_HOST", "")
    port = int(env.get("JOB_AI_IMAP_PORT", "993") or "993")
    user = env.get("JOB_AI_IMAP_USER", "")
    password = env.get("JOB_AI_IMAP_PASSWORD", "")
    mailbox = env.get("JOB_AI_IMAP_MAILBOX", "INBOX") or "INBOX"
    use_ssl = env.get("JOB_AI_IMAP_SSL", "1").lower() in {"1", "true", "yes", "on"}
    lookback_days = max(1, min(365, int(env.get("JOB_AI_IMAP_LOOKBACK_DAYS", "45") or "45")))
    if not host or not user or not password:
        raise RuntimeError("Inbox tracking is not configured. Add IMAP settings and password first.")

    since = dt.date.today() - dt.timedelta(days=lookback_days)
    since_text = since.strftime("%d-%b-%Y")
    imported = 0
    matched = 0
    scanned = 0
    with connect() as conn:
        if use_ssl:
            imap: imaplib.IMAP4 = imaplib.IMAP4_SSL(host, port)
        else:
            imap = imaplib.IMAP4(host, port)
        try:
            imap.login(user, password)
            typ, _ = imap.select(mailbox, readonly=True)
            if typ != "OK":
                raise RuntimeError(f"Could not open IMAP mailbox {mailbox}.")
            typ, data = imap.uid("search", None, "SINCE", since_text)
            if typ != "OK":
                raise RuntimeError("IMAP search failed.")
            uids = (data[0] or b"").split()
            for uid in uids[-limit:]:
                scanned += 1
                uid_text = uid.decode("ascii", errors="replace")
                message_uid = f"{host}:{mailbox}:{uid_text}"
                if conn.execute("select 1 from inbox_messages where message_uid=?", (message_uid,)).fetchone():
                    continue
                typ, msg_data = imap.uid("fetch", uid, "(RFC822)")
                if typ != "OK" or not msg_data:
                    continue
                raw = next((part[1] for part in msg_data if isinstance(part, tuple) and len(part) > 1), b"")
                if not raw:
                    continue
                parsed = parse_inbox_message(raw)
                if parsed["from_email"].lower() == user.lower():
                    continue
                match = match_inbox_message(conn, parsed["from_email"], parsed["subject"], parsed["snippet"])
                classification = classify_inbox_reply(parsed["from_email"], parsed["subject"], parsed["snippet"])
                save_inbox_message(conn, message_uid, mailbox, parsed, match, classification)
                imported += 1
                if match.get("confidence", 0) >= 40:
                    matched += 1
        finally:
            try:
                imap.close()
            except Exception:
                pass
            try:
                imap.logout()
            except Exception:
                pass
    return {"scanned": scanned, "imported": imported, "matched": matched, "mailbox": mailbox, "lookback_days": lookback_days}


def parse_inbox_message(raw: bytes) -> dict[str, str]:
    msg = BytesParser(policy=policy.default).parsebytes(raw)
    from_name, from_email = parseaddr(str(msg.get("From", "")))
    subject = normalize_space(str(msg.get("Subject", "")))
    received_at = ""
    if msg.get("Date"):
        try:
            received_at = parsedate_to_datetime(str(msg.get("Date"))).astimezone(dt.UTC).replace(microsecond=0).isoformat()
        except Exception:
            received_at = ""
    body = extract_email_text(msg)
    headers = "\n".join(f"{key}: {msg.get(key, '')}" for key in ["From", "To", "Subject", "Date", "Message-ID"])
    return {
        "from_name": normalize_space(from_name),
        "from_email": normalize_space(from_email),
        "subject": subject,
        "snippet": normalize_space(body)[:1200],
        "received_at": received_at or now_iso(),
        "raw_headers": headers[:2000],
    }


def extract_email_text(msg: Any) -> str:
    if msg.is_multipart():
        plain_parts = []
        html_parts = []
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get_content_disposition() or "")
            if disposition == "attachment":
                continue
            try:
                content = part.get_content()
            except Exception:
                continue
            if content_type == "text/plain":
                plain_parts.append(str(content))
            elif content_type == "text/html":
                html_parts.append(plain_text_from_html(str(content)))
        return "\n".join(plain_parts or html_parts)
    try:
        content = msg.get_content()
    except Exception:
        return ""
    if msg.get_content_type() == "text/html":
        return plain_text_from_html(str(content))
    return str(content)


def match_inbox_message(conn: sqlite3.Connection, from_email: str, subject: str, snippet: str) -> dict[str, Any]:
    text = f"{from_email} {subject} {snippet}".lower()
    from_domain = email_domain(from_email)
    best = {"matched_type": "", "application_id": 0, "lead_id": 0, "confidence": 0}
    app_rows = conn.execute(
        """
        select applications.*, jobs.company, jobs.title
        from applications
        join jobs on jobs.id = applications.job_id
        where applications.status in ('submitted', 'interview', 'offer', 'draft')
        """
    ).fetchall()
    for row in app_rows:
        app = row_to_dict(row) or {}
        score = match_score_for_record(app, from_email, from_domain, text)
        if score > best["confidence"]:
            best = {"matched_type": "application", "application_id": int(app["id"]), "lead_id": 0, "confidence": score}
    lead_rows = conn.execute("select * from company_leads where status in ('sent', 'follow_up_due', 'found', 'draft')").fetchall()
    for row in lead_rows:
        lead = row_to_dict(row) or {}
        score = match_score_for_record(lead, from_email, from_domain, text)
        if score > best["confidence"]:
            best = {"matched_type": "outreach", "application_id": 0, "lead_id": int(lead["id"]), "confidence": score}
    if best["confidence"] < 35:
        return {"matched_type": "", "application_id": 0, "lead_id": 0, "confidence": best["confidence"]}
    return best


def match_score_for_record(record: dict[str, Any], from_email: str, from_domain: str, text: str) -> int:
    score = 0
    contact_email = str(record.get("contact_email", "")).lower()
    company = normalize_space(str(record.get("company", ""))).lower()
    title = normalize_space(str(record.get("title", ""))).lower()
    if contact_email and from_email.lower() == contact_email:
        score += 85
    if contact_email and from_domain and email_domain(contact_email) == from_domain:
        score += 45
    if company and len(company) > 2 and company in text:
        score += 35
    if title:
        title_terms = [term for term in re.split(r"[^a-z0-9]+", title) if len(term) > 3]
        score += min(20, sum(5 for term in title_terms if term in text))
    return min(score, 100)


def email_domain(address: str) -> str:
    if "@" not in address:
        return ""
    return address.rsplit("@", 1)[1].lower()


def classify_inbox_reply(from_email: str, subject: str, snippet: str) -> dict[str, Any]:
    text = f"{from_email} {subject} {snippet}".lower()
    if any(term in from_email.lower() for term in ["no-reply", "noreply", "donotreply"]):
        return {"classification": "auto_reply", "confidence": 70}
    if any(term in text for term in ["unfortunately", "not be proceeding", "not proceed", "not selected", "unsuccessful", "other candidates", "regret to inform"]):
        return {"classification": "rejection", "confidence": 85}
    if any(term in text for term in ["interview", "schedule a call", "book a call", "availability", "next step", "shortlisted", "meet with", "calendar", "assessment"]):
        return {"classification": "interview", "confidence": 85}
    if any(term in text for term in ["received your application", "application has been received", "thank you for applying", "thanks for applying"]):
        return {"classification": "auto_reply", "confidence": 65}
    if re.search(r"\bre:\s*", subject, re.I) or any(term in text for term in ["thanks phillip", "hi phillip", "dear phillip"]):
        return {"classification": "reply", "confidence": 55}
    return {"classification": "unknown", "confidence": 20}


def save_inbox_message(
    conn: sqlite3.Connection,
    message_uid: str,
    mailbox: str,
    parsed: dict[str, str],
    match: dict[str, Any],
    classification: dict[str, Any],
) -> int:
    timestamp = now_iso()
    existing = conn.execute("select id from inbox_messages where message_uid=?", (message_uid,)).fetchone()
    values = (
        mailbox,
        parsed["from_email"],
        parsed["from_name"],
        parsed["subject"],
        parsed["snippet"],
        parsed["received_at"],
        match.get("matched_type", ""),
        int(match.get("application_id", 0) or 0),
        int(match.get("lead_id", 0) or 0),
        classification.get("classification", "unknown"),
        max(int(match.get("confidence", 0) or 0), int(classification.get("confidence", 0) or 0)),
        parsed.get("raw_headers", ""),
        timestamp,
    )
    if existing:
        conn.execute(
            """
            update inbox_messages
            set mailbox=?, from_email=?, from_name=?, subject=?, snippet=?, received_at=?,
                matched_type=?, application_id=?, lead_id=?, classification=?, confidence=?,
                raw_headers=?, updated_at=?
            where id=?
            """,
            values + (int(existing["id"]),),
        )
        conn.commit()
        return int(existing["id"])
    cur = conn.execute(
        """
        insert into inbox_messages(message_uid, mailbox, from_email, from_name, subject, snippet,
                                   received_at, matched_type, application_id, lead_id, classification,
                                   confidence, status, raw_headers, created_at, updated_at)
        values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?, ?, ?)
        """,
        (
            message_uid,
            *values,
            timestamp,
        ),
    )
    conn.commit()
    return int(cur.lastrowid or 0)


def subject_from_follow_up(app: dict[str, Any]) -> str:
    return f"Follow-up on {app.get('title') or 'application'} application"


def ensure_application(conn: sqlite3.Connection, job_id: int) -> int:
    existing = conn.execute("select id from applications where job_id = ?", (job_id,)).fetchone()
    if existing:
        return int(existing["id"])
    timestamp = now_iso()
    cur = conn.execute(
        """
        insert into applications(job_id, status, created_at, updated_at)
        values(?, 'draft', ?, ?)
        """,
        (job_id, timestamp, timestamp),
    )
    conn.commit()
    return int(cur.lastrowid)


def generate_application(conn: sqlite3.Connection, job_id: int, batch_id: str = "") -> int:
    profile = get_profile(conn)
    job = row_to_dict(conn.execute("select * from jobs where id = ?", (job_id,)).fetchone())
    if not job:
        raise RuntimeError("Job not found")
    app_id = ensure_application(conn, job_id)
    existing_app = row_to_dict(conn.execute("select * from applications where id=?", (app_id,)).fetchone()) or {}
    research_notes, research_sources, research_url = generate_application_research(job, existing_app, existing_app.get("research_url", ""))
    cover = generate_cover_letter(profile, job)
    cv_notes = generate_cv_notes(profile, job)
    answers = generate_answers(profile, job)
    follow = compose_follow_up(profile, job, existing_app)
    next_follow_up = (dt.date.today() + dt.timedelta(days=7)).isoformat()
    timestamp = now_iso()
    conn.execute(
        """
        update applications
        set cover_letter=?, cv_notes=?, answers=?, follow_up=?, research_notes=?,
            research_sources=?, research_url=?, next_follow_up=?, batch_id=?,
            queue_state=case when queue_state='' then 'review' else queue_state end,
            updated_at=?
        where id=?
        """,
        (
            cover,
            cv_notes,
            answers,
            follow,
            research_notes,
            research_sources,
            research_url,
            next_follow_up,
            batch_id or timestamp,
            timestamp,
            app_id,
        ),
    )
    conn.execute(
        """
        update jobs
        set status=case when status='new' then 'drafted' else status end, updated_at=?
        where id=? and status in ('new', 'shortlisted')
        """,
        (timestamp, job_id),
    )
    conn.execute(
        "insert into events(application_id, kind, body, created_at) values(?, 'generated', 'Generated application draft.', ?)",
        (app_id, timestamp),
    )
    conn.commit()
    write_application_documents(job, row_to_dict(conn.execute("select * from applications where id=?", (app_id,)).fetchone()) or {})
    return app_id


def safe_filename(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    return value.strip("-")[:120] or "application"


def application_documents_folder(job: dict[str, Any]) -> Path:
    return DOCS_DIR / f"{safe_filename(str(job.get('company', 'company')))}-{safe_filename(str(job.get('title', 'role')))}-{job.get('id')}"


def rtf_escape(value: str) -> str:
    text = str(value or "")
    text = text.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.replace("\n", r"\par" + "\n")


def render_cover_letter_rtf(job: dict[str, Any], application: dict[str, Any]) -> str:
    title = normalize_space(str(job.get("title", ""))) or "Role"
    company = normalize_space(str(job.get("company", ""))) or "Company"
    body = str(application.get("cover_letter", "") or "").strip()
    return (
        "{\\rtf1\\ansi\\deff0\n"
        "{\\fonttbl{\\f0 Arial;}}\n"
        "\\fs24\n"
        f"Phillip de Nobrega\\par\n"
        f"Application for {rtf_escape(title)} at {rtf_escape(company)}\\par\n"
        "\\par\n"
        f"{rtf_escape(body)}\n"
        "}\n"
    )


def render_supporting_statement_text(job: dict[str, Any], application: dict[str, Any]) -> str:
    title = normalize_space(str(job.get("title", ""))) or "the role"
    company = normalize_space(str(job.get("company", ""))) or "the company"
    cover = normalize_space(str(application.get("cover_letter", "") or ""))
    answers = normalize_space(str(application.get("answers", "") or ""))
    research = normalize_space(str(application.get("research_notes", "") or ""))
    parts = [
        f"Supporting Statement for {title} at {company}",
        "",
        cover,
    ]
    if answers:
        parts.extend(["", "Additional application context:", answers])
    if research:
        parts.extend(["", "Company-specific focus:", research])
    return "\n".join(part for part in parts if part is not None).strip()


def render_supporting_statement_rtf(job: dict[str, Any], application: dict[str, Any]) -> str:
    body = render_supporting_statement_text(job, application)
    return (
        "{\\rtf1\\ansi\\deff0\n"
        "{\\fonttbl{\\f0 Arial;}}\n"
        "\\fs24\n"
        f"{rtf_escape(body)}\n"
        "}\n"
    )


def build_application_artifacts(job: dict[str, Any], application: dict[str, Any], profile: dict[str, Any]) -> dict[str, str]:
    folder = application_documents_folder(job)
    artifacts: dict[str, str] = {}
    cv_path = str(profile.get("cv_path", "") or "").strip()
    headshot_path = str(profile.get("headshot_path", "") or "").strip()
    if cv_path:
        artifacts["cv_upload"] = cv_path
        artifacts["resume"] = cv_path
    if headshot_path:
        artifacts["headshot"] = headshot_path
        artifacts["photo"] = headshot_path
    artifact_files = {
        "cover_letter": folder / "cover-letter.rtf",
        "motivation_letter": folder / "cover-letter.rtf",
        "supporting_statement": folder / "supporting-statement.rtf",
        "personal_statement": folder / "supporting-statement.rtf",
        "questionnaire_answers": folder / "questionnaire-answers.txt",
        "additional_information": folder / "questionnaire-answers.txt",
        "company_research": folder / "company-research.txt",
        "application_pack": folder / "application-pack.html",
        "tailored_cv_brief": folder / "tailored-cv-brief.html",
    }
    for key, artifact_path in artifact_files.items():
        if artifact_path.exists():
            artifacts[key] = str(artifact_path)
    return artifacts


def write_application_documents(job: dict[str, Any], application: dict[str, Any]) -> None:
    folder = application_documents_folder(job)
    folder.mkdir(parents=True, exist_ok=True)
    tailored_cv = render_tailored_cv_text(job, application)
    parts = {
        "cover-letter.txt": application.get("cover_letter", ""),
        "cv-tailoring-notes.txt": application.get("cv_notes", ""),
        "tailored-cv-brief.txt": tailored_cv,
        "questionnaire-answers.txt": application.get("answers", ""),
        "company-research.txt": "\n\n".join(
            part for part in [application.get("research_notes", ""), application.get("research_sources", "")]
            if part
        ),
        "follow-up-email.txt": application.get("follow_up", ""),
    }
    for filename, body in parts.items():
        (folder / filename).write_text(body, encoding="utf-8")
    (folder / "cover-letter.rtf").write_text(render_cover_letter_rtf(job, application), encoding="utf-8")
    (folder / "supporting-statement.rtf").write_text(render_supporting_statement_rtf(job, application), encoding="utf-8")
    html_doc = render_printable_application(job, application)
    (folder / "application-pack.html").write_text(html_doc, encoding="utf-8")
    (folder / "tailored-cv-brief.html").write_text(render_tailored_cv_html(job, application, tailored_cv), encoding="utf-8")


def render_tailored_cv_text(job: dict[str, Any], application: dict[str, Any]) -> str:
    title = normalize_space(str(job.get("title", ""))) or "the role"
    company = normalize_space(str(job.get("company", ""))) or "the company"
    recommended = normalize_space(str(application.get("recommended_cv_version", ""))) or recommend_cv_version(None, job)
    keywords = cv_keywords_for_job(job)
    bullets = tailored_cv_bullets(job)
    summary = tailored_cv_summary(job, recommended)
    lines = [
        "Tailored CV Brief",
        f"Role: {title}",
        f"Company: {company}",
        f"Recommended CV version: {recommended}",
        "",
        "Profile summary to use near the top:",
        summary,
        "",
        "Keywords to mirror truthfully:",
        ", ".join(keywords) if keywords else "marketing, brand, content, research, analytics",
        "",
        "Evidence bullets to prioritise:",
        *[f"- {bullet}" for bullet in bullets],
        "",
        "Truth rules:",
        "- Do not invent years of experience, budgets, platforms, or work authorization.",
        "- Keep Phillip's start date and trial/project availability accurate.",
        "- Keep the original CV facts intact; only reorder, summarise, and emphasise relevant evidence.",
    ]
    return "\n".join(lines).strip()


def tailored_cv_summary(job: dict[str, Any], recommended: str) -> str:
    company = normalize_space(str(job.get("company", ""))) or "the company"
    if "Sports and fitness" in recommended:
        return f"UCT Business Science Marketing graduate based in Cape Town, with hands-on content, research, and analytics experience, plus a strong personal connection to sport through coaching and Ironman 70.3 training. Interested in helping {company} with practical brand, content, community, and campaign work."
    if "Content" in recommended:
        return f"Marketing graduate with practical social content experience, including Canva design, captions, product photography, short-form video, scheduling, and engagement reporting. Strong fit for content, brand, and community-focused marketing work at {company}."
    if "Research" in recommended:
        return f"Marketing graduate with research and analytics experience, including a UCT thesis on VR/AR adoption, market research consulting, Google Analytics certification, and survey/design thinking. Strong fit for insight-led marketing work at {company}."
    if "Startup" in recommended:
        return f"Marketing graduate with startup/project exposure, AI-assisted product development experience, and a practical approach to testing, learning, and improving marketing work. Interested in supporting growth and brand execution at {company}."
    return f"UCT Business Science Marketing graduate based in Cape Town, with experience across content creation, market research, Google Analytics, brand strategy, and sport-focused leadership. Interested in practical, measurable marketing work at {company}."


def tailored_cv_bullets(job: dict[str, Any]) -> list[str]:
    text = f"{job.get('title', '')} {job.get('description', '')}".lower()
    bullets = [
        "UCT Business Science Marketing graduate with 75%+ average and honours-equivalent final year.",
        "Google Analytics certified, with market research, consumer behaviour, and strategic marketing training.",
    ]
    if any(term in text for term in ["content", "social", "instagram", "tiktok", "creative"]):
        bullets.append("Produced weekly social content for The Cookie Factory across Instagram, Facebook, and TikTok, including Canva graphics, captions, scheduling, and engagement reporting.")
    if any(term in text for term in ["research", "analytics", "insight", "data", "survey"]):
        bullets.append("Completed primary B2B research on VR/AR adoption and worked on market research recommendations for an AR-driven startup.")
    if any(term in text for term in ["sport", "fitness", "outdoor", "wellness", "athlete", "training"]):
        bullets.append("Brings a real sport/fitness connection through rugby and water polo coaching, Ironman 70.3 training, and a self-built triathlon/gym training app.")
    if any(term in text for term in ["startup", "growth", "product", "ai", "automation", "app"]):
        bullets.append("Built a personal triathlon and gym training app using AI-assisted development, showing product thinking, user feedback, and practical iteration.")
    if any(term in text for term in ["event", "community", "activation", "partnership"]):
        bullets.append("Coached sport and helped organise school water polo tournament activity, showing planning, coordination, and community-facing leadership.")
    return dedupe_keep_order(bullets)[:7]


def cv_keywords_for_job(job: dict[str, Any]) -> list[str]:
    text = f"{job.get('title', '')} {job.get('description', '')}".lower()
    terms = list(MARKETING_KEYWORDS) + list(PREFERRED_KEYWORDS) + ENTRY_LEVEL_SIGNALS
    return [term for term in terms if term in text][:16]


def render_tailored_cv_html(job: dict[str, Any], application: dict[str, Any], body: str) -> str:
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Tailored CV Brief - {html.escape(str(job.get('company', '')))}</title>
  <style>
    body {{ font-family: Arial, sans-serif; max-width: 820px; margin: 40px auto; line-height: 1.5; color: #1f2933; }}
    pre {{ white-space: pre-wrap; font-family: inherit; background: #f6f8fa; padding: 16px; border-radius: 6px; }}
    @media print {{ body {{ margin: 20px; }} pre {{ background: white; padding: 0; }} }}
  </style>
</head>
<body>
  <h1>Tailored CV Brief</h1>
  <p><strong>{html.escape(str(job.get('title', '')))}</strong> at {html.escape(str(job.get('company', '')))}</p>
  <pre>{html.escape(body)}</pre>
</body>
</html>"""


def create_form_fill_task(conn: sqlite3.Connection, app_id: int) -> Path:
    profile = get_profile(conn)
    app = row_to_dict(conn.execute("select * from applications where id=?", (app_id,)).fetchone())
    if not app:
        raise RuntimeError("Application not found")
    job = row_to_dict(conn.execute("select * from jobs where id=?", (app["job_id"],)).fetchone())
    if not job:
        raise RuntimeError("Job not found")
    if not job.get("url"):
        raise RuntimeError("This job does not have a URL to open.")
    if is_board_prep_blocked_url(str(job.get("url", ""))):
        raise RuntimeError(
            "This job still points to a RemoteOK listing page, which is blocking direct form preparation behind signup/CAPTCHA. "
            "Use a direct company/ATS apply URL first, then prepare the form from that real application page."
        )
    active_blocker = active_domain_blocker_for_url(conn, str(job.get("url", "")))
    if active_blocker:
        raise RuntimeError(
            f"{active_blocker.get('domain', 'This ATS domain')} is in cooldown until {active_blocker.get('blocked_until', '')} "
            f"after a platform restriction page. Wait for the cooldown to clear, then retry manually."
        )
    active_limit = active_domain_rate_limit_for_url(conn, str(job.get("url", "")))
    if active_limit:
        raise RuntimeError(
            f"{active_limit.get('domain', 'This ATS domain')} was prepared recently. "
            f"Wait until {active_limit.get('next_allowed_at', '')} before trying again so the ATS does not flag rapid repeated activity."
        )

    write_application_documents(job, app)
    docs_folder = application_documents_folder(job)
    cover_letter_file_path = docs_folder / "cover-letter.rtf"
    artifacts = build_application_artifacts(job, app, profile)
    timestamp = dt.datetime.now().strftime("%Y%m%d%H%M%S")
    report_path = FORM_PREP_DIR / f"application-{app_id}-{timestamp}.report.json"
    screenshot_path = FORM_PREP_DIR / f"application-{app_id}-{timestamp}.png"
    credential = find_site_credential_for_url(conn, str(job.get("url", ""))) or {}
    started_at = now_iso()
    task = {
        "created_at": started_at,
        "platform": detect_application_platform(str(job.get("url", "")), str(job.get("source", ""))),
        "profile": profile,
        "job": {
            "id": job.get("id"),
            "title": job.get("title", ""),
            "company": job.get("company", ""),
            "location": job.get("location", ""),
            "url": job.get("url", ""),
            "source": job.get("source", ""),
            "description": job.get("description", ""),
        },
        "application": {
            "id": app.get("id"),
            "status": app.get("status", ""),
            "cover_letter": app.get("cover_letter", ""),
            "answers": app.get("answers", ""),
            "cv_notes": app.get("cv_notes", ""),
            "contact_email": app.get("contact_email", ""),
            "contact_name": app.get("contact_name", ""),
            "research_notes": app.get("research_notes", ""),
            "company_notes": app.get("company_notes", ""),
            "form_prep_overrides": parse_form_prep_overrides(str(app.get("form_prep_overrides", ""))),
            "cover_letter_file_path": str(cover_letter_file_path),
            "artifacts": artifacts,
        },
        "site_credential": {
            "domain": credential.get("domain", ""),
            "login_url": credential.get("login_url", ""),
            "username": credential.get("username", ""),
            "keychain_service": credential.get("keychain_service", ""),
            "password_set": bool(credential.get("password_set")),
        },
        "report_path": str(report_path),
        "screenshot_path": str(screenshot_path),
        "rules": {
            "final_submit": "Never click final submit. Stop for user review.",
            "captcha": "Do not bypass CAPTCHA, MFA, login challenges, rate limits, or anti-bot systems.",
        },
        "site_policy": {
            "manual_first": detect_application_platform(str(job.get("url", "")), str(job.get("source", ""))) in MANUAL_FIRST_PLATFORMS,
            "prep_rate_limit_minutes": prep_rate_limit_minutes_for_platform(detect_application_platform(str(job.get("url", "")), str(job.get("source", "")))),
        },
    }
    initial_report = {
        "created_at": started_at,
        "started_at": started_at,
        "task_created_at": started_at,
        "platform": task["platform"],
        "status": "queued",
        "current_stage": "task-created",
        "heartbeat_at": started_at,
        "last_event_at": started_at,
        "last_url": str(job.get("url", "")),
        "visited_urls": [str(job.get("url", ""))] if str(job.get("url", "")) else [],
        "login": {"status": "not-attempted"},
        "blocker": {},
        "scanned_fields": [],
        "step_history": [],
        "filled_fields": [],
        "skipped_fields": [],
        "review_fields": [],
        "errors": [],
        "events": [
            {
                "at": started_at,
                "stage": "task-created",
                "message": "Form preparation task created and queued for browser launch.",
                "url": str(job.get("url", "")),
            }
        ],
    }
    report_path.write_text(json.dumps(initial_report, indent=2, ensure_ascii=True), encoding="utf-8")
    task_path = TASK_DIR / f"application-{app_id}-{dt.datetime.now().strftime('%Y%m%d%H%M%S')}.json"
    task_path.write_text(json.dumps(task, indent=2, ensure_ascii=True), encoding="utf-8")
    conn.execute(
        """
        update applications
        set form_prep_report_path=?, form_prep_screenshot_path=?, form_prep_task_path=?, updated_at=?
        where id=?
        """,
        (str(report_path), str(screenshot_path), str(task_path), started_at, app_id),
    )
    conn.commit()
    return task_path


def create_form_fill_smoke_task(conn: sqlite3.Connection) -> Path:
    profile = get_profile(conn)
    app = row_to_dict(
        conn.execute("select * from applications order by updated_at desc limit 1").fetchone()
    ) or {}
    job = {"id": "smoke", "title": "Marketing Coordinator Smoke Test", "company": "Local Test Company", "location": "Remote"}
    html_path = SMOKE_DIR / "sample-application-form.html"
    html_path.write_text(
        f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Local Application Form Smoke Test</title>
  <style>
    body {{ font-family: Arial, sans-serif; max-width: 820px; margin: 32px auto; color: #15202b; line-height: 1.4; }}
    label {{ display: block; font-weight: 700; margin: 14px 0 6px; }}
    input, select, textarea {{ width: 100%; border: 1px solid #cfd7df; border-radius: 6px; padding: 10px; font: inherit; }}
    textarea {{ min-height: 120px; }}
    .row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
    .note {{ background: #fff7ed; border-left: 4px solid #b35c00; padding: 12px; border-radius: 6px; }}
    button {{ margin-top: 16px; padding: 10px 14px; border-radius: 6px; border: 1px solid #087f8c; background: #087f8c; color: white; font: inherit; }}
  </style>
</head>
<body>
  <h1>Local Application Form Smoke Test</h1>
  <p class="note">This fake form is only for testing the local Playwright filler. Nothing is submitted anywhere.</p>
  <form>
    <div class="row">
      <div><label for="first_name">First name</label><input id="first_name" name="first_name"></div>
      <div><label for="last_name">Last name</label><input id="last_name" name="last_name"></div>
      <div><label for="email">Email</label><input id="email" name="email" type="email"></div>
      <div><label for="phone">Phone</label><input id="phone" name="phone" type="tel"></div>
      <div><label for="location">Current location</label><input id="location" name="location"></div>
      <div><label for="country">Country</label><select id="country" name="country"><option></option><option>South Africa</option><option>United Kingdom</option><option>United States</option></select></div>
      <div><label for="linkedin">LinkedIn</label><input id="linkedin" name="linkedin"></div>
      <div><label for="portfolio">Portfolio / website</label><input id="portfolio" name="portfolio"></div>
    </div>
    <label for="resume">Resume/CV upload</label><input id="resume" name="resume" type="file" accept=".pdf">
    <label for="cover_letter">Cover letter</label><textarea id="cover_letter" name="cover_letter"></textarea>
    <label for="why_role">Why are you interested in this role?</label><textarea id="why_role" name="why_role"></textarea>
    <label for="salary_expectation">Salary expectation</label><input id="salary_expectation" name="salary_expectation">
    <label for="availability">Availability / start date</label><input id="availability" name="availability">
    <label for="work_authorization">Work authorization</label><textarea id="work_authorization" name="work_authorization"></textarea>
    <label><input type="checkbox" name="demographics" style="width:auto"> Prefer not to answer demographic questions</label>
    <button type="button">Review complete</button>
  </form>
</body>
</html>
""",
        encoding="utf-8",
    )
    timestamp = dt.datetime.now().strftime("%Y%m%d%H%M%S")
    task = {
        "created_at": now_iso(),
        "platform": "smoke",
        "profile": profile,
        "job": {
            **job,
            "url": html_path.as_uri(),
            "source": "local-smoke-test",
            "description": "Local form filler smoke test.",
        },
        "application": {
            "id": "smoke",
            "cover_letter": app.get("cover_letter") or "Local smoke-test cover letter.",
            "answers": app.get("answers") or "Local smoke-test questionnaire answers.",
            "cv_notes": app.get("cv_notes", ""),
            "contact_email": "",
            "contact_name": "",
            "research_notes": "",
            "company_notes": "",
        },
        "site_credential": {
            "domain": "",
            "login_url": "",
            "username": "",
            "keychain_service": "",
            "password_set": False,
        },
        "report_path": str(FORM_PREP_DIR / f"smoke-test-{timestamp}.report.json"),
        "screenshot_path": str(FORM_PREP_DIR / f"smoke-test-{timestamp}.png"),
        "rules": {
            "final_submit": "Never click final submit. This is a local smoke test.",
            "captcha": "No CAPTCHA or login is present in this local test.",
        },
    }
    task_path = TASK_DIR / f"smoke-test-{timestamp}.json"
    task_path.write_text(json.dumps(task, indent=2, ensure_ascii=True), encoding="utf-8")
    return task_path


def latest_form_fill_task_path(conn: sqlite3.Connection, app_id: int) -> Path:
    row = conn.execute(
        "select form_prep_task_path from applications where id=?",
        (app_id,),
    ).fetchone()
    if not row or not row["form_prep_task_path"]:
        raise RuntimeError("No saved form-prep task exists for this application yet.")
    task_path = Path(str(row["form_prep_task_path"]))
    if not task_path.exists():
        raise RuntimeError("The saved form-prep task file no longer exists. Run Prepare form again.")
    return task_path


def mark_form_fill_started(conn: sqlite3.Connection, app_id: int, started_at: str = "") -> None:
    timestamp = started_at or now_iso()
    conn.execute(
        "update applications set form_prep_started_at=?, updated_at=? where id=?",
        (timestamp, timestamp, app_id),
    )
    conn.commit()


def _find_node() -> str:
    node_path = shutil.which("node")
    if node_path:
        return node_path
    for candidate in [
        "/opt/homebrew/bin/node",
        "/usr/local/bin/node",
        "/usr/bin/node",
    ]:
        if os.path.isfile(candidate):
            return candidate
    raise RuntimeError("Node.js not found. Install it via Homebrew: brew install node")


def launch_form_filler(task_path: Path) -> int:
    script = ROOT / "scripts" / "form_filler.js"
    if not script.exists():
        raise RuntimeError("Form filler script is missing.")
    node_modules = ROOT / "node_modules" / "playwright"
    if not node_modules.exists():
        raise RuntimeError("Playwright is not installed yet. Run npm install first.")
    node = _find_node()
    log_base = LOG_DIR / f"form-fill-{task_path.stem}"
    stdout = (log_base.with_suffix(".out.log")).open("a", encoding="utf-8")
    stderr = (log_base.with_suffix(".err.log")).open("a", encoding="utf-8")
    process = subprocess.Popen(
        [node, str(script), "--task", str(task_path)],
        cwd=str(ROOT),
        stdout=stdout,
        stderr=stderr,
        start_new_session=True,
    )
    return int(process.pid)


def render_printable_application(job: dict[str, Any], application: dict[str, Any]) -> str:
    def section(title: str, body: str) -> str:
        return f"<h2>{html.escape(title)}</h2><pre>{html.escape(body or '')}</pre>"

    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>{html.escape(str(job.get('title', 'Application')))}</title>
  <style>
    body {{ font-family: Arial, sans-serif; max-width: 840px; margin: 40px auto; line-height: 1.5; color: #1f2933; }}
    h1 {{ font-size: 28px; margin-bottom: 4px; }}
    h2 {{ border-top: 1px solid #d8dee4; padding-top: 20px; margin-top: 28px; }}
    pre {{ white-space: pre-wrap; font-family: inherit; background: #f6f8fa; padding: 16px; border-radius: 6px; }}
    a {{ color: #075985; }}
    @media print {{ body {{ margin: 20px; }} pre {{ background: white; padding: 0; }} }}
  </style>
</head>
<body>
  <h1>{html.escape(str(job.get('title', '')))}</h1>
  <p><strong>{html.escape(str(job.get('company', '')))}</strong> - {html.escape(str(job.get('location', '')))}</p>
  <p><a href="{html.escape(str(job.get('url', '')))}">{html.escape(str(job.get('url', '')))}</a></p>
  {section("Cover Letter", str(application.get("cover_letter", "")))}
  {section("CV Tailoring Notes", str(application.get("cv_notes", "")))}
  {section("Tailored CV Brief", render_tailored_cv_text(job, application))}
  {section("Questionnaire Answers", str(application.get("answers", "")))}
  {section("Company Research", str(application.get("research_notes", "")))}
  {section("Research Sources", str(application.get("research_sources", "")))}
  {section("Follow-up Email", str(application.get("follow_up", "")))}
</body>
</html>"""


def try_extract_cv_text(path: str) -> str:
    path_obj = Path(path)
    if not path_obj.exists():
        return ""
    pdftotext = shutil.which("pdftotext")
    if pdftotext:
        try:
            result = subprocess.run(
                [pdftotext, path, "-"],
                check=True,
                capture_output=True,
                text=True,
                timeout=20,
            )
            return result.stdout.strip()
        except Exception:
            pass
    return extract_pdf_text_standard_library(path_obj)


def try_extract_writing_sample(path: str) -> str:
    path_obj = Path(path).expanduser()
    if not path_obj.exists():
        return ""
    suffix = path_obj.suffix.lower()
    if suffix == ".pdf":
        return try_extract_cv_text(str(path_obj))
    if suffix in {".txt", ".md", ".markdown"}:
        return path_obj.read_text(encoding="utf-8", errors="ignore").strip()
    if suffix == ".docx":
        return extract_docx_text(path_obj)
    return path_obj.read_text(encoding="utf-8", errors="ignore").strip()


def extract_docx_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as docx:
            xml = docx.read("word/document.xml").decode("utf-8", errors="ignore")
    except Exception:
        return ""
    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"</w:tr>", "\n", xml)
    xml = re.sub(r"<[^>]+>", "", xml)
    return normalize_space(html.unescape(xml)).replace(". ", ".\n").strip()


def analyze_writing_style(text: str) -> str:
    cleaned = normalize_space(text)
    if not cleaned:
        return ""
    sentences = [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", cleaned) if sentence.strip()]
    words = re.findall(r"\b[\w']+\b", cleaned)
    avg_sentence = round(len(words) / max(1, len(sentences)), 1)
    contractions = sorted(set(re.findall(r"\b\w+'(?:m|re|ve|ll|d|t|s)\b", cleaned, flags=re.I)))[:10]
    first_person = len(re.findall(r"\b(I|I'm|I've|my|me)\b", cleaned, flags=re.I))
    common_phrases = common_style_phrases(cleaned)
    tone = []
    if avg_sentence <= 16:
        tone.append("short/direct sentences")
    elif avg_sentence <= 24:
        tone.append("medium-length explanatory sentences")
    else:
        tone.append("longer reflective sentences")
    if contractions:
        tone.append("uses contractions naturally")
    if first_person >= 5:
        tone.append("comfortable writing in first person")
    return textwrap.dedent(
        f"""
        Writing sample analysed from Phillip's own document.

        - Average sentence length: {avg_sentence} words.
        - Observed tone markers: {", ".join(tone) or "not enough text to infer strongly"}.
        - Contractions seen: {", ".join(contractions) if contractions else "none obvious"}.
        - Repeated words/phrases to consider preserving: {", ".join(common_phrases) if common_phrases else "none obvious"}.

        Use this as a voice reference only. Do not copy private passages into applications unless Phillip explicitly approves them.
        """
    ).strip()


def common_style_phrases(text: str) -> list[str]:
    words = [word.lower() for word in re.findall(r"\b[a-zA-Z][a-zA-Z']+\b", text)]
    stop = {
        "the", "and", "that", "with", "this", "from", "have", "were", "been",
        "they", "their", "there", "about", "would", "could", "should", "because",
        "which", "what", "when", "where", "into", "also", "very", "just",
    }
    counts: dict[str, int] = {}
    for size in (2, 3):
        for i in range(0, max(0, len(words) - size + 1)):
            phrase_words = words[i : i + size]
            if any(word in stop for word in phrase_words):
                continue
            phrase = " ".join(phrase_words)
            counts[phrase] = counts.get(phrase, 0) + 1
    return [phrase for phrase, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])) if count > 1][:8]


def extract_pdf_text_standard_library(path: Path) -> str:
    data = path.read_bytes()
    text_parts: list[str] = []
    for match in re.finditer(rb"(\d+)\s+(\d+)\s+obj(.*?)endobj", data, re.S):
        content = match.group(3)
        if b"stream" not in content:
            continue
        header, rest = content.split(b"stream", 1)
        stream, _ = rest.split(b"endstream", 1)
        if stream.startswith(b"\r\n"):
            stream = stream[2:]
        elif stream.startswith(b"\n"):
            stream = stream[1:]
        if stream.endswith(b"\r\n"):
            stream = stream[:-2]
        elif stream.endswith(b"\n"):
            stream = stream[:-1]
        try:
            decoded = stream
            if b"ASCII85Decode" in header:
                decoded = base64.a85decode(decoded, adobe=True)
            if b"FlateDecode" in header:
                decoded = zlib.decompress(decoded)
        except Exception:
            continue
        if b"/Subtype /Image" in header or b"/Length1" in header or b"begincmap" in decoded[:200]:
            continue
        # Ignore image/font streams; text-showing content streams contain Tj/TJ.
        if b"Tj" not in decoded and b"TJ" not in decoded:
            continue
        text_parts.extend(extract_pdf_literal_strings(decoded))
    cleaned = [normalize_space(part.replace("\x00", "")) for part in text_parts]
    cleaned = [part for part in cleaned if part and any(ch.isalnum() for ch in part)]
    return "\n".join(cleaned)


def extract_pdf_literal_strings(content: bytes) -> list[str]:
    strings: list[str] = []
    i = 0
    while i < len(content):
        if content[i] != 40:
            i += 1
            continue
        depth = 1
        j = i + 1
        raw = bytearray()
        escaped = False
        while j < len(content) and depth:
            byte = content[j]
            if escaped:
                raw.append(92)
                raw.append(byte)
                escaped = False
                j += 1
                continue
            if byte == 92:
                escaped = True
                j += 1
                continue
            if byte == 40:
                depth += 1
                raw.append(byte)
                j += 1
                continue
            if byte == 41:
                depth -= 1
                if depth:
                    raw.append(byte)
                j += 1
                continue
            raw.append(byte)
            j += 1
        lookahead = content[j : j + 24]
        if b"Tj" in lookahead or b"TJ" in lookahead or b"'" in lookahead or b'"' in lookahead:
            strings.append(unescape_pdf_literal(bytes(raw)))
        i = j
    return strings


def unescape_pdf_literal(value: bytes) -> str:
    out: list[str] = []
    i = 0
    while i < len(value):
        byte = value[i]
        if byte != 92:
            out.append(chr(byte))
            i += 1
            continue
        i += 1
        if i >= len(value):
            break
        escaped = value[i]
        mapping = {
            ord("n"): "\n",
            ord("r"): "\r",
            ord("t"): "\t",
            ord("b"): "\b",
            ord("f"): "\f",
            ord("("): "(",
            ord(")"): ")",
            ord("\\"): "\\",
        }
        if escaped in mapping:
            out.append(mapping[escaped])
            i += 1
        elif 48 <= escaped <= 55:
            digits = bytes([escaped])
            i += 1
            for _ in range(2):
                if i < len(value) and 48 <= value[i] <= 55:
                    digits += bytes([value[i]])
                    i += 1
                else:
                    break
            out.append(chr(int(digits, 8)))
        elif escaped in (10, 13):
            if escaped == 13 and i + 1 < len(value) and value[i + 1] == 10:
                i += 2
            else:
                i += 1
        else:
            out.append(chr(escaped))
            i += 1
    return "".join(out)


class AppHandler(BaseHTTPRequestHandler):
    server_version = "JobApplicationAI/0.1"

    def _check_auth(self) -> bool:
        if not AUTH_PASSWORD:
            return True
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Basic "):
            return False
        try:
            decoded = base64.b64decode(auth[6:]).decode("utf-8")
            _, pwd = decoded.split(":", 1)
            return pwd == AUTH_PASSWORD
        except Exception:
            return False

    def _require_auth(self) -> bool:
        if not self._check_auth():
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="Job Application AI"')
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", "12")
            self.end_headers()
            self.wfile.write(b"Unauthorized")
            return False
        return True

    def do_GET(self) -> None:
        if not self._require_auth():
            return
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/":
            self.html(INDEX_HTML)
        elif parsed.path == "/swipe":
            self.html(SWIPE_HTML)
        elif parsed.path == "/manifest.json":
            encoded = json.dumps(PWA_MANIFEST, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("content-type", "application/manifest+json")
            self.send_header("content-length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
        elif parsed.path == "/api/state":
            self.json(get_state())
        elif parsed.path == "/api/swipe/jobs":
            self.json({"ok": True, "jobs": get_swipe_jobs()})
        elif parsed.path == "/api/open-searches":
            self.json(search_links())
        elif parsed.path == "/api/session-memory":
            self.json({"ok": True, "content": read_session_memory()})
        else:
            self.error(404, "Not found")

    def do_POST(self) -> None:
        if not self._require_auth():
            return
        parsed = urllib.parse.urlparse(self.path)
        try:
            data = self.read_json()
            if parsed.path == "/api/profile":
                with connect() as conn:
                    save_profile(conn, {k: str(v) for k, v in data.items()})
                self.json({"ok": True})
            elif parsed.path == "/api/profile/extract-cv":
                with connect() as conn:
                    profile = get_profile(conn)
                    extracted = try_extract_cv_text(profile.get("cv_path", ""))
                    if extracted:
                        save_profile(conn, {"cv_text": extracted})
                    self.json({"ok": bool(extracted), "text": extracted})
            elif parsed.path == "/api/profile/extract-writing-sample":
                with connect() as conn:
                    profile = get_profile(conn)
                    path = str(data.get("path") or profile.get("writing_sample_path", ""))
                    pasted = str(data.get("text") or "")
                    extracted = pasted.strip() or try_extract_writing_sample(path)
                    style_notes = analyze_writing_style(extracted)
                    if extracted:
                        save_profile(
                            conn,
                            {
                                "writing_sample_path": path,
                                "writing_sample_text": extracted,
                                "writing_style_notes": style_notes,
                            },
                        )
                    self.json({"ok": bool(extracted), "text": extracted, "style_notes": style_notes})
            elif parsed.path == "/api/jobs/manual":
                with connect() as conn:
                    job_id = upsert_job(conn, data)
                self.json({"ok": True, "id": job_id})
            elif parsed.path == "/api/jobs/url":
                with connect() as conn:
                    job_id = add_job_from_url(conn, str(data.get("url", "")))
                self.json({"ok": True, "id": job_id})
            elif parsed.path == "/api/alerts/import":
                with connect() as conn:
                    result = import_job_alert_text(conn, str(data.get("text", "")), str(data.get("source", "email-alert")))
                self.json({"ok": True, **result})
            elif parsed.path == "/api/discover":
                source = str(data.get("source", "")).lower()
                token = str(data.get("token", "")).strip()
                query = str(data.get("query", "")).strip() or GRADUATE_MARKETING_DISCOVERY_QUERY
                if not token:
                    raise RuntimeError("Missing board token/site name")
                with connect() as conn:
                    if source == "greenhouse":
                        result = discover_greenhouse(conn, token, query)
                    elif source == "lever":
                        result = discover_lever(conn, token, query)
                    elif source == "ashby":
                        result = discover_ashby(conn, token, query)
                    elif source == "smartrecruiters":
                        result = discover_smartrecruiters(conn, token, query)
                    elif source == "recruitee":
                        result = discover_recruitee(conn, token, query)
                    elif source == "remotive":
                        result = discover_remotive(conn, token or "marketing", query)
                    elif source == "remoteok":
                        result = discover_remoteok(conn, token, query)
                    elif source == "arbeitnow":
                        result = discover_arbeitnow(conn, token, query)
                    elif source == "workable":
                        result = discover_workable_public(conn, token, query)
                    elif source == "teamtailor":
                        result = discover_teamtailor_public(conn, token, query)
                    elif source in {"careers"}:
                        result = discover_careers_page(conn, token, query)
                    else:
                        raise RuntimeError("Unsupported source")
                self.json({"ok": True, **result})
            elif parsed.path == "/api/sources/save":
                with connect() as conn:
                    source_id = save_job_source(conn, data)
                self.json({"ok": True, "id": source_id})
            elif parsed.path == "/api/sources/run":
                with connect() as conn:
                    source = row_to_dict(conn.execute("select * from job_sources where id=?", (int(data.get("id")),)).fetchone())
                    if not source:
                        raise RuntimeError("Source not found")
                    result = run_job_source(conn, source)
                self.json({"ok": True, **result})
            elif parsed.path == "/api/sources/run-all":
                result = run_enabled_sources(force=True)
                self.json({"ok": True, **result})
            elif parsed.path == "/api/sources/seed-starter":
                with connect() as conn:
                    result = seed_starter_sources(conn)
                self.json({"ok": True, **result})
            elif parsed.path == "/api/sources/toggle":
                with connect() as conn:
                    conn.execute(
                        "update job_sources set enabled=?, updated_at=? where id=?",
                        (1 if data.get("enabled", True) else 0, now_iso(), int(data.get("id"))),
                    )
                    conn.commit()
                self.json({"ok": True})
            elif parsed.path == "/api/sources/pause-failing":
                with connect() as conn:
                    result = pause_failing_sources(conn)
                self.json({"ok": True, **result})
            elif parsed.path == "/api/daily/run":
                limit = int(data.get("limit") or 5)
                result = run_daily_workflow(limit)
                self.json({"ok": True, **result})
            elif parsed.path == "/api/automation/run":
                limit = int(data.get("limit") or 5)
                result = run_automatic_mode(limit)
                self.json({"ok": True, **result})
            elif parsed.path == "/api/reminders/export":
                with connect() as conn:
                    result = export_reminders_calendar(conn)
                self.json({"ok": True, **result})
            elif parsed.path == "/api/reminders/notify-due":
                with connect() as conn:
                    result = notify_due_reminders(conn)
                self.json({"ok": True, **result})
            elif parsed.path == "/api/jobs/status":
                with connect() as conn:
                    job_id = int(data.get("id"))
                    status = str(data.get("status", "new"))
                    reject_reason = str(data.get("reject_reason", ""))
                    if reject_reason and status == "rejected":
                        conn.execute(
                            "update jobs set status=?, reject_reason=?, updated_at=? where id=?",
                            (status, reject_reason, now_iso(), job_id),
                        )
                    else:
                        conn.execute(
                            "update jobs set status=?, updated_at=? where id=?",
                            (status, now_iso(), job_id),
                        )
                    if status == "applied":
                        app_id = ensure_application(conn, job_id)
                        app_row = conn.execute("select * from applications where id=?", (app_id,)).fetchone()
                        if app_row and not app_row["cover_letter"]:
                            # If the user marks a job applied from the job list, still create the draft pack.
                            conn.commit()
                            generate_application(conn, job_id)
                            conn.execute(
                                "update jobs set status='applied', updated_at=? where id=?",
                                (now_iso(), job_id),
                            )
                        follow_up_date = (dt.date.today() + dt.timedelta(days=7)).isoformat()
                        conn.execute(
                            """
                            update applications
                            set status='submitted',
                                next_follow_up=case when next_follow_up='' then ? else next_follow_up end,
                                updated_at=?
                            where job_id=?
                            """,
                            (follow_up_date, now_iso(), job_id),
                        )
                    conn.commit()
                self.json({"ok": True})
            elif parsed.path == "/api/jobs/too-senior":
                with connect() as conn:
                    job_id = int(data.get("id"))
                    flagged = 1 if data.get("too_senior", True) else 0
                    conn.execute(
                        "update jobs set too_senior=?, updated_at=? where id=?",
                        (flagged, now_iso(), job_id),
                    )
                    conn.commit()
                    result = rescore_all_jobs(conn)
                self.json({"ok": True, **result})
            elif parsed.path == "/api/jobs/shortlist-top":
                limit = int(data.get("limit") or 5)
                with connect() as conn:
                    result = shortlist_top_jobs(conn, limit)
                self.json({"ok": True, **result})
            elif parsed.path == "/api/applications/refresh-queue":
                limit = int(data.get("limit") or 5)
                result = refresh_application_queue(limit)
                self.json({"ok": True, **result})
            elif parsed.path == "/api/applications/reject-and-replace":
                app_id = int(data.get("id") or 0)
                result = reject_application_and_replace(
                    app_id,
                    str(data.get("reason") or ""),
                    str(data.get("notes") or ""),
                )
                self.json({"ok": True, **result})
            elif parsed.path == "/api/applications/cleanup-stale":
                result = cleanup_stale_applications()
                self.json({"ok": True, **result})
            elif parsed.path == "/api/applications/queue-state":
                app_id = int(data.get("id") or 0)
                result = set_application_queue_state(app_id, str(data.get("queue_state") or "review"))
                self.json({"ok": True, **result})
            elif parsed.path == "/api/jobs/rescore":
                with connect() as conn:
                    result = rescore_all_jobs(conn)
                self.json({"ok": True, **result})
            elif parsed.path == "/api/applications/generate-bulk":
                limit = int(data.get("limit") or 5)
                status = str(data.get("status") or "shortlisted")
                with connect() as conn:
                    result = generate_drafts_for_jobs(conn, status, limit)
                self.json({"ok": True, **result})
            elif parsed.path == "/api/applications/generate":
                with connect() as conn:
                    app_id = generate_application(conn, int(data.get("job_id")))
                self.json({"ok": True, "id": app_id})
            elif parsed.path == "/api/cv-versions/save":
                with connect() as conn:
                    cv_id = save_cv_version(conn, data)
                self.json({"ok": True, "id": cv_id})
            elif parsed.path == "/api/cv-versions/delete":
                with connect() as conn:
                    delete_cv_version(conn, int(data.get("id") or 0))
                self.json({"ok": True})
            elif parsed.path == "/api/applications/save":
                with connect() as conn:
                    app_id = int(data.get("id"))
                    fields = [
                        "status",
                        "queue_state",
                        "contact_email",
                        "contact_name",
                        "contact_role",
                        "company_notes",
                        "cover_letter",
                        "cv_notes",
                        "answers",
                        "research_url",
                        "research_notes",
                        "research_sources",
                        "follow_up",
                        "next_follow_up",
                        "form_prep_overrides",
                    ]
                    updates = {field: str(data.get(field, "")) for field in fields if field in data}
                    if updates.get("status") == "submitted" and not updates.get("next_follow_up"):
                        updates["next_follow_up"] = (dt.date.today() + dt.timedelta(days=7)).isoformat()
                    if updates:
                        assignments = ", ".join([f"{field}=?" for field in updates])
                        values = list(updates.values()) + [now_iso(), app_id]
                        conn.execute(f"update applications set {assignments}, updated_at=? where id=?", values)
                        conn.commit()
                    row = conn.execute(
                        """
                        select jobs.*, applications.*
                        from applications join jobs on jobs.id = applications.job_id
                        where applications.id=?
                        """,
                        (app_id,),
                    ).fetchone()
                    if row:
                        job = row_to_dict(conn.execute("select * from jobs where id=(select job_id from applications where id=?)", (app_id,)).fetchone()) or {}
                        app = row_to_dict(conn.execute("select * from applications where id=?", (app_id,)).fetchone()) or {}
                        write_application_documents(job, app)
                self.json({"ok": True})
            elif parsed.path == "/api/site-credentials/save":
                with connect() as conn:
                    credential_id = save_site_credential(conn, data)
                self.json({"ok": True, "id": credential_id})
            elif parsed.path == "/api/site-credentials/delete":
                with connect() as conn:
                    delete_site_credential(conn, int(data.get("id")))
                self.json({"ok": True})
            elif parsed.path == "/api/applications/regenerate-followup":
                app_id = int(data.get("id"))
                with connect() as conn:
                    profile = get_profile(conn)
                    app = row_to_dict(conn.execute("select * from applications where id=?", (app_id,)).fetchone())
                    if not app:
                        raise RuntimeError("Application not found")
                    job = row_to_dict(conn.execute("select * from jobs where id=?", (app["job_id"],)).fetchone()) or {}
                    # Save latest contact context before regenerating.
                    for field in ["contact_email", "contact_name", "contact_role", "company_notes"]:
                        if field in data:
                            app[field] = str(data.get(field, ""))
                    follow_up = compose_follow_up(profile, job, app)
                    timestamp = now_iso()
                    conn.execute(
                        """
                        update applications
                        set contact_email=?, contact_name=?, contact_role=?, company_notes=?,
                            follow_up=?, updated_at=?
                        where id=?
                        """,
                        (
                            app.get("contact_email", ""),
                            app.get("contact_name", ""),
                            app.get("contact_role", ""),
                            app.get("company_notes", ""),
                            follow_up,
                            timestamp,
                            app_id,
                        ),
                    )
                    conn.commit()
                    refreshed_app = row_to_dict(conn.execute("select * from applications where id=?", (app_id,)).fetchone()) or {}
                    write_application_documents(job, refreshed_app)
                self.json({"ok": True, "follow_up": follow_up})
            elif parsed.path == "/api/applications/humanize":
                app_id = int(data.get("id"))
                with connect() as conn:
                    app = row_to_dict(conn.execute("select * from applications where id=?", (app_id,)).fetchone())
                    if not app:
                        raise RuntimeError("Application not found")
                    for field in ["cover_letter", "answers", "follow_up", "company_notes"]:
                        if field in data:
                            app[field] = str(data.get(field, ""))
                    cover_letter = phillip_voice_text(str(app.get("cover_letter", "")), "cover_letter")
                    answers = phillip_voice_text(str(app.get("answers", "")), "answers")
                    follow_up = phillip_voice_text(str(app.get("follow_up", "")), "follow_up")
                    timestamp = now_iso()
                    conn.execute(
                        """
                        update applications
                        set cover_letter=?, answers=?, follow_up=?, company_notes=?, updated_at=?
                        where id=?
                        """,
                        (cover_letter, answers, follow_up, app.get("company_notes", ""), timestamp, app_id),
                    )
                    conn.commit()
                    job = row_to_dict(conn.execute("select * from jobs where id=?", (app["job_id"],)).fetchone()) or {}
                    refreshed_app = row_to_dict(conn.execute("select * from applications where id=?", (app_id,)).fetchone()) or {}
                    write_application_documents(job, refreshed_app)
                    checks = {
                        "cover_letter": voice_check(cover_letter),
                        "answers": voice_check(answers),
                        "follow_up": voice_check(follow_up),
                    }
                self.json({"ok": True, "cover_letter": cover_letter, "answers": answers, "follow_up": follow_up, "checks": checks})
            elif parsed.path == "/api/applications/research":
                app_id = int(data.get("id"))
                research_url = str(data.get("research_url", ""))
                with connect() as conn:
                    app = row_to_dict(conn.execute("select * from applications where id=?", (app_id,)).fetchone())
                    if not app:
                        raise RuntimeError("Application not found")
                    job = row_to_dict(conn.execute("select * from jobs where id=?", (app["job_id"],)).fetchone()) or {}
                    for field in ["company_notes"]:
                        if field in data:
                            app[field] = str(data.get(field, ""))
                    notes, sources, saved_url = generate_application_research(job, app, research_url)
                    timestamp = now_iso()
                    conn.execute(
                        """
                        update applications
                        set company_notes=?, research_url=?, research_notes=?, research_sources=?, updated_at=?
                        where id=?
                        """,
                        (
                            app.get("company_notes", ""),
                            saved_url,
                            notes,
                            sources,
                            timestamp,
                            app_id,
                        ),
                    )
                    conn.commit()
                    refreshed_app = row_to_dict(conn.execute("select * from applications where id=?", (app_id,)).fetchone()) or {}
                    write_application_documents(job, refreshed_app)
                self.json({"ok": True, "research_notes": notes, "research_sources": sources, "research_url": saved_url})
            elif parsed.path == "/api/applications/prepare-form":
                app_id = int(data.get("id"))
                with connect() as conn:
                    task_path = create_form_fill_task(conn, app_id)
                    pid = launch_form_filler(task_path)
                    mark_form_fill_started(conn, app_id)
                self.json({"ok": True, "pid": pid, "task": str(task_path)})
            elif parsed.path == "/api/applications/resume-form":
                app_id = int(data.get("id"))
                with connect() as conn:
                    task_path = latest_form_fill_task_path(conn, app_id)
                    pid = launch_form_filler(task_path)
                    mark_form_fill_started(conn, app_id)
                self.json({"ok": True, "pid": pid, "task": str(task_path)})
            elif parsed.path == "/api/applications/form-feedback":
                with connect() as conn:
                    feedback_id = save_form_fill_feedback(conn, data)
                self.json({"ok": True, "id": feedback_id})
            elif parsed.path == "/api/form-fill/smoke":
                with connect() as conn:
                    task_path = create_form_fill_smoke_task(conn)
                pid = launch_form_filler(task_path)
                self.json({"ok": True, "pid": pid, "task": str(task_path)})
            elif parsed.path == "/api/jobs/resolve-apply-url":
                job_id = int(data.get("job_id") or data.get("id") or 0)
                with connect() as conn:
                    result = resolve_board_apply_url(conn, job_id)
                self.json({**result, "ok": result.get("ok", False)})
            elif parsed.path == "/api/jobs/update-url":
                job_id = int(data.get("job_id") or data.get("id") or 0)
                new_url = normalize_space(str(data.get("url") or ""))
                if not job_id or not new_url:
                    raise RuntimeError("job_id and url are required.")
                with connect() as conn:
                    conn.execute("update jobs set url=?, updated_at=? where id=?", (new_url, now_iso(), job_id))
                    conn.commit()
                self.json({"ok": True, "url": new_url})
            elif parsed.path == "/api/email/config":
                updates = {
                    "JOB_AI_SMTP_HOST": str(data.get("host", "smtp.mweb.co.za")),
                    "JOB_AI_SMTP_PORT": str(data.get("port", "587")),
                    "JOB_AI_SMTP_USER": str(data.get("user", "")),
                    "JOB_AI_SMTP_FROM": str(data.get("from", data.get("user", ""))),
                    "JOB_AI_SMTP_TO": str(data.get("to", "")),
                    "JOB_AI_SMTP_STARTTLS": "1" if data.get("starttls", True) else "0",
                }
                password = str(data.get("password", ""))
                if password:
                    updates["JOB_AI_SMTP_PASSWORD"] = password
                write_local_env(updates)
                self.json({"ok": True, "email": email_config_status()})
            elif parsed.path == "/api/email/inbox-config":
                updates = {
                    "JOB_AI_IMAP_HOST": str(data.get("host", "imap.mweb.co.za")),
                    "JOB_AI_IMAP_PORT": str(data.get("port", "993")),
                    "JOB_AI_IMAP_USER": str(data.get("user", "")),
                    "JOB_AI_IMAP_SSL": "1" if data.get("ssl", True) else "0",
                    "JOB_AI_IMAP_MAILBOX": str(data.get("mailbox", "INBOX") or "INBOX"),
                    "JOB_AI_IMAP_LOOKBACK_DAYS": str(data.get("lookback_days", "45") or "45"),
                }
                password = str(data.get("password", ""))
                if password:
                    updates["JOB_AI_IMAP_PASSWORD"] = password
                write_local_env(updates)
                self.json({"ok": True, "inbox": inbox_config_status()})
            elif parsed.path == "/api/email/scan-inbox":
                result = scan_inbox_for_replies(int(data.get("limit") or 80))
                self.json({"ok": True, **result})
            elif parsed.path == "/api/inbox/status":
                message_id = int(data.get("id"))
                status = normalize_space(str(data.get("status", "reviewed"))) or "reviewed"
                app_status = normalize_space(str(data.get("application_status", "")))
                lead_status = normalize_space(str(data.get("lead_status", "")))
                with connect() as conn:
                    msg = row_to_dict(conn.execute("select * from inbox_messages where id=?", (message_id,)).fetchone())
                    if not msg:
                        raise RuntimeError("Inbox message not found")
                    conn.execute(
                        "update inbox_messages set status=?, updated_at=? where id=?",
                        (status, now_iso(), message_id),
                    )
                    if app_status and int(msg.get("application_id") or 0):
                        conn.execute(
                            "update applications set status=?, updated_at=? where id=?",
                            (app_status, now_iso(), int(msg["application_id"])),
                        )
                    if lead_status and int(msg.get("lead_id") or 0):
                        conn.execute(
                            "update company_leads set status=?, updated_at=? where id=?",
                            (lead_status, now_iso(), int(msg["lead_id"])),
                        )
                    conn.commit()
                self.json({"ok": True})
            elif parsed.path == "/api/inbox/match":
                message_id = int(data.get("id"))
                application_id = int(data.get("application_id") or 0)
                lead_id = int(data.get("lead_id") or 0)
                if not application_id and not lead_id:
                    raise RuntimeError("Choose an application or outreach lead to match.")
                with connect() as conn:
                    msg = row_to_dict(conn.execute("select * from inbox_messages where id=?", (message_id,)).fetchone())
                    if not msg:
                        raise RuntimeError("Inbox message not found")
                    if application_id:
                        exists = conn.execute("select 1 from applications where id=?", (application_id,)).fetchone()
                        if not exists:
                            raise RuntimeError("Application not found")
                        conn.execute(
                            """
                            update inbox_messages
                            set matched_type='application', application_id=?, lead_id=0,
                                confidence=max(confidence, 95), updated_at=?
                            where id=?
                            """,
                            (application_id, now_iso(), message_id),
                        )
                    else:
                        exists = conn.execute("select 1 from company_leads where id=?", (lead_id,)).fetchone()
                        if not exists:
                            raise RuntimeError("Outreach lead not found")
                        conn.execute(
                            """
                            update inbox_messages
                            set matched_type='outreach', application_id=0, lead_id=?,
                                confidence=max(confidence, 95), updated_at=?
                            where id=?
                            """,
                            (lead_id, now_iso(), message_id),
                        )
                    conn.commit()
                self.json({"ok": True})
            elif parsed.path == "/api/email/test":
                status = email_config_status()
                to_address = str(data.get("to") or status.get("to") or status.get("from") or "")
                send_smtp_message(
                    to_address,
                    "Job Application AI test email",
                    "This is a test email from your local Job Application AI app.",
                )
                self.json({"ok": True})
            elif parsed.path == "/api/email/send-followup":
                app_id = int(data.get("id"))
                to_address = str(data.get("to", ""))
                with connect() as conn:
                    row = conn.execute(
                        """
                        select applications.*, jobs.title, jobs.company, jobs.url, jobs.location
                        from applications
                        join jobs on jobs.id = applications.job_id
                        where applications.id=?
                        """,
                        (app_id,),
                    ).fetchone()
                    app = row_to_dict(row)
                    if not app:
                        raise RuntimeError("Application not found")
                    profile = get_profile(conn)
                    job = row_to_dict(conn.execute("select * from jobs where id=?", (app["job_id"],)).fetchone()) or {}
                    app["contact_email"] = to_address
                    follow_up_body = compose_follow_up(profile, job, app)
                    follow_up_body = phillip_voice_text(follow_up_body, "follow_up")
                    send_smtp_message(to_address, subject_from_follow_up(app), follow_up_body)
                    timestamp = now_iso()
                    conn.execute(
                        "insert into events(application_id, kind, body, created_at) values(?, 'email_sent', ?, ?)",
                        (app_id, f"Sent follow-up email to {to_address}", timestamp),
                    )
                    conn.execute(
                        "update applications set contact_email=?, follow_up=?, follow_up_sent_at=?, updated_at=? where id=?",
                        (to_address, follow_up_body, timestamp, timestamp, app_id),
                    )
                    conn.commit()
                self.json({"ok": True})
            elif parsed.path == "/api/leads/save":
                with connect() as conn:
                    lead_id = save_company_lead(conn, data)
                    profile = get_profile(conn)
                    lead = row_to_dict(conn.execute("select * from company_leads where id=?", (lead_id,)).fetchone()) or {}
                    write_outreach_documents(profile, lead)
                self.json({"ok": True, "id": lead_id})
            elif parsed.path == "/api/leads/generate":
                lead_id = int(data.get("id"))
                with connect() as conn:
                    profile = get_profile(conn)
                    lead = row_to_dict(conn.execute("select * from company_leads where id=?", (lead_id,)).fetchone())
                    if not lead:
                        raise RuntimeError("Company lead not found")
                    updates = {}
                    for field in ["company", "industry", "contact_name", "contact_role", "contact_email", "company_notes", "contact_search_notes", "outreach_style", "website", "source_url"]:
                        if field in data:
                            updates[field] = normalize_space(str(data.get(field, "")))
                            lead[field] = updates[field]
                    outreach = compose_lead_outreach(profile, lead)
                    timestamp = now_iso()
                    conn.execute(
                        """
                        update company_leads
                        set company=?, website=?, industry=?, contact_name=?, contact_role=?,
                            contact_email=?, source_url=?, company_notes=?, contact_search_notes=?, outreach_style=?, outreach_email=?,
                            status='drafted', updated_at=?
                        where id=?
                        """,
                        (
                            lead.get("company", ""),
                            lead.get("website", ""),
                            lead.get("industry", ""),
                            lead.get("contact_name", ""),
                            lead.get("contact_role", ""),
                            lead.get("contact_email", ""),
                            lead.get("source_url", ""),
                            lead.get("company_notes", ""),
                            lead.get("contact_search_notes", ""),
                            lead.get("outreach_style", "") or "intro",
                            outreach,
                            timestamp,
                            lead_id,
                        ),
                    )
                    conn.commit()
                    refreshed = row_to_dict(conn.execute("select * from company_leads where id=?", (lead_id,)).fetchone()) or {}
                    write_outreach_documents(profile, refreshed)
                self.json({"ok": True, "outreach_email": outreach})
            elif parsed.path == "/api/leads/humanize":
                lead_id = int(data.get("id"))
                with connect() as conn:
                    lead = row_to_dict(conn.execute("select * from company_leads where id=?", (lead_id,)).fetchone())
                    if not lead:
                        raise RuntimeError("Company lead not found")
                    outreach = phillip_voice_text(str(data.get("outreach_email") or lead.get("outreach_email", "")), "outreach")
                    timestamp = now_iso()
                    conn.execute(
                        "update company_leads set outreach_email=?, updated_at=? where id=?",
                        (outreach, timestamp, lead_id),
                    )
                    conn.commit()
                    refreshed = row_to_dict(conn.execute("select * from company_leads where id=?", (lead_id,)).fetchone()) or {}
                    write_outreach_documents(get_profile(conn), refreshed)
                    check = voice_check(outreach)
                self.json({"ok": True, "outreach_email": outreach, "check": check})
            elif parsed.path == "/api/leads/status":
                lead_id = int(data.get("id"))
                status = str(data.get("status", "found"))
                do_not_contact = 1 if status == "do-not-contact" else int(bool(data.get("do_not_contact", False)))
                with connect() as conn:
                    conn.execute(
                        "update company_leads set status=?, do_not_contact=?, updated_at=? where id=?",
                        (status, do_not_contact, now_iso(), lead_id),
                    )
                    conn.commit()
                self.json({"ok": True})
            elif parsed.path == "/api/leads/send":
                lead_id = int(data.get("id"))
                to_address = str(data.get("to", ""))
                with connect() as conn:
                    profile = get_profile(conn)
                    lead = row_to_dict(conn.execute("select * from company_leads where id=?", (lead_id,)).fetchone())
                    if not lead:
                        raise RuntimeError("Company lead not found")
                    if lead.get("do_not_contact"):
                        raise RuntimeError("This lead is marked do-not-contact.")
                    if not to_address:
                        to_address = str(lead.get("contact_email", ""))
                    if not to_address:
                        raise RuntimeError("A contact email is required before sending.")
                    lead["contact_email"] = to_address
                    body = compose_lead_outreach(profile, lead)
                    body = phillip_voice_text(body, "outreach")
                    send_smtp_message(to_address, lead_subject(lead), body)
                    timestamp = now_iso()
                    next_follow_up = (dt.date.today() + dt.timedelta(days=10)).isoformat()
                    conn.execute(
                        """
                        update company_leads
                        set contact_email=?, outreach_email=?, status='sent',
                            sent_at=?, next_follow_up=?, updated_at=?
                        where id=?
                        """,
                        (to_address, body, timestamp, next_follow_up, timestamp, lead_id),
                    )
                    conn.commit()
                    refreshed = row_to_dict(conn.execute("select * from company_leads where id=?", (lead_id,)).fetchone()) or {}
                    write_outreach_documents(profile, refreshed)
                self.json({"ok": True})
            elif parsed.path == "/api/targets/save":
                with connect() as conn:
                    target_id = save_target_company(conn, data)
                self.json({"ok": True, "id": target_id})
            elif parsed.path == "/api/targets/import":
                with connect() as conn:
                    result = import_target_companies(conn, str(data.get("text", "")))
                self.json({"ok": True, **result})
            elif parsed.path == "/api/targets/seed-starter":
                with connect() as conn:
                    result = seed_starter_targets(conn)
                self.json({"ok": True, **result})
            elif parsed.path == "/api/targets/source":
                with connect() as conn:
                    result = target_company_to_source(conn, int(data.get("id")))
                self.json({"ok": True, **result})
            elif parsed.path == "/api/targets/lead":
                with connect() as conn:
                    result = target_company_to_lead(conn, int(data.get("id")))
                self.json({"ok": True, **result})
            elif parsed.path == "/api/session-memory/save":
                write_session_memory(str(data.get("content", "")))
                self.json({"ok": True, "content": read_session_memory()})
            elif parsed.path == "/api/session-memory/end-draft":
                content = generate_session_memory_draft(str(data.get("content", read_session_memory())))
                self.json({"ok": True, "content": content})
            else:
                self.error(404, "Not found")
        except Exception as exc:
            self.json({"ok": False, "error": str(exc)}, status=400)

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("content-length", "0"))
        if not length:
            return {}
        body = self.rfile.read(length).decode("utf-8")
        return json.loads(body)

    def html(self, body: str, status: int = 200) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "text/html; charset=utf-8")
        self.send_header("content-length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def json(self, payload: dict[str, Any], status: int = 200) -> None:
        encoded = json.dumps(payload, indent=2, ensure_ascii=True).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def error(self, status: int, message: str) -> None:
        self.json({"ok": False, "error": message}, status=status)

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] {fmt % args}")


PWA_MANIFEST: dict[str, Any] = {
    "name": "Job Swipe",
    "short_name": "JobSwipe",
    "description": "Swipe through jobs, like Tinder",
    "start_url": "/swipe",
    "display": "standalone",
    "background_color": "#0A0A0A",
    "theme_color": "#0A0A0A",
    "orientation": "portrait",
    "icons": [
        {"src": "https://api.dicebear.com/8.x/initials/svg?seed=JS&backgroundColor=6366f1", "sizes": "192x192", "type": "image/svg+xml"},
        {"src": "https://api.dicebear.com/8.x/initials/svg?seed=JS&backgroundColor=6366f1", "sizes": "512x512", "type": "image/svg+xml"},
    ],
}


def get_swipe_jobs() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            select id, title, company, location, url, source, description,
                   score, score_reasons, too_senior, reject_reason, created_at
            from jobs
            where status in ('new', 'shortlisted')
              and too_senior = 0
              and reject_reason = ''
            order by score desc, created_at desc
            limit 80
            """
        ).fetchall()
    jobs = []
    for row in rows:
        d = dict(row)
        desc = str(d.get("description") or "")
        d["description_snippet"] = desc[:400].strip()
        d["score"] = int(d.get("score") or 0)
        jobs.append(d)
    return jobs


SWIPE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="mobile-web-app-capable" content="yes">
<meta name="theme-color" content="#0A0A0A">
<link rel="manifest" href="/manifest.json">
<title>Job Swipe</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --like: #22c55e;
    --nope: #ef4444;
    --bg: #0A0A0A;
    --card: #ffffff;
    --text: #111827;
    --muted: #6b7280;
    --border: #f3f4f6;
    --accent: #6366f1;
  }
  html, body {
    height: 100%; width: 100%;
    background: var(--bg);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    overflow: hidden;
    touch-action: none;
  }
  #app {
    display: flex;
    flex-direction: column;
    height: 100%;
    max-width: 480px;
    margin: 0 auto;
    position: relative;
  }
  /* Header */
  #header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 20px 8px;
    flex-shrink: 0;
  }
  #header h1 {
    font-size: 22px;
    font-weight: 700;
    color: #fff;
    letter-spacing: -0.5px;
  }
  #counter {
    font-size: 13px;
    color: #6b7280;
    background: #1a1a1a;
    padding: 4px 10px;
    border-radius: 20px;
  }
  /* Card stack area */
  #stack-area {
    flex: 1;
    position: relative;
    padding: 8px 16px 0;
    overflow: hidden;
  }
  /* Individual card */
  .job-card {
    position: absolute;
    inset: 0;
    margin: 8px 0;
    background: var(--card);
    border-radius: 24px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.4);
    overflow: hidden;
    display: flex;
    flex-direction: column;
    user-select: none;
    will-change: transform;
    transition: none;
  }
  .job-card.snap-back {
    transition: transform 0.35s cubic-bezier(0.175, 0.885, 0.32, 1.275);
  }
  .job-card.fly-left {
    transition: transform 0.38s ease-in, opacity 0.38s ease-in;
    transform: translateX(-130vw) rotate(-20deg) !important;
    opacity: 0;
  }
  .job-card.fly-right {
    transition: transform 0.38s ease-in, opacity 0.38s ease-in;
    transform: translateX(130vw) rotate(20deg) !important;
    opacity: 0;
  }
  /* Card behind (scale down) */
  .job-card.behind-1 {
    transform: scale(0.95) translateY(12px);
    transition: transform 0.3s ease;
  }
  .job-card.behind-2 {
    transform: scale(0.90) translateY(24px);
    transition: transform 0.3s ease;
  }
  /* Card header */
  .card-top {
    padding: 20px 20px 12px;
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }
  .company-row {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 10px;
  }
  .company-avatar {
    width: 44px;
    height: 44px;
    border-radius: 12px;
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    font-weight: 700;
    color: #fff;
    flex-shrink: 0;
  }
  .company-meta {
    flex: 1;
    min-width: 0;
  }
  .company-name {
    font-size: 13px;
    font-weight: 600;
    color: var(--muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .source-badge {
    font-size: 11px;
    color: #9ca3af;
  }
  .job-title {
    font-size: 20px;
    font-weight: 700;
    color: var(--text);
    line-height: 1.25;
    margin-bottom: 10px;
  }
  .tags-row {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .tag {
    font-size: 12px;
    font-weight: 500;
    padding: 3px 9px;
    border-radius: 20px;
    background: #f3f4f6;
    color: #374151;
  }
  .tag.remote { background: #d1fae5; color: #065f46; }
  .tag.hybrid { background: #dbeafe; color: #1e40af; }
  .tag.onsite { background: #fef3c7; color: #92400e; }
  .tag.score-high { background: #d1fae5; color: #065f46; }
  .tag.score-mid { background: #fef9c3; color: #713f12; }
  /* Card body (description) */
  .card-body {
    flex: 1;
    overflow-y: auto;
    padding: 14px 20px;
    -webkit-overflow-scrolling: touch;
  }
  .card-body p {
    font-size: 14px;
    line-height: 1.6;
    color: #374151;
    white-space: pre-line;
  }
  /* Swipe indicators */
  .indicator {
    position: absolute;
    top: 28px;
    font-size: 28px;
    font-weight: 900;
    padding: 6px 14px;
    border-radius: 10px;
    border-width: 4px;
    border-style: solid;
    opacity: 0;
    transition: opacity 0.1s;
    pointer-events: none;
    letter-spacing: 1px;
    z-index: 10;
    transform: rotate(-15deg);
  }
  .indicator.like {
    left: 20px;
    color: var(--like);
    border-color: var(--like);
    transform: rotate(-15deg);
  }
  .indicator.nope {
    right: 20px;
    color: var(--nope);
    border-color: var(--nope);
    transform: rotate(15deg);
  }
  /* Bottom action buttons */
  #actions {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 20px;
    padding: 16px 20px 32px;
    flex-shrink: 0;
  }
  .action-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    border: none;
    cursor: pointer;
    border-radius: 50%;
    transition: transform 0.15s, box-shadow 0.15s;
    flex-shrink: 0;
  }
  .action-btn:active { transform: scale(0.9); }
  .btn-nope {
    width: 60px; height: 60px;
    background: #fff;
    box-shadow: 0 4px 20px rgba(239,68,68,0.3);
    font-size: 24px;
  }
  .btn-open {
    width: 48px; height: 48px;
    background: #1a1a1a;
    box-shadow: 0 4px 16px rgba(0,0,0,0.4);
    font-size: 18px;
  }
  .btn-like {
    width: 60px; height: 60px;
    background: #fff;
    box-shadow: 0 4px 20px rgba(34,197,94,0.3);
    font-size: 24px;
  }
  /* Empty / loading state */
  #empty-state {
    display: none;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    gap: 16px;
    color: #6b7280;
    text-align: center;
    padding: 40px;
  }
  #empty-state .empty-icon { font-size: 64px; }
  #empty-state h2 { color: #fff; font-size: 22px; font-weight: 700; }
  #empty-state p { font-size: 15px; line-height: 1.5; }
  #empty-state button {
    margin-top: 8px;
    background: var(--accent);
    color: #fff;
    border: none;
    padding: 12px 28px;
    border-radius: 40px;
    font-size: 15px;
    font-weight: 600;
    cursor: pointer;
  }
  #loading-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    gap: 12px;
    color: #6b7280;
  }
  .spinner {
    width: 36px; height: 36px;
    border: 3px solid #333;
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  /* Apply sheet */
  .apply-sheet {
    position: fixed;
    bottom: 0; left: 0; right: 0;
    background: #1c1c1e;
    border-radius: 20px 20px 0 0;
    padding: 12px 20px 48px;
    transform: translateY(100%);
    transition: transform 0.35s cubic-bezier(0.32, 0.72, 0, 1);
    z-index: 200;
    box-shadow: 0 -8px 40px rgba(0,0,0,0.6);
  }
  .apply-sheet.show { transform: translateY(0); }
  .sheet-handle {
    width: 36px; height: 4px;
    background: #444; border-radius: 2px;
    margin: 0 auto 16px;
  }
  .sheet-co { font-size: 12px; color: #888; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }
  .sheet-ttl { font-size: 18px; font-weight: 700; color: #fff; margin-bottom: 20px; line-height: 1.3; }
  .sheet-btns { display: flex; gap: 10px; }
  .sheet-apply-btn {
    flex: 1; background: var(--like); color: #fff;
    border: none; padding: 14px; border-radius: 14px;
    font-size: 16px; font-weight: 700; cursor: pointer;
  }
  .sheet-later-btn {
    background: #2a2a2a; color: #aaa;
    border: none; padding: 14px 20px; border-radius: 14px;
    font-size: 15px; font-weight: 600; cursor: pointer;
  }
  /* Toast notification */
  #toast {
    position: fixed;
    bottom: 110px;
    left: 50%;
    transform: translateX(-50%) translateY(80px);
    background: #1a1a1a;
    color: #fff;
    padding: 10px 20px;
    border-radius: 40px;
    font-size: 14px;
    font-weight: 500;
    transition: transform 0.3s ease;
    pointer-events: none;
    white-space: nowrap;
    z-index: 100;
  }
  #toast.show { transform: translateX(-50%) translateY(0); }
  /* Liked queue link */
  #liked-bar {
    display: none;
    background: #16a34a;
    color: #fff;
    text-align: center;
    padding: 10px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    text-decoration: none;
    flex-shrink: 0;
  }
  #liked-bar.show { display: block; }
</style>
</head>
<body>
<div id="app">
  <div id="header">
    <h1>Job Swipe</h1>
    <span id="counter">Loading...</span>
  </div>
  <a id="liked-bar" href="/" target="_blank">View liked jobs in desktop app ↗</a>
  <div id="stack-area">
    <div id="loading-state">
      <div class="spinner"></div>
      <span>Finding jobs...</span>
    </div>
    <div id="empty-state">
      <div class="empty-icon">🎉</div>
      <h2>You're all caught up!</h2>
      <p>No more jobs to review right now.<br>Run your sources to discover more.</p>
      <button onclick="location.reload()">Refresh</button>
    </div>
  </div>
  <div id="actions" style="display:none">
    <button class="action-btn btn-nope" onclick="swipeAction('nope')" title="Not interested">✕</button>
    <button class="action-btn btn-open" onclick="openJob()" title="Open job listing">↗</button>
    <button class="action-btn btn-like" onclick="swipeAction('like')" title="Shortlist">♥</button>
  </div>
</div>
<div id="apply-sheet" class="apply-sheet">
  <div class="sheet-handle"></div>
  <div class="sheet-co" id="sheet-co"></div>
  <div class="sheet-ttl" id="sheet-ttl"></div>
  <div class="sheet-btns">
    <button class="sheet-apply-btn" onclick="applyNow()">Apply Now →</button>
    <button class="sheet-later-btn" onclick="hideApplySheet()">Later</button>
  </div>
</div>
<div id="toast"></div>

<script>
let jobs = [];
let currentIndex = 0;
let likedCount = 0;
let isDragging = false;
let currentApplyJob = null;
let sheetTimer = null;
let startX = 0, startY = 0, lastX = 0, lastY = 0;
let cardEl = null;

const stackArea = document.getElementById('stack-area');
const actions = document.getElementById('actions');
const counter = document.getElementById('counter');
const emptyState = document.getElementById('empty-state');
const loadingState = document.getElementById('loading-state');
const likedBar = document.getElementById('liked-bar');

async function loadJobs() {
  try {
    const res = await fetch('/api/swipe/jobs');
    const data = await res.json();
    jobs = data.jobs || [];
    currentIndex = 0;
    loadingState.style.display = 'none';
    renderStack();
  } catch (e) {
    loadingState.innerHTML = '<p style="color:#ef4444">Failed to load jobs. Is the server running?</p>';
  }
}

function getRemoteTag(job) {
  const loc = (job.location || '').toLowerCase();
  const desc = (job.description_snippet || '').toLowerCase();
  if (loc.includes('remote') || desc.includes('fully remote') || desc.includes('100% remote')) return 'remote';
  if (loc.includes('hybrid') || desc.includes('hybrid')) return 'hybrid';
  return 'onsite';
}

function scoreTag(score) {
  if (score >= 70) return 'score-high';
  if (score >= 40) return 'score-mid';
  return '';
}

function companyInitial(company) {
  return (company || '?').trim().charAt(0).toUpperCase();
}

function makeCard(job, zIndex) {
  const card = document.createElement('div');
  card.className = 'job-card';
  card.style.zIndex = zIndex;

  const remote = getRemoteTag(job);
  const sc = scoreTag(job.score);
  const loc = job.location || 'Location unknown';
  const snippet = (job.description_snippet || '').replace(/\\n{3,}/g, '\\n\\n').trim();

  card.innerHTML = `
    <div class="indicator like">LIKE</div>
    <div class="indicator nope">NOPE</div>
    <div class="card-top">
      <div class="company-row">
        <div class="company-avatar">${companyInitial(job.company)}</div>
        <div class="company-meta">
          <div class="company-name">${esc(job.company)}</div>
          <div class="source-badge">${esc(job.source || '')}</div>
        </div>
      </div>
      <div class="job-title">${esc(job.title)}</div>
      <div class="tags-row">
        <span class="tag ${remote}">${remote.charAt(0).toUpperCase() + remote.slice(1)}</span>
        ${loc !== 'Location unknown' ? `<span class="tag">📍 ${esc(loc)}</span>` : ''}
        ${sc ? `<span class="tag ${sc}">Score ${job.score}</span>` : ''}
      </div>
    </div>
    <div class="card-body">
      <p>${esc(snippet) || '<span style="color:#9ca3af">No description available.</span>'}</p>
    </div>
  `;
  return card;
}

function esc(str) {
  return String(str || '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function renderStack() {
  // Remove existing cards
  stackArea.querySelectorAll('.job-card').forEach(c => c.remove());

  const remaining = jobs.slice(currentIndex);

  if (remaining.length === 0) {
    emptyState.style.display = 'flex';
    actions.style.display = 'none';
    counter.textContent = 'All done';
    return;
  }

  counter.textContent = `${remaining.length} left`;
  actions.style.display = 'flex';
  emptyState.style.display = 'none';

  // Render top 3 cards (reversed so top card is on top)
  const visible = remaining.slice(0, 3).reverse();
  visible.forEach((job, i) => {
    const realI = visible.length - 1 - i; // 0 = top card
    const card = makeCard(job, 10 + i);
    if (realI === 1) card.classList.add('behind-1');
    if (realI === 2) card.classList.add('behind-2');
    stackArea.appendChild(card);
    if (realI === 0) {
      attachDrag(card);
      cardEl = card;
    }
  });
}

function attachDrag(card) {
  let ox = 0, oy = 0;

  function onStart(x, y) {
    isDragging = true;
    startX = x; startY = y; lastX = x; lastY = y;
    card.classList.remove('snap-back');
  }

  function onMove(x, y) {
    if (!isDragging) return;
    lastX = x; lastY = y;
    ox = x - startX;
    oy = y - startY;
    const rot = ox * 0.08;
    card.style.transform = `translate(${ox}px, ${oy}px) rotate(${rot}deg)`;

    const likeEl = card.querySelector('.indicator.like');
    const nopeEl = card.querySelector('.indicator.nope');
    if (ox > 30) {
      likeEl.style.opacity = Math.min(1, (ox - 30) / 80);
      nopeEl.style.opacity = 0;
    } else if (ox < -30) {
      nopeEl.style.opacity = Math.min(1, (-ox - 30) / 80);
      likeEl.style.opacity = 0;
    } else {
      likeEl.style.opacity = 0;
      nopeEl.style.opacity = 0;
    }
  }

  function onEnd() {
    if (!isDragging) return;
    isDragging = false;
    const dx = lastX - startX;
    if (dx > 100) {
      doLike(card);
    } else if (dx < -100) {
      doNope(card);
    } else {
      card.classList.add('snap-back');
      card.style.transform = '';
      card.querySelector('.indicator.like').style.opacity = 0;
      card.querySelector('.indicator.nope').style.opacity = 0;
    }
  }

  card.addEventListener('touchstart', e => {
    if (e.target.closest('.card-body')) return; // allow scroll in body
    onStart(e.touches[0].clientX, e.touches[0].clientY);
  }, { passive: true });
  card.addEventListener('touchmove', e => {
    if (!isDragging) return;
    e.preventDefault();
    onMove(e.touches[0].clientX, e.touches[0].clientY);
  }, { passive: false });
  card.addEventListener('touchend', () => onEnd());

  // Mouse support for desktop testing
  card.addEventListener('mousedown', e => {
    if (e.target.closest('.card-body')) return;
    onStart(e.clientX, e.clientY);
    const move = ev => onMove(ev.clientX, ev.clientY);
    const up = () => { onEnd(); window.removeEventListener('mousemove', move); window.removeEventListener('mouseup', up); };
    window.addEventListener('mousemove', move);
    window.addEventListener('mouseup', up);
  });
}

async function doLike(card) {
  const job = jobs[currentIndex];
  card.classList.add('fly-right');
  await api('/api/jobs/status', { id: job.id, status: 'shortlisted' });
  likedCount++;
  likedBar.classList.add('show');
  likedBar.textContent = `♥ ${likedCount} saved`;
  showApplySheet(job);
  advance();
}

function showApplySheet(job) {
  currentApplyJob = job;
  document.getElementById('sheet-co').textContent = job.company || '';
  document.getElementById('sheet-ttl').textContent = job.title || '';
  document.getElementById('apply-sheet').classList.add('show');
  clearTimeout(sheetTimer);
  sheetTimer = setTimeout(hideApplySheet, 7000);
}

function hideApplySheet() {
  document.getElementById('apply-sheet').classList.remove('show');
  currentApplyJob = null;
}

function applyNow() {
  if (currentApplyJob && currentApplyJob.url) window.open(currentApplyJob.url, '_blank');
  hideApplySheet();
}

async function doNope(card) {
  const job = jobs[currentIndex];
  card.classList.add('fly-left');
  await api('/api/jobs/status', { id: job.id, status: 'rejected', reject_reason: 'swiped left' });
  toast('Passed');
  advance();
}

function advance() {
  currentIndex++;
  setTimeout(() => renderStack(), 380);
}

function openJob() {
  if (currentIndex >= jobs.length) return;
  const job = jobs[currentIndex];
  if (job.url) window.open(job.url, '_blank');
  else toast('No URL for this job');
}

function swipeAction(dir) {
  if (!cardEl || currentIndex >= jobs.length) return;
  if (dir === 'like') doLike(cardEl);
  else doNope(cardEl);
}

async function api(path, body) {
  try {
    await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  } catch (e) { /* fire and forget */ }
}

let toastTimer;
function toast(msg) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 1800);
}

loadJobs();
</script>
</body>
</html>"""


def get_state() -> dict[str, Any]:
    with connect() as conn:
        profile = get_profile(conn)
        jobs = [row_to_dict(row) for row in conn.execute("select * from jobs order by score desc, created_at desc").fetchall()]
        apps = [
            row_to_dict(row)
            for row in conn.execute(
                """
                select applications.*, jobs.title, jobs.company, jobs.url, jobs.location
                from applications
                join jobs on jobs.id = applications.job_id
                order by applications.updated_at desc
                """
            ).fetchall()
        ]
        for app in apps:
            report = form_prep_report_for_app(app)
            if report:
                app["form_prep_report"] = report
            app["form_prep_overrides_map"] = parse_form_prep_overrides(str(app.get("form_prep_overrides", "")))
            app["platform"] = detect_application_platform(str(app.get("url", "")), str(app.get("source", "")))
            app["manual_first"] = app["platform"] in MANUAL_FIRST_PLATFORMS
            job_stub = {
                "id": app.get("job_id"),
                "company": app.get("company", ""),
                "title": app.get("title", ""),
            }
            app["documents_folder"] = str(application_documents_folder(job_stub))
            app["document_artifacts"] = build_application_artifacts(job_stub, app, profile)
        blocked_domains = active_domain_blockers(conn)
        throttled_domains = active_domain_rate_limits(conn)
        ats_stats = ats_prep_stats(conn)
        rejection_stats = rejection_reason_stats(conn)
        leads = [
            row_to_dict(row)
            for row in conn.execute("select * from company_leads order by updated_at desc, created_at desc").fetchall()
        ]
        for lead in leads:
            lead["subject_preview"] = lead_subject(lead)
            lead["readiness"] = outreach_readiness(lead)
            lead["contact_search_links"] = lead_contact_search_links(lead)
            lead["documents_folder"] = str(outreach_documents_folder(lead))
            lead["document_artifacts"] = build_outreach_artifacts(lead)
        sources = [
            row_to_dict(row)
            for row in conn.execute("select * from job_sources order by enabled desc, updated_at desc").fetchall()
        ]
        targets = [
            row_to_dict(row)
            for row in conn.execute("select * from target_companies order by priority desc, updated_at desc").fetchall()
        ]
        cv_versions = [
            row_to_dict(row)
            for row in conn.execute("select * from cv_versions order by is_default desc, name").fetchall()
        ]
        for cv in cv_versions:
            file_path = str(cv.get("file_path", "") or "")
            cv["file_exists"] = bool(file_path and Path(file_path).exists())
            cv["file_name"] = Path(file_path).name if file_path else ""
        answer_bank = [
            row_to_dict(row)
            for row in conn.execute("select * from answer_bank order by category, question_key").fetchall()
        ]
        story_bank = [
            row_to_dict(row)
            for row in conn.execute("select * from story_bank order by category, title").fetchall()
        ]
        automation_runs = [
            row_to_dict(row)
            for row in conn.execute("select * from automation_runs order by created_at desc limit 10").fetchall()
        ]
        form_feedback = [
            row_to_dict(row)
            for row in conn.execute(
                """
                select form_fill_feedback.*, applications.job_id, jobs.title, jobs.company
                from form_fill_feedback
                join applications on applications.id = form_fill_feedback.application_id
                join jobs on jobs.id = applications.job_id
                order by form_fill_feedback.created_at desc
                limit 50
                """
            ).fetchall()
        ]
        inbox_messages = [
            row_to_dict(row)
            for row in conn.execute(
                """
                select inbox_messages.*,
                       jobs.title as application_title,
                       jobs.company as application_company,
                       company_leads.company as lead_company
                from inbox_messages
                left join applications on applications.id = inbox_messages.application_id
                left join jobs on jobs.id = applications.job_id
                left join company_leads on company_leads.id = inbox_messages.lead_id
                order by inbox_messages.received_at desc, inbox_messages.created_at desc
                limit 80
                """
            ).fetchall()
        ]
        site_credentials = []
        for row in conn.execute("select * from site_credentials order by enabled desc, updated_at desc, domain").fetchall():
            credential = row_to_dict(row) or {}
            credential["password_set"] = password_is_saved_for_credential(credential)
            site_credentials.append(credential)
    return {
        "profile": profile,
        "jobs": jobs,
        "applications": apps,
        "leads": leads,
        "sources": sources,
        "targets": targets,
        "cv_versions": cv_versions,
        "answer_bank": answer_bank,
        "story_bank": story_bank,
        "automation_runs": automation_runs,
        "form_feedback": form_feedback,
        "form_feedback_recommendations": feedback_recommendations(form_feedback),
        "source_cleanup": source_cleanup_recommendations(conn),
        "email": email_config_status(),
        "inbox": inbox_config_status(),
        "inbox_messages": inbox_messages,
        "site_credentials": site_credentials,
        "blocked_domains": blocked_domains,
        "throttled_domains": throttled_domains,
        "ats_prep_stats": ats_stats,
        "rejection_reason_stats": rejection_stats,
        "session_memory": read_session_memory(),
    }


def search_links() -> dict[str, str]:
    query = urllib.parse.quote("marketing sports fitness outdoor remote South Africa")
    return {
        "LinkedIn marketing search": f"https://www.linkedin.com/jobs/search/?keywords={query}",
        "Indeed marketing search": f"https://za.indeed.com/jobs?q={query}",
        "Google company career search": f"https://www.google.com/search?q={query}+site%3Agreenhouse.io+OR+site%3Alever.co+OR+site%3Aashbyhq.com",
        "Remote OK marketing": "https://remoteok.com/remote-marketing-jobs",
        "Arbeitnow remote jobs": "https://www.arbeitnow.com/jobs/remote",
        "Wellfound marketing": "https://wellfound.com/jobs",
    }


INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Job Application AI</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/lucide/0.263.1/lucide.min.js">
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#0A0A0A;--surface:#141414;--surface2:#1E1E1E;--border:#2A2A2A;
  --text:#F0F0F0;--muted:#888;--accent:#6366f1;--accent2:#818cf8;
  --green:#22c55e;--red:#ef4444;--yellow:#f59e0b;--blue:#3b82f6;
}
html,body{height:100%;background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;overflow:hidden}
a{color:inherit;text-decoration:none}
button{cursor:pointer;font-family:inherit}
input,textarea,select{font-family:inherit}

/* Layout */
#root{display:flex;height:100vh}
#sidebar{
  width:220px;flex-shrink:0;
  background:var(--surface);
  border-right:1px solid var(--border);
  display:flex;flex-direction:column;
  padding:0;
}
#main{flex:1;overflow-y:auto;background:var(--bg)}

/* Sidebar */
.sidebar-brand{
  padding:20px 20px 16px;
  font-size:18px;font-weight:800;
  color:var(--text);letter-spacing:-0.5px;
  border-bottom:1px solid var(--border);
}
.sidebar-brand span{color:var(--accent)}
.nav-section{padding:12px 10px 4px;flex:1}
.nav-btn{
  display:flex;align-items:center;gap:10px;
  width:100%;padding:10px 12px;
  border:none;background:transparent;color:var(--muted);
  border-radius:10px;font-size:14px;font-weight:500;
  margin-bottom:2px;text-align:left;
  transition:background 0.15s,color 0.15s;
}
.nav-btn:hover{background:var(--surface2);color:var(--text)}
.nav-btn.active{background:var(--accent);color:#fff}
.nav-btn .nb{margin-left:auto;background:rgba(255,255,255,0.15);padding:2px 7px;border-radius:20px;font-size:11px;font-weight:700}
.nav-btn:not(.active) .nb{background:var(--surface2);color:var(--muted)}
.nav-swipe{
  display:flex;align-items:center;gap:10px;
  width:calc(100% - 20px);margin:10px;
  padding:11px 14px;
  background:var(--accent);color:#fff;
  border:none;border-radius:12px;
  font-size:14px;font-weight:700;
  justify-content:center;
}
.nav-swipe:hover{background:var(--accent2)}
.sidebar-footer{
  padding:12px 16px;
  border-top:1px solid var(--border);
  font-size:12px;color:var(--muted);
}

/* Tab content */
.tab{display:none;padding:32px 40px;min-height:100%}
.tab.active{display:block}

/* Section header */
.sec-header{
  display:flex;align-items:center;justify-content:space-between;
  margin-bottom:28px;
  padding-bottom:20px;
  border-bottom:1px solid var(--border);
}
.sec-title{font-size:26px;font-weight:800;letter-spacing:-0.5px}
.sec-count{
  display:inline-block;margin-left:10px;
  background:var(--surface2);color:var(--muted);
  padding:3px 10px;border-radius:20px;font-size:14px;font-weight:600;
}
.sec-actions{display:flex;gap:10px;align-items:center}

/* Buttons */
.btn{
  padding:9px 18px;border:none;border-radius:10px;
  font-size:14px;font-weight:600;cursor:pointer;
  transition:opacity 0.15s,transform 0.1s;
}
.btn:active{transform:scale(0.97)}
.btn-primary{background:var(--accent);color:#fff}
.btn-primary:hover{background:var(--accent2)}
.btn-ghost{background:var(--surface2);color:var(--text)}
.btn-ghost:hover{background:var(--border)}
.btn-danger{background:rgba(239,68,68,0.15);color:var(--red)}
.btn-success{background:rgba(34,197,94,0.15);color:var(--green)}
.btn-sm{padding:6px 12px;font-size:13px;border-radius:8px;border:none;font-weight:600;cursor:pointer}

/* Empty state */
.empty{
  display:flex;flex-direction:column;align-items:center;
  justify-content:center;padding:80px 40px;gap:14px;text-align:center;
}
.empty-icon{font-size:52px}
.empty h2{font-size:20px;font-weight:700}
.empty p{color:var(--muted);font-size:15px;line-height:1.5}

/* Job grid (Queue) */
.job-grid{
  display:grid;
  grid-template-columns:repeat(auto-fill,minmax(300px,1fr));
  gap:16px;
}
.jcard{
  background:var(--surface);border:1px solid var(--border);
  border-radius:16px;padding:20px;
  display:flex;flex-direction:column;gap:14px;
  transition:border-color 0.15s;
}
.jcard:hover{border-color:#444}
.jcard-top{display:flex;gap:12px;align-items:flex-start}
.jcard-avatar{
  width:44px;height:44px;border-radius:12px;flex-shrink:0;
  background:linear-gradient(135deg,#6366f1,#8b5cf6);
  display:flex;align-items:center;justify-content:center;
  font-size:18px;font-weight:800;color:#fff;
}
.jcard-meta{flex:1;min-width:0}
.jcard-company{font-size:12px;font-weight:600;color:var(--muted);margin-bottom:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.jcard-title{font-size:15px;font-weight:700;line-height:1.3;color:var(--text)}
.jcard-loc{font-size:12px;color:var(--muted);margin-top:3px}
.jcard-tags{display:flex;flex-wrap:wrap;gap:6px}
.tag{font-size:11px;font-weight:600;padding:3px 8px;border-radius:20px}
.tag-remote{background:rgba(34,197,94,0.15);color:var(--green)}
.tag-hybrid{background:rgba(59,130,246,0.15);color:var(--blue)}
.tag-onsite{background:rgba(245,158,11,0.15);color:var(--yellow)}
.tag-score{background:rgba(99,102,241,0.15);color:var(--accent2)}
.jcard-actions{display:flex;gap:8px;margin-top:auto}
.btn-apply{
  flex:1;background:var(--green);color:#fff;
  border:none;padding:10px;border-radius:10px;
  font-size:14px;font-weight:700;cursor:pointer;
}
.btn-apply:hover{background:#16a34a}
.btn-remove{
  background:var(--surface2);color:var(--muted);
  border:none;padding:10px 14px;border-radius:10px;
  font-size:13px;font-weight:600;cursor:pointer;
}

/* Applied list */
.app-list{display:flex;flex-direction:column;gap:10px}
.app-row{
  background:var(--surface);border:1px solid var(--border);
  border-radius:14px;padding:18px 20px;
  display:flex;align-items:center;gap:16px;
}
.app-row.follow-up-due{border-color:var(--yellow)}
.status-badge{
  font-size:11px;font-weight:700;padding:4px 10px;
  border-radius:20px;white-space:nowrap;flex-shrink:0;
}
.status-submitted{background:rgba(34,197,94,0.15);color:var(--green)}
.status-draft{background:rgba(136,136,136,0.15);color:var(--muted)}
.status-due{background:rgba(245,158,11,0.25);color:var(--yellow)}
.app-info{flex:1;min-width:0}
.app-title{font-size:15px;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.app-company{font-size:13px;color:var(--muted);margin-top:2px}
.app-right{display:flex;flex-direction:column;align-items:flex-end;gap:6px;flex-shrink:0}
.app-date{font-size:12px;color:var(--muted)}
.app-btns{display:flex;gap:6px}

/* Sources */
.sources-list{display:flex;flex-direction:column;gap:8px;margin-bottom:32px}
.source-row{
  background:var(--surface);border:1px solid var(--border);
  border-radius:12px;padding:14px 18px;
  display:flex;align-items:center;gap:14px;
}
.source-row.disabled{opacity:0.5}
.source-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.source-dot.on{background:var(--green)}
.source-dot.off{background:var(--muted)}
.source-info{flex:1;min-width:0}
.source-name{font-size:14px;font-weight:600}
.source-meta{font-size:12px;color:var(--muted);margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.source-actions{display:flex;gap:6px;flex-shrink:0}

/* Add source form */
.add-source-card{
  background:var(--surface);border:1px solid var(--border);
  border-radius:14px;padding:24px;
}
.add-source-card h3{font-size:16px;font-weight:700;margin-bottom:16px}
.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.form-group{display:flex;flex-direction:column;gap:6px}
.form-group.full{grid-column:1/-1}
.form-label{font-size:12px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:0.5px}
.form-input,.form-select,.form-textarea{
  background:var(--surface2);border:1px solid var(--border);
  border-radius:8px;padding:10px 12px;
  color:var(--text);font-size:14px;
  transition:border-color 0.15s;
}
.form-input:focus,.form-select:focus,.form-textarea:focus{
  outline:none;border-color:var(--accent);
}
.form-select option{background:var(--surface2)}
.form-textarea{resize:vertical;min-height:80px}

/* Profile form */
.profile-card{
  background:var(--surface);border:1px solid var(--border);
  border-radius:16px;padding:28px;
  max-width:640px;
}
.profile-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px}
.profile-grid .full{grid-column:1/-1}

/* Toast */
#toast{
  position:fixed;bottom:24px;left:50%;transform:translateX(-50%) translateY(80px);
  background:#1c1c1e;color:#fff;padding:10px 20px;border-radius:40px;
  font-size:14px;font-weight:500;transition:transform 0.3s ease;
  pointer-events:none;white-space:nowrap;z-index:999;
  box-shadow:0 4px 24px rgba(0,0,0,0.4);
}
#toast.show{transform:translateX(-50%) translateY(0)}

/* Spinner */
.spinner{
  width:20px;height:20px;border:2px solid var(--border);
  border-top-color:var(--accent);border-radius:50%;
  animation:spin 0.7s linear infinite;display:inline-block;
}
@keyframes spin{to{transform:rotate(360deg)}}

/* Run all progress */
#run-progress{
  background:var(--surface);border:1px solid var(--border);
  border-radius:12px;padding:16px 20px;margin-bottom:16px;
  font-size:14px;color:var(--muted);display:none;
}
#run-progress.active{display:flex;align-items:center;gap:12px}
</style>
</head>
<body>
<div id="root">

  <nav id="sidebar">
    <div class="sidebar-brand">Job<span>Swipe</span></div>
    <div class="nav-section">
      <button class="nav-swipe" onclick="location.href='/swipe'">🃏 Swipe for Jobs</button>
      <button class="nav-btn active" data-tab="queue" onclick="switchTab('queue',this)">
        ❤️ Apply Queue <span class="nb" id="nb-queue"></span>
      </button>
      <button class="nav-btn" data-tab="applied" onclick="switchTab('applied',this)">
        ✅ Applied <span class="nb" id="nb-applied"></span>
      </button>
      <button class="nav-btn" data-tab="sources" onclick="switchTab('sources',this)">
        📡 Sources
      </button>
      <button class="nav-btn" data-tab="profile" onclick="switchTab('profile',this)">
        👤 Profile
      </button>
    </div>
    <div class="sidebar-footer" id="sidebar-status">Loading...</div>
  </nav>

  <main id="main">

    <!-- QUEUE -->
    <div id="tab-queue" class="tab active">
      <div class="sec-header">
        <div><span class="sec-title">Apply Queue</span><span class="sec-count" id="q-count">0</span></div>
        <div class="sec-actions">
          <button class="btn btn-ghost" onclick="location.href='/swipe'">+ Swipe more</button>
        </div>
      </div>
      <div id="queue-body"></div>
    </div>

    <!-- APPLIED -->
    <div id="tab-applied" class="tab">
      <div class="sec-header">
        <div><span class="sec-title">Applied</span><span class="sec-count" id="a-count">0</span></div>
      </div>
      <div id="applied-body"></div>
    </div>

    <!-- SOURCES -->
    <div id="tab-sources" class="tab">
      <div class="sec-header">
        <div><span class="sec-title">Sources</span></div>
        <div class="sec-actions">
          <button class="btn btn-primary" onclick="runAll()">▶ Run All</button>
        </div>
      </div>
      <div id="run-progress"><div class="spinner"></div><span id="run-msg">Running all sources...</span></div>
      <div id="sources-body"></div>
      <div class="add-source-card" style="margin-top:24px">
        <h3>Add New Source</h3>
        <div class="form-grid">
          <div class="form-group">
            <label class="form-label">Name</label>
            <input class="form-input" id="s-name" placeholder="e.g. Takealot Careers">
          </div>
          <div class="form-group">
            <label class="form-label">Type</label>
            <select class="form-select" id="s-type" onchange="updateSourceHints()">
              <optgroup label="ATS Boards">
                <option value="greenhouse">Greenhouse</option>
                <option value="lever">Lever</option>
                <option value="ashby">Ashby</option>
                <option value="smartrecruiters">SmartRecruiters</option>
                <option value="recruitee">Recruitee</option>
                <option value="workable">Workable</option>
                <option value="teamtailor">Teamtailor</option>
              </optgroup>
              <optgroup label="Job Board Feeds">
                <option value="jobicy_rss">Jobicy RSS</option>
                <option value="remotive">Remotive</option>
                <option value="arbeitnow">Arbeitnow</option>
                <option value="adzuna">Adzuna SA</option>
                <option value="indeed_rss">Indeed RSS</option>
                <option value="weworkremotely_rss">WeWorkRemotely RSS</option>
              </optgroup>
              <optgroup label="Careers Pages">
                <option value="public">Public Careers Page</option>
                <option value="direct">Direct URL</option>
              </optgroup>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label" id="s-token-label">Board Token / URL</label>
            <input class="form-input" id="s-token" placeholder="e.g. takealot">
          </div>
          <div class="form-group">
            <label class="form-label">Search Query (optional)</label>
            <input class="form-input" id="s-query" placeholder="e.g. marketing">
          </div>
        </div>
        <div style="margin-top:14px">
          <button class="btn btn-primary" onclick="addSource()">Add Source</button>
        </div>
      </div>
    </div>

    <!-- PROFILE -->
    <div id="tab-profile" class="tab">
      <div class="sec-header">
        <div><span class="sec-title">Profile</span></div>
        <div class="sec-actions">
          <button class="btn btn-primary" onclick="saveProfile()">Save Profile</button>
        </div>
      </div>
      <div class="profile-card">
        <div class="profile-grid">
          <div class="form-group">
            <label class="form-label">Full Name</label>
            <input class="form-input" id="p-full_name">
          </div>
          <div class="form-group">
            <label class="form-label">Email</label>
            <input class="form-input" id="p-email" type="email">
          </div>
          <div class="form-group">
            <label class="form-label">Phone</label>
            <input class="form-input" id="p-phone">
          </div>
          <div class="form-group">
            <label class="form-label">Location</label>
            <input class="form-input" id="p-location">
          </div>
          <div class="form-group">
            <label class="form-label">LinkedIn URL</label>
            <input class="form-input" id="p-linkedin_url">
          </div>
          <div class="form-group">
            <label class="form-label">Portfolio URL</label>
            <input class="form-input" id="p-portfolio_url">
          </div>
          <div class="form-group full">
            <label class="form-label">Salary Expectation</label>
            <input class="form-input" id="p-salary_expectation" placeholder="e.g. R22,000/month">
          </div>
          <div class="form-group full">
            <label class="form-label">CV Text (paste your CV content here)</label>
            <textarea class="form-textarea" id="p-cv_text" rows="12" style="min-height:200px"></textarea>
          </div>
        </div>
      </div>
    </div>

  </main>
</div>
<div id="toast"></div>

<script>
'use strict';
let state = {};
let currentTab = 'queue';
let toastTimer;

// ── Tab switching ──────────────────────────────
function switchTab(tab, btn) {
  currentTab = tab;
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.id === 'tab-' + tab));
  render();
}

// ── Load & render ──────────────────────────────
async function load() {
  try {
    const res = await fetch('/api/state');
    state = await res.json();
    render();
  } catch(e) {
    toast('Failed to load data', true);
  }
}

function render() {
  updateCounts();
  if (currentTab === 'queue') renderQueue();
  else if (currentTab === 'applied') renderApplied();
  else if (currentTab === 'sources') renderSources();
  else if (currentTab === 'profile') renderProfile();
}

function updateCounts() {
  const jobs = state.jobs || [];
  const apps = state.apps || [];
  const shortlisted = jobs.filter(j => j.status === 'shortlisted').length;
  const swipeable = jobs.filter(j => j.status === 'new').length;
  nb('nb-queue', shortlisted);
  nb('nb-applied', apps.length);
  const totalSrcs = (state.sources || []).filter(s => s.enabled).length;
  document.getElementById('sidebar-status').textContent =
    `${swipeable} jobs to swipe · ${totalSrcs} sources active`;
}

function nb(id, n) {
  const el = document.getElementById(id);
  if (el) el.textContent = n > 0 ? n : '';
}

// ── Queue ──────────────────────────────────────
function renderQueue() {
  const jobs = (state.jobs || []).filter(j => j.status === 'shortlisted');
  const body = document.getElementById('queue-body');
  const countEl = document.getElementById('q-count');
  countEl.textContent = jobs.length;

  if (!jobs.length) {
    body.innerHTML = `<div class="empty">
      <div class="empty-icon">🃏</div>
      <h2>Queue is empty</h2>
      <p>Swipe right on jobs you like and they'll appear here.</p>
      <button class="btn btn-primary" onclick="location.href='/swipe'" style="margin-top:8px">Go swipe</button>
    </div>`;
    return;
  }

  body.innerHTML = `<div class="job-grid">${jobs.map(jobCard).join('')}</div>`;
}

function jobCard(job) {
  const init = (job.company || '?').charAt(0).toUpperCase();
  const remote = remoteTag(job);
  return `<div class="jcard" id="jc-${job.id}">
    <div class="jcard-top">
      <div class="jcard-avatar">${init}</div>
      <div class="jcard-meta">
        <div class="jcard-company">${esc(job.company)}</div>
        <div class="jcard-title">${esc(job.title)}</div>
        <div class="jcard-loc">${esc(job.location || '')}</div>
      </div>
    </div>
    <div class="jcard-tags">
      <span class="tag tag-${remote}">${remote}</span>
      ${job.score >= 50 ? `<span class="tag tag-score">Score ${job.score}</span>` : ''}
      ${job.source ? `<span class="tag" style="background:var(--surface2);color:var(--muted)">${esc(job.source)}</span>` : ''}
    </div>
    <div class="jcard-actions">
      <button class="btn-apply" onclick="applyJob(${job.id},${JSON.stringify(job.url||'')})">Open &amp; Apply →</button>
      <button class="btn-remove" onclick="removeJob(${job.id})">✕</button>
    </div>
  </div>`;
}

function remoteTag(job) {
  const t = ((job.location||'')+(job.description||'')).toLowerCase();
  if (t.includes('remote')) return 'remote';
  if (t.includes('hybrid')) return 'hybrid';
  return 'onsite';
}

async function applyJob(id, url) {
  if (url) window.open(url, '_blank');
  await post('/api/jobs/status', {id, status: 'applied'});
  document.getElementById('jc-'+id)?.remove();
  const remaining = document.querySelectorAll('.jcard').length;
  document.getElementById('q-count').textContent = remaining;
  toast('Marked as applied ✓');
}

async function removeJob(id) {
  await post('/api/jobs/status', {id, status: 'rejected', reject_reason: 'removed from queue'});
  document.getElementById('jc-'+id)?.remove();
  const remaining = document.querySelectorAll('.jcard').length;
  document.getElementById('q-count').textContent = remaining;
  toast('Removed');
}

// ── Applied ────────────────────────────────────
function renderApplied() {
  const apps = state.apps || [];
  const body = document.getElementById('applied-body');
  document.getElementById('a-count').textContent = apps.length;

  if (!apps.length) {
    body.innerHTML = `<div class="empty"><div class="empty-icon">📋</div><h2>No applications yet</h2><p>Apply to jobs from your queue to track them here.</p></div>`;
    return;
  }

  const today = new Date().toISOString().split('T')[0];
  const sorted = [...apps].sort((a,b) => {
    const ad = a.next_follow_up && a.next_follow_up <= today;
    const bd = b.next_follow_up && b.next_follow_up <= today;
    if (ad && !bd) return -1;
    if (!ad && bd) return 1;
    return (b.updated_at||'').localeCompare(a.updated_at||'');
  });

  body.innerHTML = `<div class="app-list">${sorted.map(a => appRow(a, today)).join('')}</div>`;
}

function appRow(app, today) {
  const due = app.next_follow_up && app.next_follow_up <= today;
  const submitted = (app.status === 'submitted') || ((state.jobs||[]).find(j=>j.id===app.job_id)?.status === 'applied');
  const cls = due ? 'status-due' : submitted ? 'status-submitted' : 'status-draft';
  const label = due ? '⚠ Follow-up due' : submitted ? 'Submitted' : 'Draft';
  const followUpHref = app.follow_up
    ? `mailto:${esc(app.contact_email||'')}?subject=${encodeURIComponent('Following up on my application — '+app.title)}&body=${encodeURIComponent(app.follow_up)}`
    : null;

  return `<div class="app-row${due?' follow-up-due':''}">
    <span class="status-badge ${cls}">${label}</span>
    <div class="app-info">
      <div class="app-title">${esc(app.title||'Untitled')}</div>
      <div class="app-company">${esc(app.company||'')}${app.location?' · '+esc(app.location):''}</div>
    </div>
    <div class="app-right">
      ${app.next_follow_up ? `<div class="app-date">Follow-up: ${app.next_follow_up}</div>` : ''}
      <div class="app-btns">
        ${app.url ? `<a href="${esc(app.url)}" target="_blank" class="btn btn-ghost btn-sm">View job</a>` : ''}
        ${due && followUpHref ? `<a href="${followUpHref}" class="btn btn-sm" style="background:rgba(245,158,11,0.2);color:var(--yellow)">Send follow-up</a>` : ''}
        ${!submitted ? `<button class="btn btn-sm btn-success" onclick="markSubmitted(${app.job_id})">Mark submitted</button>` : ''}
      </div>
    </div>
  </div>`;
}

async function markSubmitted(jobId) {
  await post('/api/jobs/status', {id: jobId, status: 'applied'});
  toast('Marked as submitted ✓');
  await load();
}

// ── Sources ────────────────────────────────────
function renderSources() {
  const sources = state.sources || [];
  const body = document.getElementById('sources-body');

  if (!sources.length) {
    body.innerHTML = `<div class="empty"><p>No sources yet. Add one below.</p></div>`;
    return;
  }

  body.innerHTML = `<div class="sources-list">${sources.map(sourceRow).join('')}</div>`;
}

function sourceRow(s) {
  const on = !!s.enabled;
  const lastRun = s.last_run ? s.last_run.split('T')[0] : 'Never';
  const result = s.last_result ? ` · ${s.last_result}` : '';
  return `<div class="source-row${on?'':' disabled'}" id="src-${s.id}">
    <div class="source-dot ${on?'on':'off'}"></div>
    <div class="source-info">
      <div class="source-name">${esc(s.name||s.token||s.source_type)}</div>
      <div class="source-meta">${esc(s.source_type)} · Last run: ${lastRun}${esc(result)}</div>
    </div>
    <div class="source-actions">
      <button class="btn btn-ghost btn-sm" onclick="runSource(${s.id}, this)">▶ Run</button>
      <button class="btn btn-sm ${on?'btn-danger':'btn-success'}" onclick="toggleSource(${s.id}, ${on?0:1})">${on?'Disable':'Enable'}</button>
    </div>
  </div>`;
}

async function runSource(id, btn) {
  const orig = btn.textContent;
  btn.textContent = '...';
  btn.disabled = true;
  try {
    const res = await post('/api/sources/run', {id});
    toast(res.message || res.result || 'Done');
    await load();
  } catch(e) { toast('Error running source', true); }
  finally { btn.textContent = orig; btn.disabled = false; }
}

async function toggleSource(id, enabled) {
  await post('/api/sources/toggle', {id, enabled});
  await load();
}

async function runAll() {
  const prog = document.getElementById('run-progress');
  const msg = document.getElementById('run-msg');
  prog.classList.add('active');
  msg.textContent = 'Running all sources...';
  try {
    const res = await post('/api/sources/run-all', {});
    msg.textContent = res.message || 'Done!';
    await load();
    setTimeout(() => prog.classList.remove('active'), 3000);
  } catch(e) {
    msg.textContent = 'Error running sources';
    setTimeout(() => prog.classList.remove('active'), 3000);
  }
}

function updateSourceHints() {
  const type = document.getElementById('s-type').value;
  const hints = {
    greenhouse: 'Board token (e.g. takealot)',
    lever: 'Company slug (e.g. buffer)',
    ashby: 'Board name (e.g. canva)',
    smartrecruiters: 'Company ID',
    recruitee: 'Subdomain',
    workable: 'Subdomain',
    teamtailor: 'Subdomain',
    jobicy_rss: 'Category (e.g. marketing)',
    remotive: 'Category (e.g. marketing)',
    arbeitnow: 'Leave blank or enter tag',
    adzuna: 'Search query (e.g. marketing cape town)',
    indeed_rss: 'Search query',
    weworkremotely_rss: 'Leave blank',
    public: 'Careers page URL',
    direct: 'Direct job URL',
  };
  document.getElementById('s-token').placeholder = hints[type] || '';
  document.getElementById('s-token-label').textContent =
    ['public','direct'].includes(type) ? 'URL' : 'Board Token / Slug';
}

async function addSource() {
  const name = document.getElementById('s-name').value.trim();
  const type = document.getElementById('s-type').value;
  const token = document.getElementById('s-token').value.trim();
  const query = document.getElementById('s-query').value.trim();
  if (!token && !['arbeitnow','weworkremotely_rss','remotive'].includes(type)) {
    toast('Please enter a board token or URL', true); return;
  }
  await post('/api/sources/save', {name: name||token, source_type: type, token, query, enabled: 1});
  document.getElementById('s-name').value = '';
  document.getElementById('s-token').value = '';
  document.getElementById('s-query').value = '';
  toast('Source added ✓');
  await load();
}

// ── Profile ────────────────────────────────────
function renderProfile() {
  const p = state.profile || {};
  const fields = ['full_name','email','phone','location','linkedin_url','portfolio_url','salary_expectation','cv_text'];
  fields.forEach(f => {
    const el = document.getElementById('p-'+f);
    if (el) el.value = p[f] || '';
  });
}

async function saveProfile() {
  const fields = ['full_name','email','phone','location','linkedin_url','portfolio_url','salary_expectation','cv_text'];
  const data = {};
  fields.forEach(f => {
    const el = document.getElementById('p-'+f);
    if (el) data[f] = el.value;
  });
  await post('/api/profile', data);
  toast('Profile saved ✓');
}

// ── Helpers ────────────────────────────────────
function esc(str) {
  return String(str||'').replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

async function post(path, body) {
  const res = await fetch(path, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  return res.json();
}

function toast(msg, err=false) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.style.background = err ? '#7f1d1d' : '#1c1c1e';
  el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 2400);
}

load();
</script>
</body>
</html>"""


def main() -> int:
    init_db()
    server = ThreadingHTTPServer((HOST, PORT), AppHandler)
    scheduler = threading.Thread(target=discovery_scheduler, daemon=True)
    scheduler.start()
    print(f"Job Application AI running at http://{HOST}:{PORT}")
    print(f"Database: {DB_PATH}")
    print("Automatic discovery scheduler is active while this app is running.")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
