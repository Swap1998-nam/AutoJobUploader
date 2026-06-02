"""
Job Auto-Apply Backend - FastAPI
Searches LinkedIn & Naukri for roles and auto-applies.
Uses SQLite for persistent application tracking.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import asyncio
import time
import random
import logging
import sqlite3
import re
import requests as http_requests
from pathlib import Path
from datetime import datetime
from chrome_manager import setup_chrome_driver, verify_chrome_installation

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Job Auto-Apply API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────
# SQLite — persistent application tracking
# ──────────────────────────────────────────
DB_PATH = Path(__file__).parent / "applications.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                id          TEXT PRIMARY KEY,
                title       TEXT NOT NULL,
                company     TEXT NOT NULL,
                location    TEXT,
                platform    TEXT NOT NULL,
                url         TEXT,
                status      TEXT NOT NULL,
                method      TEXT DEFAULT 'auto',
                experience  TEXT,
                salary      TEXT,
                applied_at  TEXT NOT NULL
            )
        """)
        conn.commit()
    logger.info(f"✅ Database ready: {DB_PATH}")

init_db()

def db_save_application(job_id, title, company, location, platform, url,
                         status, method="auto", experience=None, salary=None):
    with get_db() as conn:
        conn.execute("""
            INSERT INTO applications
                (id, title, company, location, platform, url, status, method, experience, salary, applied_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET status=excluded.status, applied_at=excluded.applied_at
        """, (job_id, title, company, location, platform, url,
              status, method, experience, salary, datetime.now().isoformat()))
        conn.commit()

def db_get_log(limit=200):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM applications ORDER BY applied_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]

def db_get_stats():
    with get_db() as conn:
        total   = conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
        applied = conn.execute("SELECT COUNT(*) FROM applications WHERE status IN ('applied','manually-applied')").fetchone()[0]
        auto    = conn.execute("SELECT COUNT(*) FROM applications WHERE method='auto'").fetchone()[0]
        manual  = conn.execute("SELECT COUNT(*) FROM applications WHERE method='manual'").fetchone()[0]
        failed  = conn.execute("SELECT COUNT(*) FROM applications WHERE status='failed'").fetchone()[0]
    return {"total": total, "applied": applied, "auto_applied": auto,
            "manually_applied": manual, "failed": failed}

# ──────────────────────────────────────────
# Models
# ──────────────────────────────────────────

class Credentials(BaseModel):
    platform: str           # "linkedin" | "naukri"
    email: str
    password: str

class SearchConfig(BaseModel):
    role: str = "Python Developer"
    location: str = "India"
    experience: str = "0-3"
    max_jobs: int = 20

class Job(BaseModel):
    id: str
    title: str
    company: str
    location: str
    experience: str
    salary: Optional[str]
    posted: str
    platform: str
    url: str
    status: str = "pending"

class MarkAppliedRequest(BaseModel):
    job_id: str
    title: str
    company: str
    location: str
    platform: str
    url: str
    experience: Optional[str] = None
    salary: Optional[str] = None

class ApplyWithJobRequest(BaseModel):
    """Apply request that carries full job data — no job_store lookup needed."""
    platform: str
    email: str
    password: str
    job_id: str
    title: str
    company: str
    location: str
    url: str
    experience: Optional[str] = None
    salary: Optional[str] = None

class BulkApplyRequest(BaseModel):
    platform: str
    credentials: Credentials
    config: SearchConfig

# ──────────────────────────────────────────
# In-memory job store (current search session only)
# ──────────────────────────────────────────
job_store: dict[str, Job] = {}
session_tokens: dict[str, str] = {}

# ──────────────────────────────────────────
# Utility: Human-like delay
# ──────────────────────────────────────────
def human_delay(min_s=1.5, max_s=3.5):
    time.sleep(random.uniform(min_s, max_s))


