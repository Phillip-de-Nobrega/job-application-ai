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
REMINDERS_DIR = DATA_DIR / "reminders"
NOTIFIED_REMINDERS_PATH = REMINDERS_DIR / "notified-reminders.json"
DB_PATH = DATA_DIR / "job_application_ai.sqlite3"
ENV_PATH = ROOT / ".env"
SESSION_MEMORY_PATH = ROOT / "SESSION_MEMORY.md"
HOST = "127.0.0.1"
PORT = int(os.environ.get("JOB_AI_PORT", "8765"))
DISCOVERY_CHECK_SECONDS = 600

CV_PATH = "/Users/phillip/Desktop/PHILLIP PERSONAL/Phillip_de_Nobrega_CV.pdf"


DEFAULT_PROFILE: dict[str, str] = {
    "full_name": "Phillip de Nobrega",
    "email": "Phillip2002@mweb.co.za",
    "phone": "+27 71 643 0185",
    "location": "Cape Town, South Africa",
    "cv_path": CV_PATH,
    "cv_text": "",
    "portfolio_url": "",
    "linkedin_url": "https://linkedin.com/in/phillip-de-nobrega-87542b353",
    "target_roles": "Marketing roles, especially outdoor, sports, fitness, brand, content, social media, growth, partnerships, community, and campaign roles.",
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


MARKETING_KEYWORDS = {
    "marketing": 8,
    "brand": 8,
    "campaign": 7,
    "content": 7,
    "social media": 7,
    "community": 6,
    "growth": 6,
    "performance marketing": 7,
    "seo": 5,
    "email marketing": 5,
    "crm": 5,
    "copywriting": 6,
    "partnership": 6,
    "influencer": 5,
    "events": 5,
    "analytics": 5,
    "google analytics": 5,
    "paid media": 6,
    "meta ads": 5,
    "tiktok": 4,
    "instagram": 4,
    "creative": 5,
    "consumer": 4,
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
]

MARKETING_TITLE_SIGNALS = [
    "marketing",
    "brand",
    "content",
    "social",
    "growth",
    "community",
    "communications",
    "campaign",
    "partnership",
    "advertising",
    "creative strategist",
    "copywriter",
]

NON_TARGET_TITLE_SIGNALS = [
    "engineer",
    "developer",
    "designer",
    "product manager",
    "project coordinator",
    "project manager",
    "account executive",
    "accounting",
    "customer success",
    "sales ",
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
    "warehouse",
    "retail associate",
    "sales assistant",
]

HARD_NON_TARGET_TITLE_SIGNALS = [
    "content reviewer",
    "online data analyst",
    "data analyst",
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
        "query": "",
    },
    {
        "name": "Sweatpals fitness community",
        "source_type": "ashby",
        "token": "sweatpals",
        "query": "",
    },
    {
        "name": "Eight Sleep sleep fitness",
        "source_type": "ashby",
        "token": "eightsleep",
        "query": "",
    },
    {
        "name": "Avida fitness coaching",
        "source_type": "ashby",
        "token": "avida",
        "query": "",
    },
    {
        "name": "TeamSnap sports platform",
        "source_type": "lever",
        "token": "teamsnap",
        "query": "",
    },
    {
        "name": "WHOOP performance wearable",
        "source_type": "lever",
        "token": "whoop",
        "query": "",
    },
    {
        "name": "Sporty Group sports media",
        "source_type": "lever",
        "token": "sporty",
        "query": "",
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
        "query": "marketing brand content community social media",
    },
    {
        "name": "Remotive remote growth",
        "source_type": "remotive",
        "token": "marketing",
        "query": "growth campaign performance marketing",
    },
    {
        "name": "Remote OK marketing",
        "source_type": "remoteok",
        "token": "marketing",
        "query": "marketing brand content social media community copywriter",
    },
    {
        "name": "Arbeitnow Europe remote marketing",
        "source_type": "arbeitnow",
        "token": "public",
        "query": "marketing brand content social media community copywriter growth",
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
    if senior_hits:
        delta -= 22
        concerns.append("Possible seniority mismatch: " + ", ".join(senior_hits[:4]))
    elif "manager" in lower_title and not any(term in lower_title for term in ["assistant", "junior", "intern"]):
        delta -= 8
        concerns.append("Manager title may be above graduate/junior level; review requirements.")

    hard_non_target_hits = [term for term in HARD_NON_TARGET_TITLE_SIGNALS if term in lower_title]
    if hard_non_target_hits:
        delta -= 45
        concerns.append("Role-title mismatch for marketing target: " + ", ".join(hard_non_target_hits[:4]))

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
    elif remote and remote_location_restricted and not remote_location_allowed:
        delta -= 20
        concerns.append("Remote role appears restricted to locations outside Phillip's Cape Town/USA/UK/Europe target; avoid unless eligibility is clear.")
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
    total = max(0, min(100, total))
    return total, "\n".join(reasons), "\n".join(concerns)


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
        existing = conn.execute("select id from jobs where url = ?", (url,)).fetchone()
    else:
        existing = None
    if existing:
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


def discover_greenhouse(conn: sqlite3.Connection, board_token: str) -> dict[str, Any]:
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
        ids.append(
            upsert_job(
                conn,
                {
                    "title": item.get("title", ""),
                    "company": payload.get("name", board_token),
                    "location": location,
                    "url": job_url,
                    "source": f"greenhouse:{board_token}",
                    "description": plain_text_from_html(item.get("content", "")),
                    "raw_json": item,
                },
            )
        )
    return {"count": len(ids), "ids": ids}


def discover_lever(conn: sqlite3.Connection, site: str) -> dict[str, Any]:
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
        ids.append(
            upsert_job(
                conn,
                {
                    "title": item.get("text", ""),
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


def discover_ashby(conn: sqlite3.Connection, board: str) -> dict[str, Any]:
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
        ids.append(
            upsert_job(
                conn,
                {
                    "title": item.get("title", ""),
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
        job_url = (
            detail.get("ref")
            or detail.get("applyUrl")
            or detail.get("postingUrl")
            or item.get("ref")
            or item.get("postingUrl")
            or ""
        )
        ids.append(
            upsert_job(
                conn,
                {
                    "title": detail.get("name") or item.get("name") or "",
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


def discover_recruitee(conn: sqlite3.Connection, subdomain: str) -> dict[str, Any]:
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
                    "title": item.get("title", ""),
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
        if any(term in title.lower() for term in HARD_NON_TARGET_TITLE_SIGNALS + ["engineer", "developer", "backend", "frontend", "devops"]):
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
        if any(term in title.lower() for term in HARD_NON_TARGET_TITLE_SIGNALS + ["engineer", "developer", "backend", "frontend", "devops"]):
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
    if source_type == "greenhouse":
        result = discover_greenhouse(conn, token)
    elif source_type == "lever":
        result = discover_lever(conn, token)
    elif source_type == "ashby":
        result = discover_ashby(conn, token)
    elif source_type == "smartrecruiters":
        result = discover_smartrecruiters(conn, token, query)
    elif source_type == "recruitee":
        result = discover_recruitee(conn, token)
    elif source_type == "remotive":
        result = discover_remotive(conn, token or "marketing", query)
    elif source_type == "remoteok":
        result = discover_remoteok(conn, token, query)
    elif source_type == "arbeitnow":
        result = discover_arbeitnow(conn, token, query)
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
        where status in ('new', 'shortlisted')
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
          and lower(concerns) not like '%remote role appears restricted%'
          and lower(concerns) not like '%would require relocation%'
          and lower(concerns) not like '%local/eu work authorization%'
          and lower(concerns) not like '%us non-remote%'
          and lower(concerns) not like '%hybrid role may require%'
        order by
          case when lower(location) like '%remote%' then 1 else 0 end desc,
          case when lower(location) like '%cape town%' or lower(location) like '%western cape%' then 1 else 0 end desc,
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


def generate_drafts_for_jobs(conn: sqlite3.Connection, status: str = "shortlisted", limit: int = 5) -> dict[str, Any]:
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
        app_id = generate_application(conn, job_id)
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


def source_cleanup_recommendations(conn: sqlite3.Connection) -> list[dict[str, Any]]:
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
                if int(payload.get("count", 0)) == 0:
                    reason = "Last run imported 0 jobs."
                    action = "review-query"
            except Exception:
                pass
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
    ids = [int(rec["id"]) for rec in recs if rec.get("action") == "pause-or-fix" and rec.get("enabled")]
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
    preferred = profile.get("preferred_industries", "")
    targets = profile.get("target_roles", "")
    cv_text = profile.get("cv_text", "").strip()
    evidence = summarize_profile_evidence(cv_text)
    company_angle = company_angle_from_job(job.get("description", ""))

    return phillip_voice_text(textwrap.dedent(
        f"""
        Dear {company} hiring team,

        I am applying for the {title} role because it sits close to the kind of marketing work I am targeting: {targets}

        My strongest fit is the combination of marketing judgement, practical execution, and interest in brands connected to {preferred.lower()} {evidence}

        From the role description, the priorities appear to include {company_angle}. I would approach this by focusing on clear audience insight, strong campaign execution, measurable outcomes, and brand consistency across the customer journey.

        I would welcome the chance to discuss how my background can support {company}'s marketing goals.

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
    return phillip_voice_text(textwrap.dedent(
        f"""
        Why are you interested in this role?
        I am interested in the {title} role because it aligns with my focus on practical marketing work, brand building, campaign execution, and customer-facing growth. {company} appears to need someone who can understand the audience, communicate clearly, and execute with consistency.

        Why should we hire you?
        I bring a focused marketing mindset, strong interest in sports/fitness/outdoor and consumer brands, and a practical approach to turning ideas into useful campaigns, content, and customer engagement. I would keep the work commercially grounded, brand-aware, and measurable.

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
    if job_url and is_useful_company_url(job_url):
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


def is_useful_company_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.lower().replace("www.", "")
    if not parsed.scheme.startswith("http") or not host:
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
        company_line = f"The role stood out because it connects with practical, audience-focused marketing work and brand execution."
    background_line = (
        "My background combines a UCT Business Science Marketing degree, Google Analytics certification, "
        "hands-on social content work, market research, and a strong personal connection to sport and endurance training."
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


def compose_cold_outreach(profile: dict[str, str], company: str, contact_name: str = "", company_notes: str = "") -> str:
    sender_name = profile.get("full_name", "Phillip de Nobrega")
    greeting = f"Hi {contact_name}," if contact_name else f"Hi {company} team,"
    reason = company_notes or "your brand and the way it connects with its audience"
    return phillip_voice_text(textwrap.dedent(
        f"""
        {greeting}

        I am reaching out because I have been following {company} and was drawn to {reason}. I am a UCT Business Science Marketing graduate with experience across content creation, market research, brand strategy, Google Analytics, Meta Ads Manager, Canva, and AI-assisted product development.

        I am especially interested in outdoor, sport, fitness, wellness, and consumer brands where practical marketing work can support real community and customer engagement. If there is a useful way for me to contribute, I would appreciate the chance to introduce myself properly.

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
    body = compose_cold_outreach(profile, company, contact_name, company_notes)
    if contact_role:
        body = body.replace(
            "I am reaching out because",
            f"I noticed your work as {contact_role}. I am reaching out because",
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
    return f"Marketing graduate interested in {company}"


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
        "status",
        "outreach_email",
        "next_follow_up",
    ]
    values = {field: normalize_space(str(data.get(field, ""))) for field in fields}
    values["status"] = values["status"] or "found"
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


def generate_application(conn: sqlite3.Connection, job_id: int) -> int:
    profile = get_profile(conn)
    job = row_to_dict(conn.execute("select * from jobs where id = ?", (job_id,)).fetchone())
    if not job:
        raise RuntimeError("Job not found")
    app_id = ensure_application(conn, job_id)
    cover = generate_cover_letter(profile, job)
    cv_notes = generate_cv_notes(profile, job)
    answers = generate_answers(profile, job)
    follow = generate_follow_up(profile, job)
    research_notes, research_sources, research_url = generate_application_research(job)
    next_follow_up = (dt.date.today() + dt.timedelta(days=7)).isoformat()
    timestamp = now_iso()
    conn.execute(
        """
        update applications
        set cover_letter=?, cv_notes=?, answers=?, follow_up=?, research_notes=?,
            research_sources=?, research_url=?, next_follow_up=?, updated_at=?
        where id=?
        """,
        (cover, cv_notes, answers, follow, research_notes, research_sources, research_url, next_follow_up, timestamp, app_id),
    )
    conn.execute(
        "update jobs set status='drafted', updated_at=? where id=? and status in ('new', 'shortlisted')",
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


def write_application_documents(job: dict[str, Any], application: dict[str, Any]) -> None:
    folder = DOCS_DIR / f"{safe_filename(str(job.get('company', 'company')))}-{safe_filename(str(job.get('title', 'role')))}-{job.get('id')}"
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

    write_application_documents(job, app)
    task = {
        "created_at": now_iso(),
        "profile": profile,
        "job": {
            "id": job.get("id"),
            "title": job.get("title", ""),
            "company": job.get("company", ""),
            "location": job.get("location", ""),
            "url": job.get("url", ""),
            "source": job.get("source", ""),
        },
        "application": {
            "id": app.get("id"),
            "cover_letter": app.get("cover_letter", ""),
            "answers": app.get("answers", ""),
            "cv_notes": app.get("cv_notes", ""),
            "contact_email": app.get("contact_email", ""),
            "contact_name": app.get("contact_name", ""),
        },
        "rules": {
            "final_submit": "Never click final submit. Stop for user review.",
            "captcha": "Do not bypass CAPTCHA, MFA, login challenges, rate limits, or anti-bot systems.",
        },
    }
    task_path = TASK_DIR / f"application-{app_id}-{dt.datetime.now().strftime('%Y%m%d%H%M%S')}.json"
    task_path.write_text(json.dumps(task, indent=2, ensure_ascii=True), encoding="utf-8")
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
    task = {
        "created_at": now_iso(),
        "profile": profile,
        "job": {
            **job,
            "url": html_path.as_uri(),
            "source": "local-smoke-test",
        },
        "application": {
            "id": "smoke",
            "cover_letter": app.get("cover_letter") or "Local smoke-test cover letter.",
            "answers": app.get("answers") or "Local smoke-test questionnaire answers.",
            "cv_notes": app.get("cv_notes", ""),
            "contact_email": "",
            "contact_name": "",
        },
        "rules": {
            "final_submit": "Never click final submit. This is a local smoke test.",
            "captcha": "No CAPTCHA or login is present in this local test.",
        },
    }
    task_path = TASK_DIR / f"smoke-test-{dt.datetime.now().strftime('%Y%m%d%H%M%S')}.json"
    task_path.write_text(json.dumps(task, indent=2, ensure_ascii=True), encoding="utf-8")
    return task_path


def launch_form_filler(task_path: Path) -> int:
    script = ROOT / "scripts" / "form_filler.js"
    if not script.exists():
        raise RuntimeError("Form filler script is missing.")
    node_modules = ROOT / "node_modules" / "playwright"
    if not node_modules.exists():
        raise RuntimeError("Playwright is not installed yet. Run npm install first.")
    log_base = LOG_DIR / f"form-fill-{task_path.stem}"
    stdout = (log_base.with_suffix(".out.log")).open("a", encoding="utf-8")
    stderr = (log_base.with_suffix(".err.log")).open("a", encoding="utf-8")
    process = subprocess.Popen(
        ["node", str(script), "--task", str(task_path)],
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

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/":
            self.html(INDEX_HTML)
        elif parsed.path == "/api/state":
            self.json(get_state())
        elif parsed.path == "/api/open-searches":
            self.json(search_links())
        elif parsed.path == "/api/session-memory":
            self.json({"ok": True, "content": read_session_memory()})
        else:
            self.error(404, "Not found")

    def do_POST(self) -> None:
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
                query = str(data.get("query", "")).strip()
                if not token:
                    raise RuntimeError("Missing board token/site name")
                with connect() as conn:
                    if source == "greenhouse":
                        result = discover_greenhouse(conn, token)
                    elif source == "lever":
                        result = discover_lever(conn, token)
                    elif source == "ashby":
                        result = discover_ashby(conn, token)
                    elif source == "smartrecruiters":
                        result = discover_smartrecruiters(conn, token, query)
                    elif source == "recruitee":
                        result = discover_recruitee(conn, token)
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
            elif parsed.path == "/api/jobs/shortlist-top":
                limit = int(data.get("limit") or 5)
                with connect() as conn:
                    result = shortlist_top_jobs(conn, limit)
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
            elif parsed.path == "/api/applications/save":
                with connect() as conn:
                    app_id = int(data.get("id"))
                    fields = [
                        "status",
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
                self.json({"ok": True, "id": lead_id})
            elif parsed.path == "/api/leads/generate":
                lead_id = int(data.get("id"))
                with connect() as conn:
                    profile = get_profile(conn)
                    lead = row_to_dict(conn.execute("select * from company_leads where id=?", (lead_id,)).fetchone())
                    if not lead:
                        raise RuntimeError("Company lead not found")
                    updates = {}
                    for field in ["company", "industry", "contact_name", "contact_role", "contact_email", "company_notes", "website", "source_url"]:
                        if field in data:
                            updates[field] = normalize_space(str(data.get(field, "")))
                            lead[field] = updates[field]
                    outreach = compose_lead_outreach(profile, lead)
                    timestamp = now_iso()
                    conn.execute(
                        """
                        update company_leads
                        set company=?, website=?, industry=?, contact_name=?, contact_role=?,
                            contact_email=?, source_url=?, company_notes=?, outreach_email=?,
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
                            outreach,
                            timestamp,
                            lead_id,
                        ),
                    )
                    conn.commit()
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
        leads = [
            row_to_dict(row)
            for row in conn.execute("select * from company_leads order by updated_at desc, created_at desc").fetchall()
        ]
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
  <style>
    :root {
      color-scheme: light;
      --ink: #15202b;
      --muted: #5b6775;
      --line: #d7dde5;
      --soft: #f4f7f9;
      --panel: #ffffff;
      --accent: #087f8c;
      --accent-2: #b35c00;
      --danger: #a52828;
      --good: #1f7a45;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: #eef3f4;
      line-height: 1.4;
    }
    header {
      position: sticky;
      top: 0;
      z-index: 5;
      background: #ffffff;
      border-bottom: 1px solid var(--line);
    }
    .topbar {
      max-width: 1320px;
      margin: 0 auto;
      padding: 16px 20px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }
    h1 { margin: 0; font-size: 22px; }
    .sub { color: var(--muted); font-size: 13px; }
    nav { display: flex; gap: 8px; flex-wrap: wrap; }
    nav button, .btn {
      border: 1px solid var(--line);
      background: #fff;
      color: var(--ink);
      padding: 9px 12px;
      border-radius: 6px;
      cursor: pointer;
      font: inherit;
      min-height: 38px;
    }
    nav button.active, .btn.primary {
      background: var(--accent);
      border-color: var(--accent);
      color: white;
    }
    .btn.warn { background: var(--accent-2); border-color: var(--accent-2); color: white; }
    main {
      max-width: 1320px;
      margin: 0 auto;
      padding: 20px;
    }
    section { display: none; }
    section.active { display: block; }
    .grid {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(340px, 420px);
      gap: 16px;
      align-items: start;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
    }
    .panel + .panel { margin-top: 16px; }
    h2 { margin: 0 0 12px; font-size: 18px; }
    h3 { margin: 0 0 8px; font-size: 15px; }
    label {
      display: block;
      font-weight: 650;
      font-size: 13px;
      margin: 12px 0 6px;
    }
    input, select, textarea {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px;
      font: inherit;
      background: #fff;
      color: var(--ink);
    }
    textarea { min-height: 120px; resize: vertical; }
    .row { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
    .actions { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-top: 12px; }
    .jobs { display: grid; gap: 10px; }
    .job {
      border: 1px solid var(--line);
      background: #fff;
      border-radius: 8px;
      padding: 14px;
      display: grid;
      grid-template-columns: 88px minmax(0, 1fr);
      gap: 12px;
    }
    .score {
      width: 72px;
      height: 72px;
      display: grid;
      place-items: center;
      border-radius: 50%;
      border: 6px solid var(--accent);
      font-size: 20px;
      font-weight: 800;
    }
    .score.low { border-color: var(--danger); }
    .score.mid { border-color: var(--accent-2); }
    .meta { color: var(--muted); font-size: 13px; overflow-wrap: anywhere; }
    .tag {
      display: inline-flex;
      align-items: center;
      min-height: 24px;
      padding: 2px 8px;
      border-radius: 999px;
      background: var(--soft);
      border: 1px solid var(--line);
      font-size: 12px;
      color: var(--muted);
      margin-right: 4px;
      margin-top: 6px;
    }
    pre {
      white-space: pre-wrap;
      background: var(--soft);
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 12px;
      overflow: auto;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 13px;
    }
    .notice {
      border-left: 4px solid var(--accent-2);
      background: #fff7ed;
      padding: 12px;
      margin-bottom: 16px;
      border-radius: 6px;
      color: #4a2c0a;
    }
    .reminder {
      border: 1px solid var(--line);
      background: #ffffff;
      border-radius: 6px;
      padding: 12px;
      margin-top: 10px;
    }
    .metric-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 16px;
    }
    .metric {
      border: 1px solid var(--line);
      background: #fff;
      border-radius: 8px;
      padding: 12px;
      min-height: 82px;
    }
    .metric strong {
      display: block;
      font-size: 24px;
      line-height: 1.1;
      margin-bottom: 4px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
      background: #fff;
    }
    th, td {
      border-bottom: 1px solid var(--line);
      padding: 9px 8px;
      text-align: left;
      vertical-align: top;
    }
    th { color: var(--muted); font-weight: 700; }
    .ok { color: var(--good); }
    .bad { color: var(--danger); }
    .muted { color: var(--muted); }
    a { color: #075985; }
    .hidden { display: none; }
    @media (max-width: 920px) {
      .grid, .row, .metric-grid { grid-template-columns: 1fr; }
      .job { grid-template-columns: 1fr; }
      .score { width: 60px; height: 60px; }
    }
  </style>
</head>
<body>
  <header>
    <div class="topbar">
      <div>
        <h1>Job Application AI</h1>
        <div class="sub">Local, supervised marketing job assistant</div>
      </div>
      <nav>
        <button data-tab="dashboard" class="active">Dashboard</button>
        <button data-tab="profile">Profile</button>
        <button data-tab="discover">Discover</button>
        <button data-tab="targets">Targets</button>
        <button data-tab="jobs">Jobs</button>
        <button data-tab="applications">Applications</button>
        <button data-tab="outreach">Outreach</button>
        <button data-tab="auto">Auto Mode</button>
        <button data-tab="analytics">Analytics</button>
        <button data-tab="email">Email</button>
        <button data-tab="session">Session</button>
      </nav>
    </div>
  </header>

  <main>
    <div id="message"></div>

    <section id="dashboard" class="active">
      <div class="notice">
        This assistant prepares and tracks applications. It stops before final submission and does not bypass CAPTCHA, login, rate limits, or platform restrictions.
      </div>
      <div class="grid">
        <div>
          <div class="panel">
            <h2>Today</h2>
            <div id="summary"></div>
            <div class="actions">
              <button class="btn primary" onclick="runDailyWorkflow()">Run daily workflow</button>
              <button class="btn primary" onclick="showTab('discover')">Find roles</button>
              <button class="btn" onclick="showTab('jobs')">Review queue</button>
              <button class="btn" onclick="showTab('applications')">Application drafts</button>
            </div>
          </div>
          <div class="panel">
            <h2>Daily Review</h2>
            <div id="dailyReview"></div>
          </div>
        </div>
        <div class="panel">
          <h2>Guided Searches</h2>
          <div id="searchLinks"></div>
        </div>
        <div class="panel">
          <h2>Source Health</h2>
          <div id="dashboardSourceHealth"></div>
        </div>
      </div>
    </section>

    <section id="profile">
      <div class="panel">
        <h2>Profile Vault</h2>
        <div class="row">
          <div><label>Full name</label><input id="profile_full_name"></div>
          <div><label>Email</label><input id="profile_email"></div>
          <div><label>Phone</label><input id="profile_phone"></div>
          <div><label>Location</label><input id="profile_location"></div>
          <div><label>LinkedIn URL</label><input id="profile_linkedin_url"></div>
          <div><label>Portfolio URL</label><input id="profile_portfolio_url"></div>
        </div>
        <label>CV path</label><input id="profile_cv_path">
        <label>CV/profile text</label><textarea id="profile_cv_text" style="min-height:220px"></textarea>
        <div class="row">
          <div><label>Target roles</label><textarea id="profile_target_roles"></textarea></div>
          <div><label>Preferred industries</label><textarea id="profile_preferred_industries"></textarea></div>
          <div><label>Target locations</label><textarea id="profile_target_locations"></textarea></div>
          <div><label>Work authorization</label><textarea id="profile_work_authorization"></textarea></div>
          <div><label>Salary expectation</label><textarea id="profile_salary_expectation"></textarea></div>
          <div><label>Salary target ZAR/month</label><input id="profile_salary_target_zar_monthly"></div>
          <div><label>Availability</label><textarea id="profile_availability"></textarea></div>
          <div><label>Notice period</label><textarea id="profile_notice_period"></textarea></div>
          <div><label>Relocation</label><textarea id="profile_relocation"></textarea></div>
          <div><label>Demographics policy</label><textarea id="profile_demographics_policy"></textarea></div>
          <div><label>References policy</label><textarea id="profile_references_policy"></textarea></div>
          <div><label>Email provider</label><input id="profile_email_provider"></div>
          <div><label>Tone</label><textarea id="profile_tone"></textarea></div>
          <div><label>Email/CV sending voice</label><textarea id="profile_email_voice"></textarea></div>
          <div><label>Writing sample document path</label><input id="profile_writing_sample_path" placeholder="/Users/phillip/Desktop/..."></div>
        </div>
        <label>Writing sample text</label><textarea id="profile_writing_sample_text" style="min-height:180px" placeholder="Paste something you wrote naturally, or add a document path above and extract it."></textarea>
        <label>Writing style notes</label><textarea id="profile_writing_style_notes" style="min-height:140px"></textarea>
        <div class="actions">
          <button class="btn primary" onclick="saveProfile()">Save profile</button>
          <button class="btn" onclick="extractCv()">Try CV extraction</button>
          <button class="btn" onclick="extractWritingSample()">Extract/analyse writing sample</button>
        </div>
      </div>
    </section>

    <section id="discover">
      <div class="grid">
        <div>
          <div class="panel">
            <h2>ATS Discovery</h2>
            <p class="muted">Use public board tokens/site names. Examples: a Greenhouse board token from boards.greenhouse.io/company, a Lever site from jobs.lever.co/company, or an Ashby board name.</p>
            <div class="row">
              <div>
                <label>Source</label>
                <select id="discover_source">
                  <option value="greenhouse">Greenhouse</option>
                  <option value="lever">Lever</option>
                  <option value="ashby">Ashby</option>
                  <option value="smartrecruiters">SmartRecruiters</option>
                  <option value="recruitee">Recruitee</option>
                  <option value="careers">Public careers page</option>
                </select>
              </div>
              <div><label>Board token / site name</label><input id="discover_token" placeholder="company-name"></div>
            </div>
            <label>Optional search query</label><input id="discover_query" placeholder="marketing OR social media">
            <div class="actions">
              <button class="btn primary" onclick="discover()">Import jobs</button>
            </div>
          </div>
          <div class="panel">
            <h2>Automatic Sources</h2>
            <p class="muted">Saved sources rerun once per day while this local app is open. Use ATS board tokens/company identifiers or a direct careers URL.</p>
            <div class="row">
              <div><label>Name</label><input id="source_name" placeholder="Nike Greenhouse"></div>
              <div>
                <label>Type</label>
                <select id="source_type">
                  <option value="greenhouse">Greenhouse</option>
                  <option value="lever">Lever</option>
                  <option value="ashby">Ashby</option>
                  <option value="smartrecruiters">SmartRecruiters</option>
                  <option value="recruitee">Recruitee</option>
                  <option value="remotive">Remotive remote jobs</option>
                  <option value="remoteok">Remote OK remote jobs</option>
                  <option value="arbeitnow">Arbeitnow Europe remote jobs</option>
                  <option value="careers">Public careers page</option>
                  <option value="workable">Workable careers page</option>
                  <option value="teamtailor">Teamtailor careers page</option>
                  <option value="url">Direct URL</option>
                </select>
              </div>
            </div>
            <label>Token / company identifier / URL</label><input id="source_token" placeholder="company-name, Workable subdomain, Teamtailor URL, or https://...">
            <label>Optional query</label><input id="source_query" placeholder="marketing, brand, social media">
            <label><input id="source_enabled" type="checkbox" style="width:auto" checked> Enabled for daily discovery</label>
            <div class="actions">
              <button class="btn primary" onclick="saveSource()">Save source</button>
              <button class="btn" onclick="seedStarterSources()">Seed starter sources</button>
              <button class="btn" onclick="runAllSources()">Run all enabled now</button>
            </div>
            <div id="sourceList"></div>
          </div>
          <div class="panel">
            <h2>Add Job URL</h2>
            <label>Job URL</label><input id="url_import" placeholder="https://...">
            <div class="actions">
              <button class="btn primary" onclick="importUrl()">Fetch URL</button>
            </div>
          </div>
          <div class="panel">
            <h2>Import Job Alert</h2>
            <p class="muted">Paste a LinkedIn, Indeed, Google Alert, recruiter, or company job-alert email. The app extracts job links and saves them for scoring/review without scraping protected pages.</p>
            <label>Alert source</label><input id="alert_source" value="email-alert">
            <label>Alert email/text</label><textarea id="alert_text" style="min-height:220px" placeholder="Paste the full job alert email or saved-search text here."></textarea>
            <div class="actions">
              <button class="btn primary" onclick="importAlert()">Import alert links</button>
            </div>
          </div>
          <div class="panel">
            <h2>Add Job Manually</h2>
            <div class="row">
              <div><label>Title</label><input id="manual_title"></div>
              <div><label>Company</label><input id="manual_company"></div>
              <div><label>Location</label><input id="manual_location"></div>
              <div><label>Source URL</label><input id="manual_url"></div>
            </div>
            <label>Description</label><textarea id="manual_description" style="min-height:220px"></textarea>
            <div class="actions">
              <button class="btn primary" onclick="addManualJob()">Save job</button>
            </div>
          </div>
        </div>
        <div class="panel">
          <h2>Source Notes</h2>
          <p>LinkedIn and Indeed are best used here as guided/manual sources: open searches, save promising jobs, paste the job URL or description, then let this app draft and track the application.</p>
          <p>For company career pages and ATS boards, use the URL importer or public API import where available.</p>
          <div id="discoverLinks"></div>
          <h2 style="margin-top:18px">Source Health</h2>
          <div id="discoverSourceHealth"></div>
        </div>
      </div>
    </section>

    <section id="targets">
      <div class="grid">
        <div>
          <div class="panel">
            <h2>Target Companies</h2>
            <p class="muted">Keep the 20-50 companies you actively want to track. Convert a target into an automatic source when you have a careers URL or ATS token, or into an outreach lead when no role is advertised.</p>
            <input id="target_id" type="hidden">
            <div class="row">
              <div><label>Company</label><input id="target_company" placeholder="Red Bull"></div>
              <div><label>Website</label><input id="target_website" placeholder="https://..."></div>
              <div><label>Careers URL</label><input id="target_careers_url" placeholder="https://company.com/careers"></div>
              <div><label>Industry</label><input id="target_industry" placeholder="Sports, fitness, outdoor"></div>
              <div>
                <label>Priority</label>
                <select id="target_priority">
                  <option value="5">5 - dream fit</option>
                  <option value="4">4 - strong fit</option>
                  <option value="3" selected>3 - worth tracking</option>
                  <option value="2">2 - occasional</option>
                  <option value="1">1 - low priority</option>
                </select>
              </div>
              <div>
                <label>Status</label>
                <select id="target_status">
                  <option value="target">target</option>
                  <option value="sourcing">sourcing</option>
                  <option value="outreach-ready">outreach-ready</option>
                  <option value="paused">paused</option>
                </select>
              </div>
              <div>
                <label>Source type</label>
                <select id="target_source_type">
                  <option value="">Auto/direct URL</option>
                  <option value="greenhouse">Greenhouse</option>
                  <option value="lever">Lever</option>
                  <option value="ashby">Ashby</option>
                  <option value="smartrecruiters">SmartRecruiters</option>
                  <option value="recruitee">Recruitee</option>
                  <option value="remotive">Remotive remote jobs</option>
                  <option value="remoteok">Remote OK remote jobs</option>
                  <option value="arbeitnow">Arbeitnow Europe remote jobs</option>
                  <option value="careers">Public careers page</option>
                  <option value="workable">Workable careers page</option>
                  <option value="teamtailor">Teamtailor careers page</option>
                  <option value="url">Direct URL</option>
                </select>
              </div>
              <div><label>ATS token / source token</label><input id="target_source_token" placeholder="company-name or board token"></div>
            </div>
            <label>Source query</label><input id="target_source_query" value="marketing">
            <label>Notes / why they fit</label><textarea id="target_notes" placeholder="Specific products, campaigns, community, brand angle, or contact ideas."></textarea>
            <div class="actions">
              <button class="btn primary" onclick="saveTarget()">Save target</button>
              <button class="btn" onclick="clearTargetForm()">New target</button>
              <button class="btn" onclick="seedStarterTargets()">Seed starter targets</button>
            </div>
          </div>
          <div class="panel">
            <h2>Bulk Import</h2>
            <p class="muted">One company per line. Format: Company | website | industry | careers URL | notes</p>
            <textarea id="target_bulk" placeholder="Salomon | https://www.salomon.com | Outdoor sports | https://www.salomon.com/careers | Trail running and outdoor brand"></textarea>
            <div class="actions">
              <button class="btn primary" onclick="importTargets()">Import targets</button>
            </div>
          </div>
        </div>
        <div class="panel">
          <h2>Target List</h2>
          <div id="targetList"></div>
        </div>
      </div>
    </section>

    <section id="jobs">
      <div class="panel">
        <h2>Job Queue</h2>
        <div class="actions">
          <select id="job_filter" onchange="renderJobs()">
            <option value="">All statuses</option>
            <option value="new">New</option>
            <option value="shortlisted">Shortlisted</option>
            <option value="drafted">Drafted</option>
            <option value="applied">Applied</option>
            <option value="rejected">Rejected</option>
          </select>
          <button class="btn" onclick="rescoreJobs()">Rescore jobs</button>
          <button class="btn primary" onclick="shortlistTopJobs()">Shortlist top 5</button>
          <button class="btn" onclick="generateShortlistDrafts()">Generate shortlist drafts</button>
        </div>
        <div id="jobList" class="jobs"></div>
      </div>
    </section>

    <section id="applications">
      <div class="grid">
        <div class="panel">
          <h2>Application Drafts</h2>
          <div class="actions">
            <button class="btn" onclick="runFormFillSmokeTest()">Run form-fill smoke test</button>
          </div>
          <div id="applicationList"></div>
        </div>
        <div class="panel">
          <h2>Edit Draft</h2>
          <div id="applicationEditor" class="muted">Select an application draft.</div>
        </div>
      </div>
    </section>

    <section id="outreach">
      <div class="grid">
        <div>
          <div class="panel">
            <h2>Company Outreach</h2>
            <div class="notice">
              Cold outreach is review-first. Do not use this for bulk email. Save only relevant companies and do not contact anyone who opts out.
            </div>
            <div class="row">
              <div><label>Company</label><input id="lead_company"></div>
              <div><label>Website</label><input id="lead_website" placeholder="https://..."></div>
              <div><label>Industry</label><input id="lead_industry" placeholder="Outdoor, fitness, sport, consumer brand"></div>
              <div><label>Source URL</label><input id="lead_source_url" placeholder="Where you found them"></div>
              <div><label>Contact name</label><input id="lead_contact_name"></div>
              <div><label>Contact role</label><input id="lead_contact_role"></div>
            </div>
            <label>Contact email</label><input id="lead_contact_email" placeholder="owner@company.com">
            <label>Why this company / personalization notes</label><textarea id="lead_company_notes" placeholder="Specific product, campaign, brand angle, community, or reason you fit."></textarea>
            <div class="actions">
              <button class="btn primary" onclick="saveLead()">Save lead</button>
            </div>
          </div>
          <div class="panel">
            <h2>Lead Queue</h2>
            <div id="leadList"></div>
          </div>
        </div>
        <div class="panel">
          <h2>Edit Outreach</h2>
          <div id="leadEditor" class="muted">Select a company lead.</div>
        </div>
      </div>
    </section>

    <section id="analytics">
      <div class="panel">
        <h2>Analytics</h2>
        <div id="analyticsOverview"></div>
      </div>
      <div class="grid">
        <div>
          <div class="panel">
            <h2>Application Funnel</h2>
            <div id="analyticsFunnel"></div>
          </div>
          <div class="panel">
            <h2>Source Quality</h2>
            <div id="analyticsSources"></div>
          </div>
        </div>
        <div>
          <div class="panel">
            <h2>Follow-up Health</h2>
            <div id="analyticsFollowups"></div>
          </div>
          <div class="panel">
            <h2>Replies And Outcomes</h2>
            <div id="analyticsReplies"></div>
          </div>
          <div class="panel">
            <h2>Recommendations</h2>
            <div id="analyticsRecommendations"></div>
          </div>
        </div>
      </div>
    </section>

    <section id="auto">
      <div class="grid">
        <div>
          <div class="panel">
            <h2>Automatic Mode</h2>
            <div class="notice">
              Automatic mode prepares the work queue, but it does not submit applications or send emails. Final submission and final send stay manual.
            </div>
            <label>Daily application target</label><input id="auto_limit" value="5" type="number" min="1" max="15">
            <div class="actions">
              <button class="btn primary" onclick="runAutomaticMode()">Run automatic mode</button>
              <button class="btn" onclick="exportReminders()">Export reminder calendar</button>
              <button class="btn" onclick="notifyDueReminders()">Notify due now</button>
              <button class="btn" onclick="showTab('dashboard')">Review Daily Review</button>
              <button class="btn" onclick="showTab('analytics')">View Analytics</button>
            </div>
            <div id="autoStatus"></div>
          </div>
          <div class="panel">
            <h2>Latest Runs</h2>
            <div id="automationRuns"></div>
          </div>
          <div class="panel">
            <h2>Source Cleanup</h2>
            <div class="actions">
              <button class="btn" onclick="pauseFailingSources()">Pause failing sources</button>
            </div>
            <div id="sourceCleanup"></div>
          </div>
          <div class="panel">
            <h2>Form Fill Feedback</h2>
            <div id="formFeedbackSummary"></div>
          </div>
        </div>
        <div>
          <div class="panel">
            <h2>CV Versions</h2>
            <div id="cvVersionList"></div>
          </div>
          <div class="panel">
            <h2>Answer Bank</h2>
            <div id="answerBankList"></div>
          </div>
          <div class="panel">
            <h2>Story Bank</h2>
            <div id="storyBankList"></div>
          </div>
        </div>
      </div>
    </section>

    <section id="email">
      <div class="grid">
        <div class="panel">
          <h2>Email Setup</h2>
          <p class="muted">MWEB's current SMTP guidance is `smtp.mweb.co.za`, port `587`, authentication required, with your full email address as username. These settings are saved locally in `.env`, which is gitignored.</p>
          <div class="row">
            <div><label>SMTP host</label><input id="email_host" value="smtp.mweb.co.za"></div>
            <div><label>SMTP port</label><input id="email_port" value="587"></div>
            <div><label>Username</label><input id="email_user" value="Phillip2002@mweb.co.za"></div>
            <div><label>From address</label><input id="email_from" value="Phillip2002@mweb.co.za"></div>
            <div><label>Default test recipient</label><input id="email_to" placeholder="Usually your own email first"></div>
            <div><label>Password</label><input id="email_password" type="password" autocomplete="new-password" placeholder="Stored locally if saved"></div>
          </div>
          <label><input id="email_starttls" type="checkbox" style="width:auto" checked> Use STARTTLS/encryption on port 587</label>
          <div class="actions">
            <button class="btn primary" onclick="saveEmailConfig()">Save email settings</button>
            <button class="btn" onclick="sendTestEmail()">Send test email</button>
          </div>
        </div>
        <div class="panel">
          <h2>Status</h2>
          <div id="emailStatus"></div>
          <pre>Use this first:
1. Save settings with your MWEB password.
2. Send a test email to yourself.
3. If MWEB rejects STARTTLS, untick STARTTLS and test again.
4. Once the test works, follow-up drafts can be sent from the Applications tab.</pre>
        </div>
        <div class="panel">
          <h2>Inbox Reply Tracking</h2>
          <p class="muted">IMAP is read-only here. The app scans your inbox, matches likely recruiter/company replies to applications or outreach, and waits for you to decide what to do.</p>
          <div class="row">
            <div><label>IMAP host</label><input id="inbox_host" value="imap.mweb.co.za"></div>
            <div><label>IMAP port</label><input id="inbox_port" value="993"></div>
            <div><label>Username</label><input id="inbox_user" value="Phillip2002@mweb.co.za"></div>
            <div><label>Mailbox</label><input id="inbox_mailbox" value="INBOX"></div>
            <div><label>Lookback days</label><input id="inbox_lookback_days" type="number" min="1" max="365" value="45"></div>
            <div><label>Password</label><input id="inbox_password" type="password" autocomplete="new-password" placeholder="Stored locally if saved"></div>
          </div>
          <label><input id="inbox_ssl" type="checkbox" style="width:auto" checked> Use SSL/TLS on port 993</label>
          <div class="actions">
            <button class="btn primary" onclick="saveInboxConfig()">Save inbox settings</button>
            <button class="btn" onclick="scanInbox()">Scan inbox now</button>
          </div>
          <div id="inboxStatus"></div>
        </div>
        <div class="panel">
          <h2>Tracked Replies</h2>
          <div id="inboxMessages"></div>
        </div>
      </div>
    </section>

    <section id="session">
      <div class="grid">
        <div class="panel">
          <h2>Session Memory</h2>
          <p class="muted">This is the durable handoff future sessions read before continuing the project. Use the draft button near the end of a work session, review the text, then save it.</p>
          <textarea id="session_memory" style="min-height:520px"></textarea>
          <div class="actions">
            <button class="btn" onclick="refreshSessionMemory()">Refresh</button>
            <button class="btn primary" onclick="generateEndSessionDraft()">Generate end-session draft</button>
            <button class="btn warn" onclick="saveSessionMemory()">Save memory file</button>
          </div>
        </div>
        <div class="panel">
          <h2>Memory Rules</h2>
          <pre>When Phillip says "end session", update SESSION_MEMORY.md before replying.

Do not store passwords, SMTP secrets, API keys, cookies, or private tokens.

Record:
- completed work
- changed files
- current app health if checked
- decisions and preferences
- blockers or risks
- best next actions</pre>
        </div>
      </div>
    </section>
  </main>

  <script>
    let state = {profile: {}, jobs: [], applications: [], targets: []};
    let selectedApplication = null;
    let selectedLead = null;
    let selectedTarget = null;

    const profileKeys = [
      "full_name", "email", "phone", "location", "cv_path", "cv_text",
      "portfolio_url", "linkedin_url", "target_roles", "preferred_industries",
      "target_locations", "work_authorization", "salary_expectation",
      "salary_target_zar_monthly", "availability", "notice_period", "relocation",
      "demographics_policy", "references_policy", "email_provider", "tone", "email_voice",
      "writing_sample_path", "writing_sample_text", "writing_style_notes"
    ];
    let reminderPopupShown = false;

    document.querySelectorAll("nav button").forEach(button => {
      button.addEventListener("click", () => showTab(button.dataset.tab));
    });

    function showTab(tab) {
      document.querySelectorAll("nav button").forEach(b => b.classList.toggle("active", b.dataset.tab === tab));
      document.querySelectorAll("main section").forEach(s => s.classList.toggle("active", s.id === tab));
    }

    async function api(path, options = {}) {
      const response = await fetch(path, {
        headers: {"content-type": "application/json"},
        ...options
      });
      const payload = await response.json();
      if (!payload.ok && payload.error) throw new Error(payload.error);
      return payload;
    }

    async function load() {
      state = await api("/api/state");
      renderProfile();
      renderDashboard();
      renderEmail();
      renderJobs();
      renderApplications();
      renderLeads();
      renderTargets();
      renderSources();
      renderSourceHealth();
      renderAnalytics();
      renderAutoMode();
      renderSearchLinks();
      renderSessionMemory();
    }

    function message(text, type = "ok") {
      const el = document.getElementById("message");
      el.innerHTML = `<div class="notice ${type === "bad" ? "bad" : ""}">${escapeHtml(text)}</div>`;
      setTimeout(() => { el.innerHTML = ""; }, 5000);
    }

    function renderProfile() {
      for (const key of profileKeys) {
        const el = document.getElementById(`profile_${key}`);
        if (el) el.value = state.profile[key] || "";
      }
    }

    function renderDashboard() {
      const jobs = state.jobs;
      const apps = state.applications;
      const ready = jobs.filter(j => j.score >= 55 && ["new", "shortlisted"].includes(j.status)).length;
      const drafted = apps.filter(a => a.status === "draft").length;
      const applied = jobs.filter(j => j.status === "applied").length;
      const leadCount = (state.leads || []).length;
      const targetCount = (state.targets || []).length;
      const sourceCount = (state.sources || []).filter(source => source.enabled).length;
      const reminders = followUpReminders();
      document.getElementById("summary").innerHTML = `
        <p><strong>${jobs.length}</strong> jobs tracked.</p>
        <p><strong>${ready}</strong> strong jobs ready for review.</p>
        <p><strong>${drafted}</strong> application drafts waiting.</p>
        <p><strong>${applied}</strong> applications marked as submitted.</p>
        <p><strong>${targetCount}</strong> target companies tracked.</p>
        <p><strong>${leadCount}</strong> company outreach leads tracked.</p>
        <p><strong>${sourceCount}</strong> automatic job sources enabled.</p>
        <p class="muted">Daily target: ${escapeHtml(state.profile.daily_target || "5 high-quality applications per day.")}</p>
        <h3>Follow-up Reminders</h3>
        ${renderReminderList(reminders)}
      `;
      renderDailyReview();
      showReminderPopup(reminders);
    }

    function dailyReviewApplications() {
      const actionable = state.applications.filter(app => ["draft", "ready"].includes(app.status));
      if (actionable.length) return actionable.slice(0, 5);
      return state.applications.filter(app => app.status !== "rejected").slice(0, 5);
    }

    function appJob(app) {
      return (state.jobs || []).find(job => Number(job.id) === Number(app.job_id)) || {};
    }

    function missingApplicationItems(app) {
      const missing = [];
      const job = appJob(app);
      if (!app.url) missing.push("job URL");
      if (!app.cover_letter) missing.push("cover letter");
      if (!app.answers) missing.push("questionnaire answers");
      if (!app.follow_up) missing.push("follow-up email");
      if (!app.research_notes) missing.push("company research");
      if (!app.company_notes) missing.push("personalization notes");
      if (!app.contact_email) missing.push("contact email if available");
      if (!app.contact_name) missing.push("contact name if available");
      if (app.status === "submitted" && !app.next_follow_up) missing.push("follow-up date");
      if ((job.concerns || "").trim()) missing.push("fit concerns to review");
      return missing;
    }

    function nextApplicationAction(app) {
      const missing = missingApplicationItems(app);
      const requiredDraftMissing = !app.cover_letter || !app.answers || !app.follow_up;
      if (app.status === "submitted" && app.next_follow_up && !app.follow_up_sent_at && daysUntil(app.next_follow_up) <= 0) {
        return "Send due follow-up.";
      }
      if (requiredDraftMissing) return "Regenerate or complete the draft.";
      if (!app.company_notes) return "Add company-specific notes before using the email drafts.";
      if (!app.contact_email) return "Look for a recruiter/contact email, or proceed through the ATS only.";
      if (app.status === "ready") return "Run Prepare form and review the browser fields.";
      if (missing.length) return "Review missing details, then prepare the form.";
      return "Ready for supervised form preparation.";
    }

    function renderDailyReview() {
      const target = document.getElementById("dailyReview");
      if (!target) return;
      const apps = dailyReviewApplications();
      if (!apps.length) {
        target.innerHTML = `
          <p class="muted">No application drafts yet.</p>
          <div class="actions">
            <button class="btn primary" onclick="runDailyWorkflow()">Run daily workflow</button>
            <button class="btn" onclick="showTab('jobs')">Review jobs</button>
          </div>
        `;
        return;
      }
      target.innerHTML = apps.map(app => {
        const job = appJob(app);
        const missing = missingApplicationItems(app);
        const blockerCount = missing.filter(item => !item.includes("if available")).length;
        const statusClass = blockerCount ? "bad" : missing.length ? "muted" : "ok";
        const concerns = (job.concerns || "").trim();
        return `
          <div class="reminder">
            <h3>${escapeHtml(app.company)} - ${escapeHtml(app.title)}</h3>
            <div class="meta">Status: ${escapeHtml(app.status)} - job score ${escapeHtml(job.score ?? "n/a")} - quality ${escapeHtml(app.quality_score || 0)} - ${escapeHtml(app.location || "Location not listed")}</div>
            ${app.recommended_cv_version ? `<div><span class="tag">${escapeHtml(app.recommended_cv_version)}</span></div>` : ""}
            <p class="${statusClass}">${escapeHtml(nextApplicationAction(app))}</p>
            <div>
              ${missing.length ? missing.slice(0, 7).map(item => `<span class="tag">${escapeHtml(item)}</span>`).join("") : `<span class="tag">complete enough to prepare</span>`}
            </div>
            ${concerns ? `<details><summary>Fit concerns</summary><pre>${escapeHtml(concerns)}</pre></details>` : ""}
            <div class="actions">
              <button class="btn primary" onclick="selectApplication(${app.id})">Review draft</button>
              ${app.url ? `<a class="btn" href="${escapeAttr(app.url)}" target="_blank" rel="noreferrer">Open job</a>` : ""}
              <button class="btn" onclick="prepareApplicationFromDashboard(${app.id})">Prepare form</button>
              <button class="btn warn" onclick="markApplicationSubmittedFromDashboard(${app.id})">Mark submitted</button>
            </div>
          </div>
        `;
      }).join("");
    }

    function followUpReminders() {
      return state.applications
        .filter(app => app.status === "submitted" && app.next_follow_up && !app.follow_up_sent_at)
        .map(app => ({...app, daysUntil: daysUntil(app.next_follow_up)}))
        .sort((a, b) => a.daysUntil - b.daysUntil);
    }

    function daysUntil(dateText) {
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      const target = new Date(`${dateText}T00:00:00`);
      return Math.ceil((target - today) / 86400000);
    }

    function followUpLabel(app) {
      if (app.follow_up_sent_at) return `Follow-up sent ${formatDate(app.follow_up_sent_at.slice(0, 10))}`;
      if (!app.next_follow_up) return "Follow-up not scheduled";
      const days = daysUntil(app.next_follow_up);
      if (days > 1) return `Follow-up in ${days} days`;
      if (days === 1) return "Follow-up tomorrow";
      if (days === 0) return "Follow-up due today";
      return `Follow-up overdue by ${Math.abs(days)} day${Math.abs(days) === 1 ? "" : "s"}`;
    }

    function renderReminderList(reminders) {
      if (!reminders.length) return `<p class="muted">No submitted applications waiting for follow-up.</p>`;
      return reminders.slice(0, 8).map(app => {
        const dueClass = app.daysUntil <= 0 ? "bad" : app.daysUntil <= 2 ? "ok" : "muted";
        return `
          <div class="reminder">
            <h3>${escapeHtml(app.company)} - ${escapeHtml(app.title)}</h3>
            <p class="${dueClass}">${escapeHtml(followUpLabel(app))}</p>
            <div class="actions">
              <button class="btn primary" onclick="selectApplication(${app.id})">Review</button>
              <button class="btn" onclick="sendFollowUpFor(${app.id})">Send follow-up</button>
            </div>
          </div>
        `;
      }).join("");
    }

    function showReminderPopup(reminders) {
      if (reminderPopupShown) return;
      const due = reminders.filter(app => app.daysUntil <= 0);
      if (!due.length) return;
      reminderPopupShown = true;
      setTimeout(() => {
        alert(`${due.length} follow-up email${due.length === 1 ? " is" : "s are"} due today or overdue. Open the Dashboard or Applications tab to review and send.`);
      }, 300);
    }

    function formatDate(dateText) {
      if (!dateText) return "";
      return dateText;
    }

    function renderEmail() {
      const cfg = state.email || {};
      const inbox = state.inbox || {};
      document.getElementById("email_host").value = cfg.host || "smtp.mweb.co.za";
      document.getElementById("email_port").value = cfg.port || "587";
      document.getElementById("email_user").value = cfg.user || state.profile.email || "";
      document.getElementById("email_from").value = cfg.from || state.profile.email || "";
      document.getElementById("email_to").value = cfg.to || state.profile.email || "";
      document.getElementById("email_starttls").checked = String(cfg.starttls ?? "1") !== "0";
      document.getElementById("inbox_host").value = inbox.host || "imap.mweb.co.za";
      document.getElementById("inbox_port").value = inbox.port || "993";
      document.getElementById("inbox_user").value = inbox.user || state.profile.email || "";
      document.getElementById("inbox_mailbox").value = inbox.mailbox || "INBOX";
      document.getElementById("inbox_lookback_days").value = inbox.lookback_days || "45";
      document.getElementById("inbox_ssl").checked = String(inbox.ssl ?? "1") !== "0";
      document.getElementById("emailStatus").innerHTML = `
        <p><strong>Host:</strong> ${escapeHtml(cfg.host || "not set")}</p>
        <p><strong>User:</strong> ${escapeHtml(cfg.user || "not set")}</p>
        <p><strong>From:</strong> ${escapeHtml(cfg.from || "not set")}</p>
        <p><strong>Password:</strong> ${cfg.password_set ? '<span class="ok">saved locally</span>' : '<span class="bad">not saved</span>'}</p>
      `;
      document.getElementById("inboxStatus").innerHTML = `
        <p><strong>Inbox host:</strong> ${escapeHtml(inbox.host || "not set")}</p>
        <p><strong>Inbox user:</strong> ${escapeHtml(inbox.user || "not set")}</p>
        <p><strong>Mailbox:</strong> ${escapeHtml(inbox.mailbox || "INBOX")}</p>
        <p><strong>Password:</strong> ${inbox.password_set ? '<span class="ok">saved locally</span>' : '<span class="bad">not saved</span>'}</p>
      `;
      renderInboxMessages();
    }

    function renderInboxMessages() {
      const messages = state.inbox_messages || [];
      const target = document.getElementById("inboxMessages");
      if (!target) return;
      if (!messages.length) {
        target.innerHTML = `<p class="muted">No tracked replies yet. Save inbox settings, then scan your inbox.</p>`;
        return;
      }
      target.innerHTML = messages.map(item => {
        const match = item.matched_type === "application"
          ? `${item.application_company || "Application"} - ${item.application_title || ""}`
          : item.matched_type === "outreach"
            ? `${item.lead_company || "Outreach lead"}`
            : "No confident match";
        const actionButtons = inboxActionButtons(item);
        return `
          <article class="job">
            <div>
              <span class="tag">${escapeHtml(item.classification || "unknown")}</span>
              <span class="tag">${escapeHtml(item.status || "new")}</span>
              <span class="tag">${escapeHtml(String(item.confidence || 0))}%</span>
            </div>
            <div>
              <h3>${escapeHtml(item.subject || "(no subject)")}</h3>
              <div class="meta">${escapeHtml(item.from_name || "")} ${escapeHtml(item.from_email || "")} - ${escapeHtml(item.received_at || "")}</div>
              <div class="meta">Match: ${escapeHtml(match)}</div>
              <pre>${escapeHtml(item.snippet || "")}</pre>
              <div class="actions">
                ${actionButtons}
                <button class="btn" onclick="matchInboxToApplication(${item.id})">Match application</button>
                <button class="btn" onclick="matchInboxToLead(${item.id})">Match outreach</button>
                <button class="btn" onclick="markInbox(${item.id}, 'reviewed')">Mark reviewed</button>
                <button class="btn" onclick="markInbox(${item.id}, 'ignored')">Ignore</button>
              </div>
            </div>
          </article>
        `;
      }).join("");
    }

    function inboxActionButtons(item) {
      if (item.matched_type === "application" && item.application_id) {
        const interview = `<button class="btn primary" onclick="markInbox(${item.id}, 'handled', 'interview')">Mark interview</button>`;
        const rejected = `<button class="btn warn" onclick="markInbox(${item.id}, 'handled', 'rejected')">Mark rejected</button>`;
        return `${item.classification === "interview" ? interview : ""}${item.classification === "rejection" ? rejected : ""}`;
      }
      if (item.matched_type === "outreach" && item.lead_id) {
        return `<button class="btn primary" onclick="markInbox(${item.id}, 'handled', '', 'replied')">Mark outreach replied</button>`;
      }
      return "";
    }

    async function renderSearchLinks() {
      const links = await api("/api/open-searches");
      const html = Object.entries(links).map(([label, url]) => `<p><a href="${escapeAttr(url)}" target="_blank" rel="noreferrer">${escapeHtml(label)}</a></p>`).join("");
      document.getElementById("searchLinks").innerHTML = html;
      document.getElementById("discoverLinks").innerHTML = html;
    }

    function renderJobs() {
      const filter = document.getElementById("job_filter")?.value || "";
      const jobs = state.jobs.filter(job => !filter || job.status === filter);
      document.getElementById("jobList").innerHTML = jobs.map(job => {
        const scoreClass = job.score < 35 ? "low" : job.score < 60 ? "mid" : "";
        return `
          <article class="job">
            <div class="score ${scoreClass}">${job.score}</div>
            <div>
              <h3>${escapeHtml(job.title)}</h3>
              <div class="meta">${escapeHtml(job.company)} - ${escapeHtml(job.location || "Location not listed")}</div>
              <div>
                <span class="tag">${escapeHtml(job.status)}</span>
                <span class="tag">${escapeHtml(job.source)}</span>
              </div>
              ${job.url ? `<p class="meta"><a href="${escapeAttr(job.url)}" target="_blank" rel="noreferrer">${escapeHtml(job.url)}</a></p>` : ""}
              <pre>${escapeHtml(job.score_reasons || "")}${job.concerns ? "\n\nConcerns:\n" + escapeHtml(job.concerns) : ""}</pre>
              <details><summary>Description</summary><pre>${escapeHtml(job.description || "")}</pre></details>
              <div class="actions">
                <button class="btn" onclick="setJobStatus(${job.id}, 'shortlisted')">Shortlist</button>
                <button class="btn primary" onclick="generateApplication(${job.id})">Generate draft</button>
                <button class="btn" onclick="setJobStatus(${job.id}, 'applied')">Mark applied</button>
                <button class="btn" onclick="setJobStatus(${job.id}, 'rejected')">Reject</button>
              </div>
            </div>
          </article>`;
      }).join("") || `<p class="muted">No jobs in this view.</p>`;
    }

    function renderSources() {
      const sources = state.sources || [];
      const target = document.getElementById("sourceList");
      if (!target) return;
      target.innerHTML = sources.map(source => {
        let last = "never run";
        if (source.last_run) last = `last run ${source.last_run.slice(0, 10)}`;
        return `
          <div class="reminder">
            <h3>${escapeHtml(source.name || `${source.source_type}:${source.token}`)}</h3>
            <div class="meta">${escapeHtml(source.source_type)} - ${escapeHtml(source.token)} - ${escapeHtml(source.enabled ? "enabled" : "paused")}</div>
            <div class="meta">${escapeHtml(last)}</div>
            ${source.last_result ? `<pre>${escapeHtml(source.last_result)}</pre>` : ""}
            <div class="actions">
              <button class="btn primary" onclick="runSource(${source.id})">Run now</button>
              <button class="btn" onclick="toggleSource(${source.id}, ${source.enabled ? "false" : "true"})">${source.enabled ? "Pause" : "Enable"}</button>
            </div>
          </div>
        `;
      }).join("") || `<p class="muted">No automatic sources saved yet.</p>`;
    }

    function sourceResult(source) {
      try {
        return JSON.parse(source.last_result || "{}");
      } catch {
        return {raw: source.last_result || ""};
      }
    }

    function renderSourceHealth() {
      const sources = state.sources || [];
      const targets = ["dashboardSourceHealth", "discoverSourceHealth"]
        .map(id => document.getElementById(id))
        .filter(Boolean);
      if (!targets.length) return;
      const enabled = sources.filter(source => source.enabled).length;
      const errors = sources.filter(source => {
        const result = sourceResult(source);
        return Boolean(result.error);
      });
      const cards = sources.slice().sort((a, b) => {
        const aError = sourceResult(a).error ? 1 : 0;
        const bError = sourceResult(b).error ? 1 : 0;
        return bError - aError || Number(b.enabled) - Number(a.enabled);
      }).slice(0, 8).map(source => {
        const result = sourceResult(source);
        const ok = !result.error && source.last_run;
        const count = Number(result.count || 0);
        const status = result.error ? "error" : ok ? `${count} jobs` : "not run";
        const cls = result.error ? "bad" : ok ? "ok" : "muted";
        return `
          <div class="reminder">
            <h3>${escapeHtml(source.name || source.token)}</h3>
            <div class="meta">${escapeHtml(source.source_type)} - ${escapeHtml(source.enabled ? "enabled" : "paused")} - ${escapeHtml(source.last_run ? source.last_run.slice(0, 10) : "never run")}</div>
            <p class="${cls}">${escapeHtml(status)}</p>
            ${result.error ? `<pre>${escapeHtml(result.error)}</pre>` : ""}
            <div class="actions">
              <button class="btn" onclick="runSource(${source.id})">Run</button>
              <button class="btn" onclick="toggleSource(${source.id}, ${source.enabled ? "false" : "true"})">${source.enabled ? "Pause" : "Enable"}</button>
            </div>
          </div>
        `;
      }).join("");
      const html = `
        <p><strong>${enabled}</strong> enabled sources. <strong>${errors.length}</strong> source${errors.length === 1 ? "" : "s"} with visible errors.</p>
        ${cards || `<p class="muted">No sources saved yet.</p>`}
      `;
      for (const target of targets) target.innerHTML = html;
    }

    function renderAnalytics() {
      if (!document.getElementById("analyticsOverview")) return;
      const jobs = state.jobs || [];
      const apps = state.applications || [];
      const leads = state.leads || [];
      const messages = state.inbox_messages || [];
      const followups = followUpReminders();
      const submitted = apps.filter(app => ["submitted", "interview", "offer"].includes(app.status));
      const responses = apps.filter(app => ["interview", "offer"].includes(app.status));
      const rejected = apps.filter(app => app.status === "rejected");
      const replyMatches = messages.filter(item => item.matched_type && Number(item.confidence || 0) >= 40);
      const interviews = messages.filter(item => item.classification === "interview");
      const strongJobs = jobs.filter(job => Number(job.score || 0) >= 55);
      const avgScore = jobs.length ? Math.round(jobs.reduce((sum, job) => sum + Number(job.score || 0), 0) / jobs.length) : 0;
      document.getElementById("analyticsOverview").innerHTML = `
        <div class="metric-grid">
          ${metric("Jobs", jobs.length, `${strongJobs.length} strong fits`)}
          ${metric("Drafts", apps.length, `${submitted.length} submitted`)}
          ${metric("Responses", responses.length, `${responseRate(responses.length, submitted.length)} response rate`)}
          ${metric("Inbox matches", replyMatches.length, `${interviews.length} interview signal(s)`)}
          ${metric("Avg score", avgScore, `${rejected.length} rejected`)}
        </div>
      `;
      renderAnalyticsFunnel(apps);
      renderAnalyticsSources(jobs, apps);
      renderAnalyticsFollowups(followups, apps, leads);
      renderAnalyticsReplies(messages, apps);
      renderAnalyticsRecommendations(jobs, apps, followups, messages);
    }

    function metric(label, value, detail) {
      return `<div class="metric"><strong>${escapeHtml(value)}</strong><div>${escapeHtml(label)}</div><div class="meta">${escapeHtml(detail)}</div></div>`;
    }

    function responseRate(count, submitted) {
      if (!submitted) return "0%";
      return `${Math.round((count / submitted) * 100)}%`;
    }

    function countBy(items, fn) {
      const out = {};
      for (const item of items) {
        const key = fn(item) || "unknown";
        out[key] = (out[key] || 0) + 1;
      }
      return out;
    }

    function renderAnalyticsFunnel(apps) {
      const statuses = ["draft", "ready", "submitted", "interview", "offer", "rejected"];
      const counts = countBy(apps, app => app.status || "draft");
      document.getElementById("analyticsFunnel").innerHTML = `
        <table>
          <thead><tr><th>Status</th><th>Count</th><th>Action</th></tr></thead>
          <tbody>
            ${statuses.map(status => {
              const count = counts[status] || 0;
              const action = status === "draft" ? "Review and prepare"
                : status === "ready" ? "Open form"
                : status === "submitted" ? "Track follow-up"
                : status === "interview" ? "Prepare notes"
                : status === "offer" ? "Assess fit"
                : "Learn and refine";
              return `<tr><td>${escapeHtml(status)}</td><td>${count}</td><td>${escapeHtml(action)}</td></tr>`;
            }).join("")}
          </tbody>
        </table>
      `;
    }

    function renderAnalyticsSources(jobs, apps) {
      const appsByJob = Object.fromEntries(apps.map(app => [Number(app.job_id), app]));
      const sourceRows = Object.values(jobs.reduce((acc, job) => {
        const key = job.source || "unknown";
        if (!acc[key]) acc[key] = {source: key, jobs: 0, score: 0, strong: 0, drafts: 0, submitted: 0, responses: 0, errors: 0};
        const row = acc[key];
        row.jobs += 1;
        row.score += Number(job.score || 0);
        if (Number(job.score || 0) >= 55) row.strong += 1;
        if ((job.concerns || "").toLowerCase().includes("potential scam")) row.errors += 1;
        const app = appsByJob[Number(job.id)];
        if (app) {
          row.drafts += 1;
          if (["submitted", "interview", "offer"].includes(app.status)) row.submitted += 1;
          if (["interview", "offer"].includes(app.status)) row.responses += 1;
        }
        return acc;
      }, {})).map(row => ({...row, avg: row.jobs ? Math.round(row.score / row.jobs) : 0}))
        .sort((a, b) => b.strong - a.strong || b.avg - a.avg)
        .slice(0, 12);

      document.getElementById("analyticsSources").innerHTML = `
        <table>
          <thead><tr><th>Source</th><th>Jobs</th><th>Avg</th><th>Strong</th><th>Drafts</th><th>Submitted</th><th>Responses</th></tr></thead>
          <tbody>
            ${sourceRows.map(row => `
              <tr>
                <td>${escapeHtml(row.source)}</td>
                <td>${row.jobs}</td>
                <td>${row.avg}</td>
                <td>${row.strong}</td>
                <td>${row.drafts}</td>
                <td>${row.submitted}</td>
                <td>${row.responses}</td>
              </tr>
            `).join("") || `<tr><td colspan="7" class="muted">No source data yet.</td></tr>`}
          </tbody>
        </table>
      `;
    }

    function renderAnalyticsFollowups(followups, apps, leads) {
      const overdue = followups.filter(item => item.daysUntil < 0).length;
      const dueToday = followups.filter(item => item.daysUntil === 0).length;
      const upcoming = followups.filter(item => item.daysUntil > 0).length;
      const outreachSent = leads.filter(lead => lead.status === "sent").length;
      document.getElementById("analyticsFollowups").innerHTML = `
        <div class="metric-grid">
          ${metric("Overdue", overdue, "send or reschedule")}
          ${metric("Due today", dueToday, "review first")}
          ${metric("Upcoming", upcoming, "scheduled follow-ups")}
          ${metric("Outreach sent", outreachSent, "company leads")}
        </div>
        ${renderReminderList(followups)}
      `;
    }

    function renderAnalyticsReplies(messages, apps) {
      const counts = countBy(messages, item => item.classification || "unknown");
      const matched = messages.filter(item => item.matched_type && Number(item.confidence || 0) >= 40);
      const interviews = messages.filter(item => item.classification === "interview");
      const rejections = messages.filter(item => item.classification === "rejection");
      const autoReplies = messages.filter(item => item.classification === "auto_reply");
      const byMatch = countBy(matched, item => item.matched_type || "unmatched");
      const target = document.getElementById("analyticsReplies");
      if (!target) return;
      target.innerHTML = `
        <div class="metric-grid">
          ${metric("Tracked replies", messages.length, `${matched.length} matched`)}
          ${metric("Interview signals", interviews.length, "from inbox")}
          ${metric("Rejections", rejections.length, "from inbox")}
          ${metric("Auto replies", autoReplies.length, "confirmations")}
        </div>
        <table>
          <thead><tr><th>Classification</th><th>Count</th></tr></thead>
          <tbody>
            ${Object.entries(counts).sort((a, b) => b[1] - a[1]).map(([name, count]) => `<tr><td>${escapeHtml(name)}</td><td>${count}</td></tr>`).join("") || `<tr><td colspan="2" class="muted">No inbox replies tracked yet.</td></tr>`}
          </tbody>
        </table>
        <p class="meta">Matched applications: ${escapeHtml(String(byMatch.application || 0))}. Matched outreach: ${escapeHtml(String(byMatch.outreach || 0))}.</p>
      `;
    }

    function renderAnalyticsRecommendations(jobs, apps, followups, messages = []) {
      const recommendations = [];
      const targetCount = (state.targets || []).length;
      const drafts = apps.filter(app => app.status === "draft").length;
      const submitted = apps.filter(app => ["submitted", "interview", "offer"].includes(app.status)).length;
      const strong = jobs.filter(job => Number(job.score || 0) >= 55 && ["new", "shortlisted"].includes(job.status)).length;
      const sourceErrors = (state.sources || []).filter(source => sourceResult(source).error);
      const inbox = state.inbox || {};
      const unreviewedReplies = messages.filter(item => item.status === "new" && item.classification !== "auto_reply").length;
      if (targetCount < 20) recommendations.push("Add more target companies so the system can search brands Phillip actually wants.");
      if (sourceErrors.length) recommendations.push(`Fix or pause ${sourceErrors.length} failing source(s), starting with ${sourceErrors[0].name || sourceErrors[0].token}.`);
      if (strong >= 5 && drafts < 5) recommendations.push("Generate drafts from the strongest queued jobs.");
      if (drafts >= 5 && submitted < 5) recommendations.push("Use Daily Review to turn drafts into submitted applications.");
      if (followups.some(item => item.daysUntil <= 0)) recommendations.push("Send due follow-ups before adding more applications.");
      if (!inbox.password_set) recommendations.push("Save the IMAP password in Inbox Reply Tracking so replies can be tracked.");
      if (unreviewedReplies) recommendations.push(`Review ${unreviewedReplies} new inbox repl${unreviewedReplies === 1 ? "y" : "ies"} before sending more outreach.`);
      if (!recommendations.length) recommendations.push("System looks balanced. Keep adding target companies and run the daily workflow.");
      document.getElementById("analyticsRecommendations").innerHTML = recommendations.map(item => `<div class="reminder">${escapeHtml(item)}</div>`).join("");
    }

    function renderAutoMode() {
      if (!document.getElementById("automationRuns")) return;
      const runs = state.automation_runs || [];
      document.getElementById("automationRuns").innerHTML = runs.map(run => `
        <div class="reminder">
          <h3>${escapeHtml(run.kind || "auto-mode")} - ${escapeHtml((run.created_at || "").slice(0, 19))}</h3>
          <p>${escapeHtml(run.summary || "")}</p>
        </div>
      `).join("") || `<p class="muted">No automation runs yet.</p>`;

      const cvs = state.cv_versions || [];
      document.getElementById("cvVersionList").innerHTML = cvs.map(cv => `
        <div class="reminder">
          <h3>${escapeHtml(cv.name || "CV version")}</h3>
          <div class="meta">${escapeHtml(cv.focus || "")}${cv.is_default ? " - default" : ""}</div>
          <p>${escapeHtml(cv.notes || "")}</p>
        </div>
      `).join("") || `<p class="muted">No CV versions seeded yet.</p>`;

      const answers = state.answer_bank || [];
      document.getElementById("answerBankList").innerHTML = answers.slice(0, 10).map(answer => `
        <details class="reminder">
          <summary>${escapeHtml(answer.question || answer.question_key || "Answer")}</summary>
          <pre>${escapeHtml(answer.answer || "")}</pre>
        </details>
      `).join("") || `<p class="muted">No answer bank items yet.</p>`;

      const stories = state.story_bank || [];
      document.getElementById("storyBankList").innerHTML = stories.map(story => `
        <details class="reminder">
          <summary>${escapeHtml(story.title || "Story")}</summary>
          <p>${escapeHtml(story.story || "")}</p>
          <pre>${escapeHtml(story.proof_points || "")}</pre>
        </details>
      `).join("") || `<p class="muted">No story bank items yet.</p>`;

      const feedbackTarget = document.getElementById("formFeedbackSummary");
      if (feedbackTarget) {
        const feedback = state.form_feedback || [];
        const recs = state.form_feedback_recommendations || [];
        feedbackTarget.innerHTML = `
          ${recs.length ? `<h3>Mapping recommendations</h3>${recs.map(rec => `<div class="reminder">${escapeHtml(rec)}</div>`).join("")}` : `<p class="muted">No feedback recommendations yet.</p>`}
          <h3>Latest feedback</h3>
          ${feedback.slice(0, 8).map(item => `
            <details class="reminder">
              <summary>${escapeHtml(item.company || "")} - ${escapeHtml(item.title || "")}</summary>
              <pre>Worked: ${escapeHtml(item.worked || "")}

Missed: ${escapeHtml(item.missed || "")}

Wrong: ${escapeHtml(item.wrong || "")}

Notes: ${escapeHtml(item.notes || "")}</pre>
            </details>
          `).join("") || `<p class="muted">No form-fill feedback saved yet.</p>`}
        `;
      }

      const cleanupTarget = document.getElementById("sourceCleanup");
      if (cleanupTarget) {
        const recs = state.source_cleanup || [];
        cleanupTarget.innerHTML = recs.map(rec => `
          <div class="reminder">
            <h3>${escapeHtml(rec.name || rec.token || "Source")}</h3>
            <div class="meta">${escapeHtml(rec.source_type || "")} - ${escapeHtml(rec.enabled ? "enabled" : "paused")}</div>
            <p class="${rec.action === "pause-or-fix" ? "bad" : "muted"}">${escapeHtml(rec.reason || "")}</p>
            <div class="actions">
              <button class="btn" onclick="toggleSource(${rec.id}, false)">Pause</button>
              <button class="btn" onclick="runSource(${rec.id})">Run again</button>
            </div>
          </div>
        `).join("") || `<p class="muted">No source cleanup recommendations.</p>`;
      }
    }

    function renderApplications() {
      const list = document.getElementById("applicationList");
      list.innerHTML = state.applications.map(app => `
        <div class="panel">
          <h3>${escapeHtml(app.title)}</h3>
          <div class="meta">${escapeHtml(app.company)} - ${escapeHtml(followUpLabel(app))}</div>
          <div class="meta">${escapeHtml(contactSummary(app))}</div>
          <div>
            ${app.research_notes ? `<span class="tag">research saved</span>` : `<span class="tag">research needed</span>`}
            <span class="tag">quality ${escapeHtml(app.quality_score || 0)}</span>
            ${app.recommended_cv_version ? `<span class="tag">${escapeHtml(app.recommended_cv_version)}</span>` : ""}
          </div>
          <div class="actions">
            <button class="btn primary" onclick="selectApplication(${app.id})">Edit</button>
            ${app.url ? `<a class="btn" href="${escapeAttr(app.url)}" target="_blank" rel="noreferrer">Open job</a>` : ""}
            <a class="btn" href="${mailto(app)}">Email draft</a>
          </div>
        </div>
      `).join("") || `<p class="muted">No application drafts yet.</p>`;
      if (selectedApplication) selectApplication(selectedApplication.id, false);
    }

    function renderLeads() {
      const leads = state.leads || [];
      document.getElementById("leadList").innerHTML = leads.map(lead => `
        <div class="panel">
          <h3>${escapeHtml(lead.company || "Unnamed company")}</h3>
          <div class="meta">${escapeHtml(lead.industry || "No industry")} - ${escapeHtml(lead.status)}</div>
          <div class="meta">${escapeHtml(lead.contact_email ? contactLeadSummary(lead) : "No contact email saved")}</div>
          ${lead.website ? `<p class="meta"><a href="${escapeAttr(lead.website)}" target="_blank" rel="noreferrer">${escapeHtml(lead.website)}</a></p>` : ""}
          <div class="actions">
            <button class="btn primary" onclick="selectLead(${lead.id})">Edit</button>
            <button class="btn" onclick="setLeadStatus(${lead.id}, 'do-not-contact')">Do not contact</button>
          </div>
        </div>
      `).join("") || `<p class="muted">No company leads yet.</p>`;
      if (selectedLead) selectLead(selectedLead.id, false);
    }

    function renderTargets() {
      const targets = state.targets || [];
      const target = document.getElementById("targetList");
      if (!target) return;
      target.innerHTML = targets.map(item => `
        <div class="reminder">
          <h3>${escapeHtml(item.company || "Unnamed company")}</h3>
          <div class="meta">${escapeHtml(item.industry || "No industry")} - priority ${escapeHtml(item.priority || 3)} - ${escapeHtml(item.status || "target")}</div>
          ${item.website ? `<p class="meta"><a href="${escapeAttr(item.website)}" target="_blank" rel="noreferrer">${escapeHtml(item.website)}</a></p>` : ""}
          ${item.careers_url ? `<p class="meta"><a href="${escapeAttr(item.careers_url)}" target="_blank" rel="noreferrer">${escapeHtml(item.careers_url)}</a></p>` : ""}
          <div>
            ${item.source_id ? `<span class="tag">source #${escapeHtml(item.source_id)}</span>` : ""}
            ${item.lead_id ? `<span class="tag">lead #${escapeHtml(item.lead_id)}</span>` : ""}
            ${item.source_type ? `<span class="tag">${escapeHtml(item.source_type)}</span>` : ""}
          </div>
          ${item.notes ? `<pre>${escapeHtml(item.notes)}</pre>` : ""}
          <div class="actions">
            <button class="btn primary" onclick="editTarget(${item.id})">Edit</button>
            <button class="btn" onclick="targetToSource(${item.id})">Make job source</button>
            <button class="btn" onclick="targetToLead(${item.id})">Make outreach lead</button>
          </div>
        </div>
      `).join("") || `<p class="muted">No target companies yet. Add dream-fit brands here first.</p>`;
    }

    function renderSessionMemory() {
      const el = document.getElementById("session_memory");
      if (el && !el.matches(":focus")) el.value = state.session_memory || "";
    }

    function editTarget(id) {
      selectedTarget = (state.targets || []).find(item => item.id === id);
      if (!selectedTarget) return;
      const fields = ["company", "website", "careers_url", "industry", "priority", "status", "source_type", "source_token", "source_query", "notes"];
      document.getElementById("target_id").value = selectedTarget.id || "";
      for (const field of fields) {
        const el = document.getElementById(`target_${field}`);
        if (el) el.value = selectedTarget[field] || (field === "source_query" ? "marketing" : "");
      }
      showTab("targets");
    }

    function clearTargetForm() {
      selectedTarget = null;
      document.getElementById("target_id").value = "";
      ["company", "website", "careers_url", "industry", "source_token", "notes"].forEach(field => {
        document.getElementById(`target_${field}`).value = "";
      });
      document.getElementById("target_priority").value = "3";
      document.getElementById("target_status").value = "target";
      document.getElementById("target_source_type").value = "";
      document.getElementById("target_source_query").value = "marketing";
    }

    function selectLead(id, switchTab = true) {
      selectedLead = (state.leads || []).find(lead => lead.id === id);
      if (!selectedLead) return;
      const lead = selectedLead;
      document.getElementById("leadEditor").innerHTML = `
        <h3>${escapeHtml(lead.company || "Company lead")}</h3>
        <div class="row">
          <div><label>Company</label><input id="edit_lead_company" value="${escapeAttr(lead.company || "")}"></div>
          <div><label>Website</label><input id="edit_lead_website" value="${escapeAttr(lead.website || "")}"></div>
          <div><label>Industry</label><input id="edit_lead_industry" value="${escapeAttr(lead.industry || "")}"></div>
          <div><label>Status</label>
            <select id="edit_lead_status">
              ${["found", "researched", "drafted", "approved", "sent", "replied", "do-not-contact"].map(s => `<option value="${s}" ${lead.status === s ? "selected" : ""}>${s}</option>`).join("")}
            </select>
          </div>
          <div><label>Contact name</label><input id="edit_lead_contact_name" value="${escapeAttr(lead.contact_name || "")}"></div>
          <div><label>Contact role</label><input id="edit_lead_contact_role" value="${escapeAttr(lead.contact_role || "")}"></div>
        </div>
        <label>Contact email</label><input id="edit_lead_contact_email" value="${escapeAttr(lead.contact_email || "")}">
        <label>Source URL</label><input id="edit_lead_source_url" value="${escapeAttr(lead.source_url || "")}">
        <label>Why this company / personalization notes</label><textarea id="edit_lead_company_notes">${escapeHtml(lead.company_notes || "")}</textarea>
        <label>Outreach email</label><textarea id="edit_lead_outreach_email" style="min-height:240px">${escapeHtml(lead.outreach_email || "")}</textarea>
        <div class="actions">
          <button class="btn primary" onclick="saveLeadEdit()">Save lead</button>
          <button class="btn" onclick="generateLeadEmail()">Generate personalized outreach</button>
          <button class="btn" onclick="humanizeLeadEmail()">Humanize outreach</button>
          <button class="btn warn" onclick="sendLeadEmail()">Send outreach</button>
          <button class="btn" onclick="setLeadStatus(${lead.id}, 'do-not-contact')">Do not contact</button>
        </div>
      `;
      if (switchTab) showTab("outreach");
    }

    function contactLeadSummary(lead) {
      return [lead.contact_name, lead.contact_role, lead.contact_email].filter(Boolean).join(" - ");
    }

    function selectApplication(id, switchTab = true) {
      selectedApplication = state.applications.find(app => app.id === id);
      if (!selectedApplication) return;
      const app = selectedApplication;
      document.getElementById("applicationEditor").innerHTML = `
        <h3>${escapeHtml(app.title)} at ${escapeHtml(app.company)}</h3>
        <label>Status</label>
        <select id="edit_status">
          ${["draft", "ready", "submitted", "interview", "rejected", "offer"].map(s => `<option value="${s}" ${app.status === s ? "selected" : ""}>${s}</option>`).join("")}
        </select>
        <div class="row">
          <div><label>Contact name</label><input id="edit_contact_name" value="${escapeAttr(app.contact_name || "")}" placeholder="Jane"></div>
          <div><label>Contact role</label><input id="edit_contact_role" value="${escapeAttr(app.contact_role || "")}" placeholder="Marketing Manager"></div>
        </div>
        <label>Company/contact email</label><input id="edit_contact_email" value="${escapeAttr(app.contact_email || "")}" placeholder="recruiter@company.com">
        <label>Personalization notes</label><textarea id="edit_company_notes" placeholder="What stood out about the company, campaign, product, team, or brand.">${escapeHtml(app.company_notes || "")}</textarea>
        <label>Company research URL</label><input id="edit_research_url" value="${escapeAttr(app.research_url || "")}" placeholder="Company website, about page, or careers page">
        <label>Next follow-up</label><input id="edit_next_follow_up" type="date" value="${escapeAttr(app.next_follow_up || "")}">
        <p class="muted">${escapeHtml(followUpLabel(app))}</p>
        <label>Company research notes</label><textarea id="edit_research_notes" style="min-height:180px">${escapeHtml(app.research_notes || "")}</textarea>
        <label>Research sources</label><textarea id="edit_research_sources">${escapeHtml(app.research_sources || "")}</textarea>
        <label>Application checklist</label><textarea id="edit_checklist" readonly>${escapeHtml(app.checklist || "")}</textarea>
        <label>Quality notes</label><textarea id="edit_quality_notes" readonly>${escapeHtml(app.quality_notes || "")}</textarea>
        <label>Truthfulness / work authorization flags</label><textarea id="edit_truthfulness_flags" readonly>${escapeHtml(app.truthfulness_flags || "")}</textarea>
        <p class="muted">Quality score: ${escapeHtml(app.quality_score || 0)}. Recommended CV: ${escapeHtml(app.recommended_cv_version || "not assessed yet")}.</p>
        <details><summary>Tailored CV brief preview</summary><pre>${escapeHtml(tailoredCvPreview(app))}</pre></details>
        <label>Cover letter</label><textarea id="edit_cover_letter" style="min-height:220px">${escapeHtml(app.cover_letter || "")}</textarea>
        <label>CV notes</label><textarea id="edit_cv_notes">${escapeHtml(app.cv_notes || "")}</textarea>
        <label>Questionnaire answers</label><textarea id="edit_answers" style="min-height:220px">${escapeHtml(app.answers || "")}</textarea>
        <label>Follow-up email</label><textarea id="edit_follow_up">${escapeHtml(app.follow_up || "")}</textarea>
        <div class="actions">
          <button class="btn primary" onclick="saveApplication()">Save draft</button>
          <button class="btn" onclick="humanizeApplication()">Humanize sent copy</button>
          <button class="btn" onclick="researchApplication()">Research company</button>
          <button class="btn" onclick="regenerateFollowUp()">Regenerate personalized follow-up</button>
          <button class="btn" onclick="prepareApplicationForm()">Prepare form</button>
          <button class="btn warn" onclick="markApplicationSubmitted()">Mark submitted</button>
          <a class="btn" href="${mailto(app)}">Open email draft</a>
          <button class="btn" onclick="sendFollowUp()">Send follow-up</button>
        </div>
        <h3 style="margin-top:18px">Form Fill Feedback</h3>
        <label>What filled correctly?</label><textarea id="form_feedback_worked" placeholder="Example: name, email, phone, CV upload"></textarea>
        <label>What was missed?</label><textarea id="form_feedback_missed" placeholder="Example: LinkedIn, salary, cover letter"></textarea>
        <label>What was wrong?</label><textarea id="form_feedback_wrong" placeholder="Example: location was put into country, salary was too long"></textarea>
        <label>Notes</label><textarea id="form_feedback_notes" placeholder="Anything useful about this ATS/site."></textarea>
        <div class="actions">
          <button class="btn" onclick="saveFormFillFeedback()">Save form feedback</button>
        </div>
        <p class="muted">Generated files are written into the local documents folder after saving.</p>
      `;
      if (switchTab) showTab("applications");
    }

    function contactSummary(app) {
      const bits = [];
      if (app.contact_name) bits.push(app.contact_name);
      if (app.contact_role) bits.push(app.contact_role);
      if (app.contact_email) bits.push(app.contact_email);
      return bits.length ? `Contact: ${bits.join(" - ")}` : "No contact person saved";
    }

    function tailoredCvPreview(app) {
      const job = appJob(app);
      const version = app.recommended_cv_version || "General marketing CV";
      const keywords = cvKeywords(job);
      return [
        `Role: ${app.title || ""}`,
        `Company: ${app.company || ""}`,
        `Recommended CV: ${version}`,
        "",
        "Use this CV angle:",
        cvSummaryForVersion(version, app.company || "the company"),
        "",
        "Keywords to mirror truthfully:",
        keywords.length ? keywords.join(", ") : "marketing, brand, content, research, analytics",
        "",
        "Prioritise evidence from:",
        "- UCT Business Science Marketing",
        "- Cookie Factory content work",
        "- Look@ / SIGMUND market research",
        "- Sports coaching and Ironman training",
        "- Triathlon/gym training app where relevant"
      ].join("\\n");
    }

    function cvSummaryForVersion(version, company) {
      if (version.includes("Sports")) return `Cape Town-based UCT marketing graduate with content, research, analytics, coaching, and endurance-sport experience, positioned for practical sport/fitness brand work at ${company}.`;
      if (version.includes("Content")) return `Marketing graduate with hands-on social content, Canva, captions, short-form video, scheduling, and reporting experience, positioned for content and brand work at ${company}.`;
      if (version.includes("Research")) return `Marketing graduate with thesis, market research, Google Analytics, and insight-led recommendation experience, positioned for research/analytics marketing work at ${company}.`;
      if (version.includes("Startup")) return `Marketing graduate with AR startup project exposure and AI-assisted product-building experience, positioned for growth/startup marketing work at ${company}.`;
      return `UCT Business Science Marketing graduate with content, research, analytics, and sport leadership experience, positioned for practical marketing work at ${company}.`;
    }

    function cvKeywords(job) {
      const text = `${job.title || ""} ${job.description || ""}`.toLowerCase();
      const terms = ["marketing", "brand", "campaign", "content", "social media", "community", "growth", "analytics", "paid media", "events", "partnership", "sport", "fitness", "outdoor", "wellness", "consumer"];
      return terms.filter(term => text.includes(term)).slice(0, 12);
    }

    async function saveProfile() {
      const payload = {};
      for (const key of profileKeys) payload[key] = document.getElementById(`profile_${key}`).value;
      await api("/api/profile", {method: "POST", body: JSON.stringify(payload)});
      message("Profile saved.");
      await load();
    }

    async function extractCv() {
      const result = await api("/api/profile/extract-cv", {method: "POST", body: "{}"});
      if (result.ok) {
        message("CV text extracted.");
      } else {
        message("No PDF extractor is available yet. Paste CV text into the profile field for now.", "bad");
      }
      await load();
    }

    async function extractWritingSample() {
      const payload = {
        path: document.getElementById("profile_writing_sample_path").value,
        text: document.getElementById("profile_writing_sample_text").value
      };
      const result = await api("/api/profile/extract-writing-sample", {method: "POST", body: JSON.stringify(payload)});
      if (result.ok) {
        document.getElementById("profile_writing_sample_text").value = result.text || "";
        document.getElementById("profile_writing_style_notes").value = result.style_notes || "";
        message("Writing sample extracted and analysed.");
      } else {
        message("Could not extract that writing sample. Paste the text into the writing sample field instead.", "bad");
      }
      await load();
    }

    async function discover() {
      const source = document.getElementById("discover_source").value;
      const token = document.getElementById("discover_token").value;
      const query = document.getElementById("discover_query").value;
      const result = await api("/api/discover", {method: "POST", body: JSON.stringify({source, token, query})});
      message(`Imported ${result.count} jobs.`);
      await load();
      showTab("jobs");
    }

    async function saveSource() {
      const payload = {
        name: document.getElementById("source_name").value,
        source_type: document.getElementById("source_type").value,
        token: document.getElementById("source_token").value,
        query: document.getElementById("source_query").value,
        enabled: document.getElementById("source_enabled").checked
      };
      await api("/api/sources/save", {method: "POST", body: JSON.stringify(payload)});
      ["name", "token", "query"].forEach(key => document.getElementById(`source_${key}`).value = "");
      message("Automatic source saved.");
      await load();
    }

    async function runSource(id) {
      const result = await api("/api/sources/run", {method: "POST", body: JSON.stringify({id})});
      message(`Source imported ${result.count || 0} jobs.`);
      await load();
      showTab("jobs");
    }

    async function runAllSources() {
      const result = await api("/api/sources/run-all", {method: "POST", body: "{}"});
      const errors = (result.errors || []).length ? ` Errors: ${(result.errors || []).join("; ")}` : "";
      message(`Ran ${result.ran || 0} sources and imported ${result.imported || 0} jobs.${errors}`, errors ? "bad" : "ok");
      await load();
      showTab("jobs");
    }

    async function runDailyWorkflow() {
      message("Running daily workflow. This can take a minute while sources are checked.");
      const result = await api("/api/daily/run", {method: "POST", body: JSON.stringify({limit: 5})});
      const errors = result.discovery?.errors?.length ? ` Errors: ${result.discovery.errors.join("; ")}` : "";
      message(
        `Daily workflow complete: ${result.discovery?.imported || 0} jobs imported, ${result.rescored?.count || 0} rescored, ${result.shortlisted?.count || 0} shortlisted, ${result.drafts?.count || 0} drafts generated.${errors}`,
        errors ? "bad" : "ok"
      );
      await load();
      showTab("applications");
    }

    async function runAutomaticMode() {
      const limit = Number(document.getElementById("auto_limit")?.value || 5);
      const status = document.getElementById("autoStatus");
      if (status) status.innerHTML = `<div class="notice">Automatic mode is running. This can take a few minutes while sources, drafts, research, quality checks, and reports are prepared.</div>`;
      const result = await api("/api/automation/run", {method: "POST", body: JSON.stringify({limit})});
      const errors = [
        ...(result.discovery?.errors || []),
        ...(result.target_sources?.errors || [])
      ];
      const html = `
        <div class="notice ${errors.length ? "bad" : ""}">
          Automatic mode complete. Imported ${result.discovery?.imported || 0} jobs, generated ${result.drafts?.count || 0} drafts, researched ${result.researched?.count || 0}, humanized ${result.humanized?.count || 0}, assessed ${result.assessed?.count || 0}.
          ${result.weekly_report ? `<br>Weekly report: ${escapeHtml(result.weekly_report)}` : ""}
          ${result.reminders?.ics_path ? `<br>Reminder calendar: ${escapeHtml(result.reminders.ics_path)} (${result.reminders.count || 0} reminders)` : ""}
          ${result.notifications ? `<br>Local notifications sent: ${result.notifications.sent || 0} (${result.notifications.due || 0} due)` : ""}
          ${result.inbox_scan ? `<br>Inbox replies: ${result.inbox_scan.imported || 0} new, ${result.inbox_scan.matched || 0} matched` : ""}
          ${result.checklist ? `<br>Checklist: ${escapeHtml(result.checklist)}` : ""}
          ${errors.length ? `<pre>${escapeHtml(errors.join("\\n"))}</pre>` : ""}
        </div>
      `;
      if (status) status.innerHTML = html;
      message("Automatic mode completed. Review Daily Review before submitting anything.");
      await load();
      showTab("dashboard");
    }

    async function exportReminders() {
      const result = await api("/api/reminders/export", {method: "POST", body: "{}"});
      message(`Exported ${result.count || 0} reminder(s) to ${result.ics_path}.`);
      const status = document.getElementById("autoStatus");
      if (status) {
        status.innerHTML = `<div class="notice">Reminder calendar exported: ${escapeHtml(result.ics_path)}<br>Summary: ${escapeHtml(result.summary_path || "")}</div>`;
      }
    }

    async function notifyDueReminders() {
      const result = await api("/api/reminders/notify-due", {method: "POST", body: "{}"});
      message(`Checked due reminders. Sent ${result.sent || 0} notification(s).`);
      const status = document.getElementById("autoStatus");
      if (status) {
        const errors = (result.errors || []).join("\\n");
        status.innerHTML = `
          <div class="${errors ? "notice bad" : "notice"}">
            Due reminders: ${result.due || 0}<br>
            Notifications sent: ${result.sent || 0}
            ${errors ? `<pre>${escapeHtml(errors)}</pre>` : ""}
          </div>
        `;
      }
    }

    async function seedStarterSources() {
      const result = await api("/api/sources/seed-starter", {method: "POST", body: "{}"});
      message(`Seeded ${result.count || 0} starter sources.`);
      await load();
    }

    async function toggleSource(id, enabled) {
      await api("/api/sources/toggle", {method: "POST", body: JSON.stringify({id, enabled})});
      await load();
    }

    async function pauseFailingSources() {
      const result = await api("/api/sources/pause-failing", {method: "POST", body: "{}"});
      message(`Paused ${result.count || 0} failing source(s).`);
      await load();
    }

    async function importUrl() {
      const url = document.getElementById("url_import").value;
      await api("/api/jobs/url", {method: "POST", body: JSON.stringify({url})});
      message("Job imported from URL.");
      await load();
      showTab("jobs");
    }

    async function importAlert() {
      const text = document.getElementById("alert_text").value;
      const source = document.getElementById("alert_source").value || "email-alert";
      const result = await api("/api/alerts/import", {method: "POST", body: JSON.stringify({text, source})});
      document.getElementById("alert_text").value = "";
      const skipped = result.skipped ? ` Skipped ${result.skipped} extra link(s) after the first 40.` : "";
      message(`Imported ${result.count || 0} job alert link(s).${skipped}`);
      await load();
      showTab("jobs");
    }

    async function addManualJob() {
      const payload = {
        title: document.getElementById("manual_title").value,
        company: document.getElementById("manual_company").value,
        location: document.getElementById("manual_location").value,
        url: document.getElementById("manual_url").value,
        description: document.getElementById("manual_description").value,
        source: "manual"
      };
      await api("/api/jobs/manual", {method: "POST", body: JSON.stringify(payload)});
      message("Manual job saved.");
      await load();
      showTab("jobs");
    }

    function targetPayload() {
      return {
        id: document.getElementById("target_id").value || null,
        company: document.getElementById("target_company").value,
        website: document.getElementById("target_website").value,
        careers_url: document.getElementById("target_careers_url").value,
        industry: document.getElementById("target_industry").value,
        priority: document.getElementById("target_priority").value,
        status: document.getElementById("target_status").value,
        source_type: document.getElementById("target_source_type").value,
        source_token: document.getElementById("target_source_token").value,
        source_query: document.getElementById("target_source_query").value,
        notes: document.getElementById("target_notes").value
      };
    }

    async function saveTarget() {
      const result = await api("/api/targets/save", {method: "POST", body: JSON.stringify(targetPayload())});
      message("Target company saved.");
      await load();
      editTarget(result.id);
    }

    async function importTargets() {
      const text = document.getElementById("target_bulk").value;
      const result = await api("/api/targets/import", {method: "POST", body: JSON.stringify({text})});
      document.getElementById("target_bulk").value = "";
      const skipped = (result.skipped || []).length ? ` Skipped ${result.skipped.length} line(s).` : "";
      message(`Imported ${result.count || 0} target companies.${skipped}`, skipped ? "bad" : "ok");
      await load();
      showTab("targets");
    }

    async function seedStarterTargets() {
      const result = await api("/api/targets/seed-starter", {method: "POST", body: "{}"});
      message(`Seeded ${result.count || 0} target companies.`);
      await load();
      showTab("targets");
    }

    async function targetToSource(id) {
      const result = await api("/api/targets/source", {method: "POST", body: JSON.stringify({id})});
      message(`Automatic source created as #${result.source_id}.`);
      await load();
      showTab("discover");
    }

    async function targetToLead(id) {
      const result = await api("/api/targets/lead", {method: "POST", body: JSON.stringify({id})});
      message(`Outreach lead created as #${result.lead_id}.`);
      await load();
      showTab("outreach");
      selectLead(result.lead_id);
    }

    async function refreshSessionMemory() {
      const result = await api("/api/session-memory");
      document.getElementById("session_memory").value = result.content || "";
      message("Session memory refreshed.");
    }

    async function generateEndSessionDraft() {
      const current = document.getElementById("session_memory").value;
      const result = await api("/api/session-memory/end-draft", {method: "POST", body: JSON.stringify({content: current})});
      document.getElementById("session_memory").value = result.content || "";
      message("End-session draft added. Review it, then save the memory file.");
    }

    async function saveSessionMemory() {
      const content = document.getElementById("session_memory").value;
      const result = await api("/api/session-memory/save", {method: "POST", body: JSON.stringify({content})});
      state.session_memory = result.content || content;
      message("SESSION_MEMORY.md saved.");
    }

    function leadPayloadFrom(prefix, id = null) {
      return {
        id,
        company: document.getElementById(`${prefix}_company`).value,
        website: document.getElementById(`${prefix}_website`).value,
        industry: document.getElementById(`${prefix}_industry`).value,
        contact_name: document.getElementById(`${prefix}_contact_name`).value,
        contact_role: document.getElementById(`${prefix}_contact_role`).value,
        contact_email: document.getElementById(`${prefix}_contact_email`).value,
        source_url: document.getElementById(`${prefix}_source_url`).value,
        company_notes: document.getElementById(`${prefix}_company_notes`).value,
        status: document.getElementById(`${prefix}_status`)?.value || "found",
        outreach_email: document.getElementById(`${prefix}_outreach_email`)?.value || ""
      };
    }

    async function saveLead() {
      const payload = leadPayloadFrom("lead");
      await api("/api/leads/save", {method: "POST", body: JSON.stringify(payload)});
      ["company", "website", "industry", "source_url", "contact_name", "contact_role", "contact_email", "company_notes"].forEach(key => {
        document.getElementById(`lead_${key}`).value = "";
      });
      message("Company lead saved.");
      await load();
      showTab("outreach");
    }

    async function saveLeadEdit() {
      if (!selectedLead) return;
      const payload = leadPayloadFrom("edit_lead", selectedLead.id);
      await api("/api/leads/save", {method: "POST", body: JSON.stringify(payload)});
      message("Company lead saved.");
      await load();
    }

    async function generateLeadEmail() {
      if (!selectedLead) return;
      const payload = leadPayloadFrom("edit_lead", selectedLead.id);
      const result = await api("/api/leads/generate", {method: "POST", body: JSON.stringify(payload)});
      document.getElementById("edit_lead_outreach_email").value = result.outreach_email || "";
      message("Personalized outreach generated.");
      await load();
    }

    async function humanizeLeadEmail() {
      if (!selectedLead) return;
      const result = await api("/api/leads/humanize", {
        method: "POST",
        body: JSON.stringify({
          id: selectedLead.id,
          outreach_email: document.getElementById("edit_lead_outreach_email").value
        })
      });
      document.getElementById("edit_lead_outreach_email").value = result.outreach_email || "";
      const check = result.check || {};
      const flagged = (check.flags || []).length + (check.long_sentence_count || 0);
      message(flagged ? `Humanized outreach, but ${flagged} voice issue(s) still need review.` : "Humanized outreach in Phillip's voice.");
      await load();
    }

    async function setLeadStatus(id, status) {
      await api("/api/leads/status", {method: "POST", body: JSON.stringify({id, status})});
      message(`Lead marked ${status}.`);
      await load();
    }

    async function sendLeadEmail() {
      if (!selectedLead) return;
      await saveLeadEdit();
      const to = prompt("Recipient email address for this outreach:", document.getElementById("edit_lead_contact_email").value || "");
      if (!to) return;
      await api("/api/leads/send", {method: "POST", body: JSON.stringify({id: selectedLead.id, to})});
      message("Outreach email sent and follow-up scheduled.");
      await load();
    }

    async function setJobStatus(id, status) {
      await api("/api/jobs/status", {method: "POST", body: JSON.stringify({id, status})});
      await load();
    }

    async function rescoreJobs() {
      const result = await api("/api/jobs/rescore", {method: "POST", body: "{}"});
      message(`Rescored ${result.count || 0} jobs.`);
      await load();
      renderJobs();
    }

    async function shortlistTopJobs() {
      const result = await api("/api/jobs/shortlist-top", {method: "POST", body: JSON.stringify({limit: 5})});
      message(`Shortlisted ${result.count || 0} top jobs.`);
      await load();
      document.getElementById("job_filter").value = "shortlisted";
      renderJobs();
    }

    async function generateShortlistDrafts() {
      const result = await api("/api/applications/generate-bulk", {method: "POST", body: JSON.stringify({status: "shortlisted", limit: 5})});
      message(`Generated ${result.count || 0} application drafts from shortlisted jobs.`);
      await load();
      showTab("applications");
    }

    async function generateApplication(job_id) {
      await api("/api/applications/generate", {method: "POST", body: JSON.stringify({job_id})});
      message("Application draft generated.");
      await load();
      showTab("applications");
    }

    async function saveApplication() {
      if (!selectedApplication) return;
      const payload = {
        id: selectedApplication.id,
        status: document.getElementById("edit_status").value,
        contact_email: document.getElementById("edit_contact_email").value,
        contact_name: document.getElementById("edit_contact_name").value,
        contact_role: document.getElementById("edit_contact_role").value,
        company_notes: document.getElementById("edit_company_notes").value,
        research_url: document.getElementById("edit_research_url").value,
        research_notes: document.getElementById("edit_research_notes").value,
        research_sources: document.getElementById("edit_research_sources").value,
        next_follow_up: document.getElementById("edit_next_follow_up").value,
        cover_letter: document.getElementById("edit_cover_letter").value,
        cv_notes: document.getElementById("edit_cv_notes").value,
        answers: document.getElementById("edit_answers").value,
        follow_up: document.getElementById("edit_follow_up").value
      };
      await api("/api/applications/save", {method: "POST", body: JSON.stringify(payload)});
      message("Application saved and documents regenerated.");
      await load();
    }

    async function regenerateFollowUp() {
      if (!selectedApplication) return;
      const payload = {
        id: selectedApplication.id,
        contact_email: document.getElementById("edit_contact_email").value,
        contact_name: document.getElementById("edit_contact_name").value,
        contact_role: document.getElementById("edit_contact_role").value,
        company_notes: document.getElementById("edit_company_notes").value
      };
      const result = await api("/api/applications/regenerate-followup", {method: "POST", body: JSON.stringify(payload)});
      document.getElementById("edit_follow_up").value = result.follow_up || "";
      message("Personalized follow-up regenerated.");
      await load();
    }

    async function humanizeApplication() {
      if (!selectedApplication) return;
      const payload = {
        id: selectedApplication.id,
        company_notes: document.getElementById("edit_company_notes").value,
        cover_letter: document.getElementById("edit_cover_letter").value,
        answers: document.getElementById("edit_answers").value,
        follow_up: document.getElementById("edit_follow_up").value
      };
      const result = await api("/api/applications/humanize", {method: "POST", body: JSON.stringify(payload)});
      document.getElementById("edit_cover_letter").value = result.cover_letter || "";
      document.getElementById("edit_answers").value = result.answers || "";
      document.getElementById("edit_follow_up").value = result.follow_up || "";
      const flagged = Object.values(result.checks || {}).reduce((sum, check) => sum + ((check.flags || []).length || 0) + (check.long_sentence_count || 0), 0);
      message(flagged ? `Humanized copy, but ${flagged} voice issue(s) still need review.` : "Humanized sent copy in Phillip's voice.");
      await load();
    }

    async function researchApplication() {
      if (!selectedApplication) return;
      const payload = {
        id: selectedApplication.id,
        research_url: document.getElementById("edit_research_url").value,
        company_notes: document.getElementById("edit_company_notes").value
      };
      const result = await api("/api/applications/research", {method: "POST", body: JSON.stringify(payload)});
      document.getElementById("edit_research_url").value = result.research_url || "";
      document.getElementById("edit_research_notes").value = result.research_notes || "";
      document.getElementById("edit_research_sources").value = result.research_sources || "";
      message("Company research notes generated.");
      await load();
    }

    async function prepareApplicationForm() {
      if (!selectedApplication) return;
      await saveApplication();
      const result = await api("/api/applications/prepare-form", {method: "POST", body: JSON.stringify({id: selectedApplication.id})});
      message(`Visible browser launched for form preparation. Process ${result.pid}. Review everything manually and submit yourself.`);
    }

    async function saveFormFillFeedback() {
      if (!selectedApplication) return;
      const payload = {
        application_id: selectedApplication.id,
        worked: document.getElementById("form_feedback_worked").value,
        missed: document.getElementById("form_feedback_missed").value,
        wrong: document.getElementById("form_feedback_wrong").value,
        notes: document.getElementById("form_feedback_notes").value
      };
      await api("/api/applications/form-feedback", {method: "POST", body: JSON.stringify(payload)});
      ["worked", "missed", "wrong", "notes"].forEach(key => {
        document.getElementById(`form_feedback_${key}`).value = "";
      });
      message("Form-fill feedback saved.");
      await load();
    }

    async function prepareApplicationFromDashboard(id) {
      selectApplication(id, false);
      await prepareApplicationForm();
      showTab("applications");
    }

    async function runFormFillSmokeTest() {
      const result = await api("/api/form-fill/smoke", {method: "POST", body: "{}"});
      message(`Smoke-test browser launched. Process ${result.pid}. Check that the fake form fields are filled, then close the browser.`);
    }

    async function markApplicationSubmitted() {
      if (!selectedApplication) return;
      document.getElementById("edit_status").value = "submitted";
      const followUp = new Date();
      followUp.setDate(followUp.getDate() + 7);
      document.getElementById("edit_next_follow_up").value = followUp.toISOString().slice(0, 10);
      await saveApplication();
      await setJobStatus(selectedApplication.job_id, "applied");
      message("Application marked submitted. Follow-up scheduled for 7 days from today.");
    }

    async function markApplicationSubmittedFromDashboard(id) {
      selectApplication(id, false);
      await markApplicationSubmitted();
      showTab("applications");
    }

    async function saveEmailConfig() {
      const payload = {
        host: document.getElementById("email_host").value,
        port: document.getElementById("email_port").value,
        user: document.getElementById("email_user").value,
        from: document.getElementById("email_from").value,
        to: document.getElementById("email_to").value,
        password: document.getElementById("email_password").value,
        starttls: document.getElementById("email_starttls").checked
      };
      await api("/api/email/config", {method: "POST", body: JSON.stringify(payload)});
      document.getElementById("email_password").value = "";
      message("Email settings saved locally.");
      await load();
    }

    async function saveInboxConfig() {
      const payload = {
        host: document.getElementById("inbox_host").value,
        port: document.getElementById("inbox_port").value,
        user: document.getElementById("inbox_user").value,
        mailbox: document.getElementById("inbox_mailbox").value,
        lookback_days: document.getElementById("inbox_lookback_days").value,
        password: document.getElementById("inbox_password").value,
        ssl: document.getElementById("inbox_ssl").checked
      };
      await api("/api/email/inbox-config", {method: "POST", body: JSON.stringify(payload)});
      document.getElementById("inbox_password").value = "";
      message("Inbox settings saved locally.");
      await load();
    }

    async function scanInbox() {
      await saveInboxConfig();
      const result = await api("/api/email/scan-inbox", {method: "POST", body: JSON.stringify({limit: 80})});
      message(`Inbox scan complete: ${result.imported || 0} new message(s), ${result.matched || 0} matched.`);
      await load();
      showTab("email");
    }

    async function markInbox(id, status, applicationStatus = "", leadStatus = "") {
      await api("/api/inbox/status", {
        method: "POST",
        body: JSON.stringify({id, status, application_status: applicationStatus, lead_status: leadStatus})
      });
      message("Inbox reply updated.");
      await load();
      showTab("email");
    }

    async function matchInboxToApplication(id) {
      const options = (state.applications || [])
        .slice()
        .sort((a, b) => Number(b.id) - Number(a.id))
        .slice(0, 20)
        .map(app => `${app.id}: ${app.company} - ${app.title}`)
        .join("\\n");
      const value = prompt(`Enter application ID to match this reply:\\n\\n${options}`);
      if (!value) return;
      const applicationId = Number(String(value).split(":")[0].trim());
      if (!applicationId) return message("Enter a valid application ID.", "bad");
      await api("/api/inbox/match", {method: "POST", body: JSON.stringify({id, application_id: applicationId})});
      message("Inbox reply matched to application.");
      await load();
      showTab("email");
    }

    async function matchInboxToLead(id) {
      const options = (state.leads || [])
        .slice()
        .sort((a, b) => Number(b.id) - Number(a.id))
        .slice(0, 20)
        .map(lead => `${lead.id}: ${lead.company || "Unnamed company"} ${lead.contact_email ? "- " + lead.contact_email : ""}`)
        .join("\\n");
      const value = prompt(`Enter outreach lead ID to match this reply:\\n\\n${options || "No outreach leads saved."}`);
      if (!value) return;
      const leadId = Number(String(value).split(":")[0].trim());
      if (!leadId) return message("Enter a valid outreach lead ID.", "bad");
      await api("/api/inbox/match", {method: "POST", body: JSON.stringify({id, lead_id: leadId})});
      message("Inbox reply matched to outreach lead.");
      await load();
      showTab("email");
    }

    async function sendTestEmail() {
      await saveEmailConfig();
      await api("/api/email/test", {method: "POST", body: JSON.stringify({to: document.getElementById("email_to").value})});
      message("Test email sent.");
    }

    async function sendFollowUp() {
      if (!selectedApplication) return;
      await sendFollowUpFor(selectedApplication.id);
    }

    async function sendFollowUpFor(id) {
      const app = state.applications.find(item => item.id === id) || selectedApplication;
      if (!app) return;
      if (!selectedApplication || selectedApplication.id !== id) {
        selectedApplication = app;
      }
      const existing = document.getElementById("edit_contact_email")?.value || app.contact_email || "";
      const to = prompt("Recipient email address for this follow-up:", existing);
      if (!to) return;
      if (document.getElementById("edit_contact_email")) {
        document.getElementById("edit_contact_email").value = to;
        await saveApplication();
      }
      await api("/api/email/send-followup", {method: "POST", body: JSON.stringify({id, to})});
      message("Follow-up email sent.");
      await load();
    }

    function mailto(app) {
      const subject = encodeURIComponent(`Follow-up on ${app.title} application`);
      const body = encodeURIComponent(app.follow_up || "");
      return `mailto:?subject=${subject}&body=${body}`;
    }

    function escapeHtml(value) {
      return String(value ?? "").replace(/[&<>"']/g, ch => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
      }[ch]));
    }

    function escapeAttr(value) {
      return escapeHtml(value).replace(/`/g, "&#96;");
    }

    load().catch(error => message(error.message, "bad"));
  </script>
</body>
</html>
"""


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
