#!/usr/bin/env python
"""
Debug LinkedIn Job Search - Visual inspection tool
Run this to see EXACTLY what LinkedIn shows and debug scraping
"""

import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from chrome_manager import setup_chrome_driver

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def debug_linkedin_search():
    """Debug LinkedIn job search and save screenshots"""
    
    email = input("Enter LinkedIn email: ").strip()
    password = input("Enter LinkedIn password: ").strip()
    role = input("Enter job role (default: Python Developer): ").strip() or "Python Developer"
    location = input("Enter location (default: India): ").strip() or "India"
    
    try:
        driver = setup_chrome_driver()
    except Exception as e:
        logger.error(f"Failed to start browser: {e}")
        return
    
    try:
        # Login
        logger.info("🔍 Opening LinkedIn login page...")
        driver.get("https://www.linkedin.com/login")
        time.sleep(2)
        
        logger.info("🔍 Entering credentials...")
        driver.find_element(By.ID, "username").send_keys(email)
        time.sleep(0.5)
        driver.find_element(By.ID, "password").send_keys(password)
        time.sleep(0.5)
        driver.find_element(By.XPATH, "//button[@type='submit']").click()
        time.sleep(5)
        
        logger.info(f"✅ Logged in. Current URL: {driver.current_url}")
        
        # Go to job search
        search_url = (
            f"https://www.linkedin.com/jobs/search/"
            f"?keywords={role.replace(' ', '%20')}"
            f"&location={location.replace(' ', '%20')}"
            f"&f_E=1%2C2%2C3"
            f"&f_AL=true"
            f"&sortBy=DD"
        )
        
        logger.info(f"🔍 Opening job search: {search_url}")
        driver.get(search_url)
        
        # Give it time to load
        logger.info("⏳ Waiting for jobs to load (10 seconds)...")
        time.sleep(10)
        
        # Scroll
        logger.info("🔍 Scrolling to trigger dynamic loading...")
        for i in range(5):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.5)
            logger.info(f"   Scroll {i+1}/5")
        
        time.sleep(3)
        
        # Save screenshot
        screenshot_path = "linkedin_search.png"
        logger.info(f"📸 Saving screenshot to {screenshot_path}...")
        driver.save_screenshot(screenshot_path)
        logger.info(f"✅ Screenshot saved: {screenshot_path}")
        
        # Try to find jobs with multiple selectors
        selectors = [
            ("li[data-occludable-job-id]", "Occludable job ID (most stable)"),
            ("li[data-job-id]", "Job ID data selector"),
            ("div.job-card-container--clickable", "Card container clickable"),
            ("div.job-card-container", "Card container"),
            ("li.jobs-search-results__list-item", "Original selector"),
            ("li.scaffold-layout__list-item", "Scaffold list item"),
            ("li.base-card", "Base card selector"),
            ("article.jobs-search-results__list-item", "Article selector"),
            ("div.base-card", "Div card selector"),
            ("div[data-job-id]", "Job ID div selector"),
        ]
        
        logger.info("\n🔍 Checking all selectors:\n")
        for selector, desc in selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                logger.info(f"  {desc:30} ({selector:40}): {len(elements):3} found")
            except Exception as e:
                logger.info(f"  {desc:30} ({selector:40}): ERROR - {e}")
        
        # Show page info
        logger.info(f"\n📊 PAGE INFO:")
        logger.info(f"  Title: {driver.title}")
        logger.info(f"  URL: {driver.current_url}")
        logger.info(f"  Page size: {len(driver.page_source)} characters")
        
        # Show first few job titles
        logger.info(f"\n🎯 ATTEMPTING TO EXTRACT JOB INFO:\n")
        
        for selector, desc in selectors[:2]:
            cards = driver.find_elements(By.CSS_SELECTOR, selector)
            if cards:
                logger.info(f"Using: {desc}\n")
                for i, card in enumerate(cards[:3]):
                    try:
                        # Get all text content
                        text = card.text
                        logger.info(f"  Job {i+1}: {text[:100]}...")
                    except Exception as e:
                        logger.info(f"  Job {i+1}: ERROR - {e}")
                break
        
        # Save page source
        source_path = "linkedin_search.html"
        logger.info(f"\n💾 Saving page source to {source_path}...")
        with open(source_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        logger.info(f"✅ Page source saved: {source_path}")
        
        logger.info("\n✅ Debug complete!")
        logger.info("   📸 Check 'linkedin_search.png' to see what LinkedIn shows")
        logger.info("   💾 Check 'linkedin_search.html' to see the page source")
        logger.info("   📋 Above selectors show which ones found job cards")
        
        input("\nPress Enter to close browser...")
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        driver.quit()


if __name__ == "__main__":
    debug_linkedin_search()