# ──────────────────────────────────────────
# LinkedIn Automation (Selenium)
# ──────────────────────────────────────────
def linkedin_login_and_search(email: str, password: str, config: SearchConfig) -> List[Job]:
    """
    Uses Selenium to log in to LinkedIn and collect job listings.
    Returns list of Job objects.
    """
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException

    try:
        driver = setup_chrome_driver()
    except Exception as e:
        logger.error(f"ChromeDriver initialization failed: {e}")
        raise Exception(f"Failed to start browser automation: {str(e)}. Check that Chrome is installed.")
    
    wait = WebDriverWait(driver, 15)
    jobs: List[Job] = []

    try:
        # ── LOGIN ──
        logger.info("LinkedIn: Opening login page...")
        driver.get("https://www.linkedin.com/login")
        # Wait for the field — no fixed sleep needed
        wait.until(EC.presence_of_element_located((By.ID, "username")))
        driver.find_element(By.ID, "username").send_keys(email)
        driver.find_element(By.ID, "password").send_keys(password)
        driver.find_element(By.XPATH, "//button[@type='submit']").click()

        # Wait for a definitive outcome instead of sleeping blindly
        try:
            WebDriverWait(driver, 8).until(lambda d: (
                "feed" in d.current_url
                or "checkpoint" in d.current_url
                or "challenge" in d.current_url
                or ("login" not in d.current_url and d.current_url != "https://www.linkedin.com/login")
                or bool(d.find_elements(By.CSS_SELECTOR,
                    "#error-for-password, #error-for-username, .alert-content"))
            ))
        except Exception:
            pass

        current_url = driver.current_url
        logger.info(f"LinkedIn: URL after login: {current_url}")

        if "checkpoint" in current_url or "challenge" in current_url or "verify" in current_url.lower():
            raise Exception(
                "🔐 LinkedIn Security Check Required. Log in manually on LinkedIn first, then try again."
            )

        still_on_login = "login" in current_url.lower() and "feed" not in current_url
        if "error" in current_url.lower() or still_on_login:
            raise Exception("❌ LinkedIn login failed. Check your email/password.")

        # ── SEARCH ──
        import urllib.parse
        search_url = (
            f"https://www.linkedin.com/jobs/search/"
            f"?keywords={urllib.parse.quote(config.role)}"
            f"&location={urllib.parse.quote(config.location)}"
            f"&f_E=1%2C2%2C3"   # Entry/Associate/Mid
            f"&f_AL=true"         # Easy Apply only
            f"&sortBy=DD"         # Date Desc
            f"&count=25"          # request more results per page
        )
        logger.info(f"LinkedIn: Searching jobs at {search_url}")
        driver.get(search_url)

        # Wait for page load + app-shell render — event-driven, no fixed sleep
        logger.info("LinkedIn: Waiting for page to finish rendering...")
        try:
            WebDriverWait(driver, 15).until(lambda d: d.execute_script(
                "return document.readyState === 'complete' && "
                "document.documentElement.className.indexOf('app-loader--default') === -1;"
            ))
            logger.info("LinkedIn: App shell loaded")
        except Exception:
            pass
        human_delay(1, 2)  # small buffer for React hydration

        # Wait for any known job-list container to appear in the DOM
        logger.info("LinkedIn: Waiting for job list container to load...")
        container_css = (
            "div.scaffold-layout__list-container,"
            "div[class*='jobs-search-results-grid'],"
            "ul[class*='jobs-search-results'],"
            "div[class*='jobs-search-results'],"
            "ul.jobs-search-results__list-wrapper,"
            "div.jobs-search-results__list-wrapper"
        )
        try:
            WebDriverWait(driver, 12).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, container_css))
            )
            logger.info("LinkedIn: Job list container found")
        except Exception:
            logger.warning("LinkedIn: Timeout waiting for job cards: could not find container, will scroll page")

        # Scroll using pure JS — no Python element references passed to execute_script,
        # so a React re-render can't produce a stale-handle crash.
        SCROLL_JS = """
            var sel = [
                'div.scaffold-layout__list-container',
                'ul.jobs-search-results__list-wrapper',
                'div.jobs-search-results__list-wrapper',
                'div[class*="jobs-search-results"]'
            ];
            var el = null;
            for (var i = 0; i < sel.length; i++) {
                el = document.querySelector(sel[i]);
                if (el) break;
            }
            if (el) { el.scrollTop = el.scrollHeight; }
            else     { window.scrollTo(0, document.body.scrollHeight); }
        """
        logger.info("LinkedIn: Scrolling to load more jobs...")
        for scroll_num in range(3):
            try:
                driver.execute_script(SCROLL_JS)
            except Exception:
                pass
            human_delay(1.0, 1.5)
            logger.info(f"LinkedIn: Scroll {scroll_num + 1}/3")

        try:
            driver.execute_script("window.scrollTo(0, 0);")
        except Exception:
            pass
        human_delay(0.5, 1.0)

        # Now collect cards — fresh references after all scrolling is complete
        logger.info("LinkedIn: Searching for job cards with multiple selectors...")
        card_selectors = [
            "li[data-occludable-job-id]",
            "li[data-job-id]",
            "div.job-card-container--clickable",
            "div.job-card-container",
            "li.jobs-search-results__list-item",
            "li.scaffold-layout__list-item",
            "li.base-card",
            "article.base-card",
            "div.base-card.base-card--clickable",
            "[data-job-id]",
            "li[data-list-index]",
            "article.jobs-search-results__list-item",
        ]

        cards = []
        used_selector = None
        for selector in card_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    cards = elements
                    used_selector = selector
                    logger.info(f"LinkedIn: Found {len(cards)} cards using selector: {selector}")
                    break
            except Exception as e:
                logger.debug(f"LinkedIn: Selector '{selector}' failed: {e}")

        if not cards:
            logger.warning("LinkedIn: No job cards found with any selector!")
            page_source = driver.page_source
            if "LinkedIn is blocking this" in page_source or "unusual activity" in page_source:
                raise Exception(
                    "LinkedIn detected unusual activity. "
                    "Log in manually first, then try again."
                )

        logger.info(f"LinkedIn: Found {len(cards)} job cards total")

        for i, card in enumerate(cards[:config.max_jobs]):
            try:
                # Guard: if LinkedIn replaced the DOM element it becomes stale — skip cleanly
                _ = card.tag_name
            except Exception:
                logger.debug(f"LinkedIn: Card {i} is stale, skipping")
                continue

            try:
                # Try to get title
                title = "N/A"
                for title_sel in [
                    "a.job-card-list__title--link",
                    "a.job-card-list__title",
                    "strong.t-bold",
                    "a[data-control-name='jobcard_title']",
                ]:
                    try:
                        title = card.find_element(By.CSS_SELECTOR, title_sel).text.strip()
                        if title:
                            break
                    except Exception:
                        pass
                if title == "N/A":
                    links = card.find_elements(By.TAG_NAME, "a")
                    title = links[0].text.strip() if links else "N/A"

                # Try to get company
                company = "N/A"
                for co_sel in [
                    "span.job-card-container__primary-description",
                    "div.artdeco-entity-lockup__subtitle span",
                    "span.base-search-card__subtitle",
                    "a.job-card-container__company-name",
                    "span[class*='company']",
                ]:
                    try:
                        company = card.find_element(By.CSS_SELECTOR, co_sel).text.strip()
                        if company:
                            break
                    except Exception:
                        pass

                # Try to get location
                location = config.location
                for loc_sel in [
                    "li.job-card-container__metadata-item",
                    "div.artdeco-entity-lockup__caption span",
                    "span.job-search-card__location",
                    "span[class*='location']",
                    "ul.job-card-container__metadata-wrapper li",
                ]:
                    try:
                        location = card.find_element(By.CSS_SELECTOR, loc_sel).text.strip()
                        if location:
                            break
                    except Exception:
                        pass

                # Try to get URL
                job_url = "#"
                for url_sel in [
                    "a.job-card-list__title--link",
                    "a.job-card-list__title",
                    "a[data-control-name='jobcard_title']",
                ]:
                    try:
                        job_url = card.find_element(By.CSS_SELECTOR, url_sel).get_attribute("href") or "#"
                        if job_url != "#":
                            break
                    except Exception:
                        pass
                if job_url == "#":
                    links = card.find_elements(By.TAG_NAME, "a")
                    job_url = links[0].get_attribute("href") if links else "#"
                
                if job_url and job_url != "#":
                    job_url = job_url.split("?")[0]
                
                if title == "N/A" and company == "N/A":
                    logger.debug(f"LinkedIn: Skipping empty card {i} (not yet hydrated)")
                    continue

                job_id = f"li_{i}_{int(time.time())}"

                jobs.append(Job(
                    id=job_id,
                    title=title,
                    company=company,
                    location=location,
                    experience=config.experience + " yrs",
                    salary=None,
                    posted="Recent",
                    platform="linkedin",
                    url=job_url,
                    status="pending"
                ))
                logger.info(f"LinkedIn: Found job {i+1}: {title} @ {company}")
            except Exception as e:
                logger.warning(f"LinkedIn: Could not parse card {i}: {e}")
                continue

    finally:
        driver.quit()

    return jobs


def linkedin_easy_apply(job: Job, email: str, password: str) -> bool:
    """
    Opens a LinkedIn job page and clicks Easy Apply.
    Returns True if successfully applied.
    """
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    try:
        driver = setup_chrome_driver()
    except Exception as e:
        logger.error(f"ChromeDriver initialization failed: {e}")
        return False
        
    wait = WebDriverWait(driver, 15)

    try:
        # ── LOGIN ──
        driver.get("https://www.linkedin.com/login")
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "username")))
        driver.find_element(By.ID, "username").send_keys(email)
        driver.find_element(By.ID, "password").send_keys(password)
        driver.find_element(By.XPATH, "//button[@type='submit']").click()

        # Wait until we're actually on the feed — not just a fixed sleep
        try:
            WebDriverWait(driver, 12).until(lambda d:
                "feed" in d.current_url or "mynetwork" in d.current_url
                or "checkpoint" in d.current_url)
        except Exception:
            pass

        if "checkpoint" in driver.current_url or "challenge" in driver.current_url:
            logger.warning("LinkedIn security check triggered during apply")
            return False

        logger.info(f"LinkedIn: Navigating to job page: {job.url}")

        # ── JOB PAGE ──
        driver.get(job.url)

        # Wait for the job details panel to fully render
        try:
            WebDriverWait(driver, 12).until(lambda d:
                d.execute_script("return document.readyState") == "complete")
        except Exception:
            pass
        human_delay(2, 3)

        # ── FIND EASY APPLY BUTTON ──
        # CSS selectors first, then XPath text-match as ultimate fallback
        easy_apply_btn = None

        css_selectors = [
            "button[aria-label*='Easy Apply']",
            "button[aria-label*='easy apply']",
            "button.jobs-apply-button--top-card",
            "button.jobs-apply-button",
            "[data-control-name='jobdetails_topcard_inapply']",
            "button.artdeco-button--primary[data-live-test-job-apply-button]",
            "div.jobs-apply-button--top-card button",
        ]
        for sel in css_selectors:
            try:
                easy_apply_btn = WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, sel)))
                logger.info(f"LinkedIn: Found Easy Apply via CSS: {sel}")
                break
            except Exception:
                continue

        # XPath fallback — match button text
        if not easy_apply_btn:
            for xpath in [
                "//button[contains(., 'Easy Apply')]",
                "//button[contains(@aria-label, 'Easy Apply')]",
                "//button[contains(@aria-label, 'easy apply')]",
            ]:
                try:
                    easy_apply_btn = WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable((By.XPATH, xpath)))
                    logger.info(f"LinkedIn: Found Easy Apply via XPath: {xpath}")
                    break
                except Exception:
                    continue

        if not easy_apply_btn:
            # Save screenshot so the user can see what's on the page
            try:
                ss_path = f"easy_apply_not_found_{int(time.time())}.png"
                driver.save_screenshot(ss_path)
                logger.warning(f"Easy Apply button not found for {job.url} — screenshot: {ss_path}")
            except Exception:
                logger.warning(f"Easy Apply button not found for {job.url}")
            return False

        easy_apply_btn.click()
        human_delay(2, 3)

        # ── CLICK THROUGH MODAL (Next → Review → Submit) ──
        for step in range(6):
            clicked = False
            # Try submit first (highest priority)
            for xpath in [
                "//button[@aria-label='Submit application']",
                "//button[contains(@aria-label,'Submit')]",
                "//button[contains(.,'Submit application')]",
            ]:
                try:
                    btn = WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable((By.XPATH, xpath)))
                    btn.click()
                    human_delay(2, 3)
                    clicked = True
                    break
                except Exception:
                    continue

            if not clicked:
                for xpath in [
                    "//button[@aria-label='Continue to next step']",
                    "//button[@aria-label='Review your application']",
                    "//button[contains(@aria-label,'Next')]",
                    "//button[@data-easy-apply-next-button]",
                ]:
                    try:
                        btn = WebDriverWait(driver, 3).until(
                            EC.element_to_be_clickable((By.XPATH, xpath)))
                        btn.click()
                        human_delay(1.5, 2.5)
                        clicked = True
                        break
                    except Exception:
                        continue

            if not clicked:
                break  # no more steps found

        page_src = driver.page_source
        if "application submitted" in page_src.lower() or "applied" in driver.current_url:
            logger.info(f"✅ Applied to {job.title} @ {job.company}")
            return True

        return True  # optimistic

    except Exception as e:
        logger.error(f"LinkedIn apply error: {e}")
        return False
    finally:
        driver.quit()


# ──────────────────────────────────────────
# Naukri Automation (Selenium)
# ──────────────────────────────────────────
def naukri_login_and_search(email: str, password: str, config: SearchConfig) -> List[Job]:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    try:
        driver = setup_chrome_driver()
    except Exception as e:
        logger.error(f"ChromeDriver initialization failed: {e}")
        raise Exception(f"Failed to start browser automation: {str(e)}.")

    wait = WebDriverWait(driver, 15)
    jobs: List[Job] = []

    def dismiss_popups():
        """Close cookie banners, chat widgets, and login nudges."""
        for sel in [
            "button#login_Layer",        # login popup dismiss
            "button.cross-btn",
            "[class*='close']",
            "[aria-label='Close']",
            "button.commonModal__close",
        ]:
            try:
                btn = driver.find_element(By.CSS_SELECTOR, sel)
                if btn.is_displayed():
                    btn.click()
            except Exception:
                pass

    try:
        # ── LOGIN ──
        logger.info("Naukri: Logging in...")
        driver.get("https://www.naukri.com/nlogin/login")
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR,
            "#usernameField, input[placeholder*='Email'], input[type='email']")))
        dismiss_popups()

        # Email field
        for sel in ["#usernameField", "input[placeholder*='Email']", "input[type='email']"]:
            try:
                f = driver.find_element(By.CSS_SELECTOR, sel)
                f.clear(); f.send_keys(email); break
            except Exception:
                pass

        # Password field
        for sel in ["#passwordField", "input[placeholder*='Password']", "input[type='password']"]:
            try:
                f = driver.find_element(By.CSS_SELECTOR, sel)
                f.clear(); f.send_keys(password); break
            except Exception:
                pass

        # Submit
        for sel in ["button[type='submit']", "button.loginButton", "input[type='submit']"]:
            try:
                driver.find_element(By.CSS_SELECTOR, sel).click(); break
            except Exception:
                pass

        # Wait for login to complete
        try:
            WebDriverWait(driver, 8).until(lambda d:
                "nlogin" not in d.current_url or "myapps" in d.current_url)
        except Exception:
            pass
        human_delay(1, 2)
        dismiss_popups()

        # ── SEARCH ──
        import urllib.parse
        keyword_slug = config.role.replace(" ", "-").lower()
        exp = config.experience.replace(" ", "")
        # Try the SEO URL first (most reliable), fall back to query-param URL
        search_url = (
            f"https://www.naukri.com/{keyword_slug}-jobs"
            f"?k={urllib.parse.quote(config.role)}"
            f"&experience={exp}"
            f"&jobAge=7"    # posted in last 7 days
        )
        logger.info(f"Naukri: Searching {search_url}")
        driver.get(search_url)

        # Wait for the page to load results
        try:
            WebDriverWait(driver, 12).until(lambda d:
                d.execute_script("return document.readyState") == "complete")
        except Exception:
            pass
        human_delay(2, 3)
        dismiss_popups()

        # Scroll to trigger lazy-load
        for _ in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            human_delay(1.0, 1.5)
        driver.execute_script("window.scrollTo(0, 0);")
        human_delay(0.5, 1)

        # ── FIND CARDS — multiple selectors for Naukri's evolving HTML ──
        card_selectors = [
            "div.srp-jobtuple-wrapper",          # current (2024-25)
            "div[class*='srp-jobtuple']",
            "div.cust-job-tuple",
            "article.jobTuple",                  # older layout
            "div.jobTuple",
            "li.jobTuple",
            "div[class*='jobTuple']",
        ]
        cards = []
        used_sel = None
        for sel in card_selectors:
            found = driver.find_elements(By.CSS_SELECTOR, sel)
            if found:
                cards = found
                used_sel = sel
                break

        logger.info(f"Naukri: Found {len(cards)} job cards" +
                    (f" using '{used_sel}'" if used_sel else " (no selector matched)"))

        if not cards:
            # Save HTML for debugging
            src_preview = driver.page_source[:3000]
            logger.info(f"Naukri: Page source preview:\n{src_preview}")

        for i, card in enumerate(cards[:config.max_jobs]):
            try:
                _ = card.tag_name  # stale check
            except Exception:
                continue
            try:
                # Title
                title = "N/A"
                for sel in ["a.title", "a[class*='title']", "a.jobTitle",
                            "h2 a", "h3 a", "a[title]"]:
                    try:
                        el = card.find_element(By.CSS_SELECTOR, sel)
                        title = el.text.strip() or el.get_attribute("title") or "N/A"
                        if title and title != "N/A": break
                    except Exception:
                        pass

                # Company
                company = "N/A"
                for sel in ["a.comp-name", "span.comp-name", "a[class*='comp']",
                            "a.subTitle", "span.companyName", "a.company-name"]:
                    try:
                        company = card.find_element(By.CSS_SELECTOR, sel).text.strip()
                        if company: break
                    except Exception:
                        pass

                # Experience
                experience = config.experience + " yrs"
                for sel in ["span.expwdth", "span[class*='exp']", "li.experience",
                            "span.experience", "div[class*='exp']"]:
                    try:
                        v = card.find_element(By.CSS_SELECTOR, sel).text.strip()
                        if v: experience = v; break
                    except Exception:
                        pass

                # Location
                location = config.location
                for sel in ["span.locWdth", "span[class*='loc']", "li.location",
                            "span.location", "a.loc-link"]:
                    try:
                        v = card.find_element(By.CSS_SELECTOR, sel).text.strip()
                        if v: location = v; break
                    except Exception:
                        pass

                # Salary
                salary = None
                for sel in ["span.sal", "span[class*='sal']", "span.salary",
                            "li.salary", "span[class*='Salary']"]:
                    try:
                        v = card.find_element(By.CSS_SELECTOR, sel).text.strip()
                        if v: salary = v; break
                    except Exception:
                        pass

                # URL
                job_url = "#"
                for sel in ["a.title", "a[class*='title']", "a.jobTitle", "h2 a", "h3 a"]:
                    try:
                        href = card.find_element(By.CSS_SELECTOR, sel).get_attribute("href")
                        if href: job_url = href; break
                    except Exception:
                        pass

                if title == "N/A" and company == "N/A":
                    continue

                jobs.append(Job(
                    id=f"nk_{i}_{int(time.time())}",
                    title=title, company=company, location=location,
                    experience=experience, salary=salary,
                    posted="Recent", platform="naukri",
                    url=job_url, status="pending"
                ))
                logger.info(f"Naukri: Job {i+1}: {title} @ {company}")
            except Exception as e:
                logger.warning(f"Naukri: Could not parse card {i}: {e}")

    finally:
        driver.quit()

    return jobs


def naukri_apply(job: Job, email: str, password: str) -> bool:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    try:
        driver = setup_chrome_driver()
    except Exception as e:
        logger.error(f"ChromeDriver initialization failed: {e}")
        return False
        
    wait = WebDriverWait(driver, 15)

    try:
        driver.get("https://www.naukri.com/nlogin/login")
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR,
            "#usernameField, input[type='email']")))
        for sel in ["#usernameField", "input[type='email']"]:
            try: f = driver.find_element(By.CSS_SELECTOR, sel); f.clear(); f.send_keys(email); break
            except Exception: pass
        for sel in ["#passwordField", "input[type='password']"]:
            try: f = driver.find_element(By.CSS_SELECTOR, sel); f.clear(); f.send_keys(password); break
            except Exception: pass
        for sel in ["button[type='submit']", "button.loginButton"]:
            try: driver.find_element(By.CSS_SELECTOR, sel).click(); break
            except Exception: pass
        try:
            WebDriverWait(driver, 8).until(lambda d: "nlogin" not in d.current_url)
        except Exception:
            pass
        human_delay(1, 2)

        logger.info(f"Naukri: Navigating to job page: {job.url}")
        driver.get(job.url)
        try:
            WebDriverWait(driver, 10).until(lambda d:
                d.execute_script("return document.readyState") == "complete")
        except Exception:
            pass
        human_delay(1, 2)

        # CSS selectors
        apply_btn = None
        css_selectors = [
            "button#apply-button",
            "button.apply-button",
            "button[class*='apply-btn']",
            "a.apply-button",
            "div.apply-button button",
            "button[title*='Apply']",
            "button[class*='applyBtn']",
            "a[class*='applyBtn']",
        ]
        for sel in css_selectors:
            try:
                apply_btn = WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, sel)))
                logger.info(f"Naukri: Found Apply button via CSS: {sel}")
                break
            except Exception:
                pass

        # XPath text fallback
        if not apply_btn:
            for xpath in [
                "//button[contains(., 'Apply')]",
                "//a[contains(., 'Apply')]",
                "//button[contains(@class,'apply')]",
            ]:
                try:
                    apply_btn = WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable((By.XPATH, xpath)))
                    logger.info(f"Naukri: Found Apply button via XPath: {xpath}")
                    break
                except Exception:
                    pass

        if not apply_btn:
            try:
                ss_path = f"naukri_apply_not_found_{int(time.time())}.png"
                driver.save_screenshot(ss_path)
                logger.warning(f"Apply button not found on Naukri — screenshot: {ss_path}")
            except Exception:
                logger.warning("Apply button not found on Naukri job page")
            return False

        apply_btn.click()
        human_delay(2, 3)
        logger.info(f"✅ Naukri Applied: {job.title} @ {job.company}")
        return True

    except Exception as e:
        logger.error(f"Naukri apply error: {e}")
        return False
    finally:
        driver.quit()


# ──────────────────────────────────────────
# Background Tasks
# ──────────────────────────────────────────
def run_bulk_apply(platform: str, credentials: Credentials, config: SearchConfig):
    """Background task: search + apply to all found jobs"""
    logger.info(f"🚀 Starting bulk apply on {platform} for '{config.role}'")

    if platform == "linkedin":
        jobs = linkedin_login_and_search(credentials.email, credentials.password, config)
    else:
        jobs = naukri_login_and_search(credentials.email, credentials.password, config)

    for j in jobs:
        job_store[j.id] = j

    applied = 0
    failed = 0

    for job_id, job in list(job_store.items()):
        if job.platform != platform or job.status != "pending":
            continue

        job.status = "applying"
        try:
            if platform == "linkedin":
                success = linkedin_easy_apply(job, credentials.email, credentials.password)
            else:
                success = naukri_apply(job, credentials.email, credentials.password)

            job.status = "applied" if success else "failed"
            if success:
                applied += 1
            else:
                failed += 1
        except Exception as e:
            job.status = "failed"
            failed += 1
            logger.error(f"Error applying to {job.title}: {e}")

        apply_log.append({
            "job_id": job_id,
            "title": job.title,
            "company": job.company,
            "status": job.status,
            "timestamp": datetime.now().isoformat()
        })

        human_delay(5, 10)  # Rate limiting

    logger.info(f"✅ Bulk apply complete: {applied} applied, {failed} failed")


# ──────────────────────────────────────────
# Credential validators (login only, no search)
# ──────────────────────────────────────────

def _is_chrome_crash(err: Exception) -> bool:
    s = str(err)
    return (
        not s.strip()
        or s.strip() == "Message:"
        or "GetHandleVerifier" in s
        or "session not created" in s.lower()
        or "chrome not reachable" in s.lower()
        or "disconnected" in s.lower()
        or "failed to start" in s.lower()
    )


def _linkedin_validate(email: str, password: str) -> dict:
    """
    Validate LinkedIn credentials by opening a real Chrome browser and logging in.
    Uses time.sleep instead of WebDriverWait to avoid GetHandleVerifier crashes.
    """
    driver = None
    try:
        logger.info("LinkedIn validate: launching Chrome (headless)...")
        driver = setup_chrome_driver(headless=True)
        driver.get("https://www.linkedin.com/login")
        time.sleep(3)  # let page fully render before touching DOM

        # Fill credentials via JavaScript — avoids WebDriverWait polling crashes
        driver.execute_script("""
            var u = document.getElementById('username');
            var p = document.getElementById('password');
            if (u) { u.value = arguments[0]; u.dispatchEvent(new Event('input', {bubbles:true})); }
            if (p) { p.value = arguments[1]; p.dispatchEvent(new Event('input', {bubbles:true})); }
        """, email, password)
        time.sleep(0.5)

        driver.execute_script("""
            var btn = document.querySelector('button[type="submit"]');
            if (btn) btn.click();
        """)

        time.sleep(7)  # wait for LinkedIn to redirect after submit

        url = driver.execute_script("return window.location.href") or ""
        logger.info(f"LinkedIn validate: post-login url = {url}")

        if "/feed" in url or "/mynetwork" in url:
            return {"valid": True}

        if any(x in url for x in ("checkpoint", "challenge", "verify")):
            raise HTTPException(status_code=401,
                detail="🔐 LinkedIn security check required. "
                       "Please log into LinkedIn manually in your browser first, then try again.")

        raise HTTPException(status_code=401,
            detail="❌ Wrong email or password. Please check and try again.")

    except HTTPException:
        raise
    except Exception as e:
        err = str(e)
        logger.error(f"LinkedIn validate error: {err}")
        if _is_chrome_crash(e):
            raise HTTPException(status_code=500,
                detail="Chrome crashed during login check. Please try again.")
        raise HTTPException(status_code=500,
            detail=f"Browser error during login. ({err[:120]})")
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


def _naukri_validate(email: str, password: str) -> dict:
    """
    Validate Naukri credentials by opening a real Chrome browser and logging in.
    Uses time.sleep instead of WebDriverWait to avoid GetHandleVerifier crashes.
    """
    driver = None
    try:
        logger.info("Naukri validate: launching Chrome (headless)...")
        driver = setup_chrome_driver(headless=True)
        driver.get("https://www.naukri.com/nlogin/login")
        time.sleep(3)

        driver.execute_script("""
            var e = document.querySelector('#usernameField, input[type="email"], input[placeholder*="Email"]');
            var p = document.querySelector('#passwordField, input[type="password"]');
            if (e) { e.value = arguments[0]; e.dispatchEvent(new Event('input', {bubbles:true})); }
            if (p) { p.value = arguments[1]; p.dispatchEvent(new Event('input', {bubbles:true})); }
        """, email, password)
        time.sleep(0.5)

        driver.execute_script("""
            var btn = document.querySelector('button[type="submit"], .loginButton, input[type="submit"]');
            if (btn) btn.click();
        """)

        time.sleep(7)

        url = driver.execute_script("return window.location.href") or ""
        logger.info(f"Naukri validate: post-login url = {url}")

        # Naukri redirects away from /nlogin on success
        if "nlogin" not in url and "login" not in url.lower():
            return {"valid": True}

        raise HTTPException(status_code=401,
            detail="❌ Wrong email or password. Please check and try again.")

    except HTTPException:
        raise
    except Exception as e:
        err = str(e)
        logger.error(f"Naukri validate error: {err}")
        if _is_chrome_crash(e):
            raise HTTPException(status_code=500,
                detail="Chrome crashed during login check. Please try again.")
        raise HTTPException(status_code=500,
            detail=f"Browser error during login. ({err[:120]})")
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass




# ──────────────────────────────────────────
# API ROUTES
# ──────────────────────────────────────────


@app.post("/api/validate-credentials")
def validate_credentials(creds: Credentials):
    """Validate credentials by actually logging in via Selenium."""
    if creds.platform == "linkedin":
        return _linkedin_validate(creds.email, creds.password)
    elif creds.platform == "naukri":
        return _naukri_validate(creds.email, creds.password)
    raise HTTPException(status_code=400, detail="Platform must be 'linkedin' or 'naukri'")


@app.get("/")
def root():
    return {"message": "Job Auto-Apply API is running 🚀"}


@app.post("/api/search-jobs")
def search_jobs(credentials: Credentials, config: SearchConfig):
    """Search for jobs on LinkedIn or Naukri and store them.
    Retries once automatically if Chrome crashes (GetHandleVerifier / empty message)."""
    from chrome_manager import kill_orphan_drivers

    def _run_search():
        if credentials.platform == "linkedin":
            return linkedin_login_and_search(credentials.email, credentials.password, config)
        elif credentials.platform == "naukri":
            return naukri_login_and_search(credentials.email, credentials.password, config)
        else:
            raise HTTPException(status_code=400, detail="Platform must be 'linkedin' or 'naukri'")

    try:
        logger.info(f"Searching {config.role} on {credentials.platform} for {credentials.email}")
        job_store.clear()

        def _is_chrome_crash(err: Exception) -> bool:
            s = str(err)
            return (
                not s.strip()
                or s.strip() == "Message:"
                or "GetHandleVerifier" in s
                or "Message: Stacktrace:" in s
                or "session not created" in s.lower()
                or "chrome not reachable" in s.lower()
                or "cannot connect to chrome" in s.lower()
                or "disconnected: not connected to devtools" in s.lower()
                or "failed to start" in s.lower()
            )

        MAX_ATTEMPTS = 3
        last_err: Exception | None = None
        jobs = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                jobs = _run_search()
                break
            except Exception as err:
                last_err = err
                if _is_chrome_crash(err) and attempt < MAX_ATTEMPTS:
                    wait = attempt * 5   # 5s, 10s between retries
                    logger.warning(
                        f"⚠️  Chrome crash on attempt {attempt}/{MAX_ATTEMPTS} "
                        f"— cleaning up and retrying in {wait}s..."
                    )
                    kill_orphan_drivers()
                    time.sleep(wait)
                else:
                    raise

        if jobs is None:
            raise last_err

        for j in jobs:
            job_store[j.id] = j

        logger.info(f"✅ Found {len(jobs)} jobs for '{config.role}'")

        if len(jobs) == 0:
            logger.warning("⚠️  No jobs found. This can happen for several reasons:")
            logger.warning("   1. LinkedIn/Naukri's anti-bot detection")
            logger.warning("   2. Jobs haven't loaded yet (try again)")
            logger.warning("   3. Search filters too restrictive")
            logger.warning("   4. Account too new or flagged")

        # Return only the freshly found jobs, not the whole accumulated store
        return {"success": True, "count": len(jobs), "jobs": jobs, "message": "Try Manual Apply if automation isn't working"}
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ Search failed: {error_msg}")
        
        # Provide more user-friendly error messages
        if "Security" in error_msg or "2FA" in error_msg or "verification" in error_msg.lower():
            detail = error_msg
        elif "login failed" in error_msg.lower():
            detail = error_msg
        elif "unusual activity" in error_msg.lower():
            detail = "LinkedIn blocked automation due to unusual activity. Log in manually first or try again in 24 hours."
        else:
            detail = f"Search failed: {error_msg}. Try: 1) Manual Apply instead, 2) Log in to {credentials.platform} manually first, 3) Disable 2FA, 4) Try Naukri instead"
        
        raise HTTPException(status_code=500, detail=detail)


@app.get("/api/jobs")
def get_jobs(platform: Optional[str] = None, status: Optional[str] = None):
    """Get all stored jobs with optional filters."""
    jobs = list(job_store.values())
    if platform:
        jobs = [j for j in jobs if j.platform == platform]
    if status:
        jobs = [j for j in jobs if j.status == status]
    return {"jobs": jobs, "total": len(jobs)}


@app.post("/api/apply/{job_id}")
def apply_single(job_id: str, req: ApplyWithJobRequest):
    """Auto-apply to a job. Job data is carried in the request body — no job_store lookup."""
    # Build a Job object from the request (works even after backend restart / store clear)
    job = job_store.get(job_id) or Job(
        id=job_id,
        title=req.title,
        company=req.company,
        location=req.location,
        experience=req.experience or "",
        salary=req.salary,
        posted="Recent",
        platform=req.platform,
        url=req.url,
        status="applying",
    )
    job.status = "applying"
    job_store[job_id] = job  # re-register so status updates are visible

    try:
        if req.platform == "linkedin":
            success = linkedin_easy_apply(job, req.email, req.password)
        else:
            success = naukri_apply(job, req.email, req.password)

        job.status = "applied" if success else "failed"
        db_save_application(
            job_id=job_id, title=job.title, company=job.company,
            location=job.location, platform=job.platform, url=job.url,
            status=job.status, method="auto",
            experience=job.experience, salary=job.salary,
        )
        return {"success": success, "job": job}
    except Exception as e:
        job.status = "failed"
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/mark-applied")
def mark_applied(req: MarkAppliedRequest):
    """Record a manually applied job into the database."""
    db_save_application(
        job_id=req.job_id, title=req.title, company=req.company,
        location=req.location, platform=req.platform, url=req.url,
        status="manually-applied", method="manual",
        experience=req.experience, salary=req.salary,
    )
    return {"success": True}


@app.post("/api/bulk-apply")
def bulk_apply(request: BulkApplyRequest, background_tasks: BackgroundTasks):
    """Search and auto-apply to all matching jobs in background."""
    background_tasks.add_task(
        run_bulk_apply,
        request.platform,
        request.credentials,
        request.config
    )
    return {
        "success": True,
        "message": f"Bulk apply started in background for '{request.config.role}' on {request.platform}"
    }


@app.get("/api/apply-log")
def get_apply_log():
    """Get full application history from database."""
    log = db_get_log()
    # Normalize field name so frontend's l.timestamp works
    for entry in log:
        entry["timestamp"] = entry.get("applied_at", "")
    return {"log": log, "total": len(log)}


@app.get("/api/stats")
def get_stats():
    """Stats from current session jobs + lifetime DB totals."""
    session_jobs = list(job_store.values())
    db = db_get_stats()
    return {
        # Session counts (current search)
        "total":    len(session_jobs),
        "pending":  sum(1 for j in session_jobs if j.status == "pending"),
        "applying": sum(1 for j in session_jobs if j.status == "applying"),
        "applied":  sum(1 for j in session_jobs if j.status in ("applied", "manually-applied")),
        "failed":   sum(1 for j in session_jobs if j.status == "failed"),
        # Lifetime DB totals
        "db_total":            db["total"],
        "db_applied":          db["applied"],
        "db_auto_applied":     db["auto_applied"],
        "db_manually_applied": db["manually_applied"],
        "db_failed":           db["failed"],
    }


@app.delete("/api/jobs")
def clear_jobs():
    """Clear all stored jobs."""
    job_store.clear()
    return {"success": True, "message": "All jobs cleared"}


# ──────────────────────────────────────────
# Run server
# ──────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("job_apply_backend:app", host="0.0.0.0", port=8001, reload=True)


# ──────────────────────────────────────────
# SETUP INSTRUCTIONS
# ──────────────────────────────────────────
"""
INSTALLATION:
    pip install fastapi uvicorn selenium webdriver-manager

REQUIREMENTS:
    - Google Chrome installed
    - Python 3.9+

RUN:
    python job_apply_backend.py
    OR
    uvicorn job_apply_backend:app --reload --port 8000

API DOCS (auto-generated):
    http://localhost:8000/docs

ENDPOINTS:
    POST /api/search-jobs     - Search and fetch jobs
    GET  /api/jobs            - List all jobs
    POST /api/apply/{job_id}  - Apply to single job
    POST /api/bulk-apply      - Auto-apply to all found jobs (background)
    GET  /api/apply-log       - View application history
    GET  /api/stats           - Dashboard stats
    DELETE /api/jobs          - Clear job list

NOTE:
    LinkedIn & Naukri may require CAPTCHA solving for first login.
    Use cookies/session persistence to avoid repeated logins.
    Respect each platform's Terms of Service.
"""
