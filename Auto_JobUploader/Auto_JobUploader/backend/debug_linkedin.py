"""
Debug Helper - Run this to test LinkedIn login with visible browser
Usage: python debug_linkedin.py
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
import time

def debug_linkedin_login():
    """Test LinkedIn login with visible browser window"""
    
    email = input("Enter LinkedIn email: ").strip()
    password = input("Enter LinkedIn password: ").strip()
    
    options = Options()
    # DO NOT use headless - we want to see what's happening
    # options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/120.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )
    
    try:
        print("\n🔍 DEBUG: Opening LinkedIn login page...")
        driver.get("https://www.linkedin.com/login")
        time.sleep(2)
        
        print(f"📍 Current URL: {driver.current_url}")
        print(f"📄 Page title: {driver.title}")
        
        print("\n🔍 DEBUG: Waiting for username field...")
        wait = WebDriverWait(driver, 15)
        wait.until(EC.presence_of_element_located((By.ID, "username")))
        
        print("✅ Found username field. Entering credentials...")
        driver.find_element(By.ID, "username").send_keys(email)
        time.sleep(0.5)
        driver.find_element(By.ID, "password").send_keys(password)
        time.sleep(0.5)
        
        print("✅ Clicking submit button...")
        driver.find_element(By.XPATH, "//button[@type='submit']").click()
        
        print("⏳ Waiting for login to process (5 seconds)...")
        time.sleep(5)
        
        current_url = driver.current_url
        print(f"\n📍 URL after login: {current_url}")
        print(f"📄 Page title: {driver.title}")
        
        # Check URL patterns
        if "feed" in current_url:
            print("✅ SUCCESS: You're on the LinkedIn feed!")
        elif "checkpoint" in current_url:
            print("⚠️  SECURITY CHECK: LinkedIn is asking for verification (2FA/Email)")
            print("   👉 Complete the verification manually in the browser window")
        elif "verify" in current_url.lower():
            print("⚠️  VERIFICATION NEEDED: Email or phone verification required")
        elif "error" in current_url.lower():
            print("❌ ERROR: Login failed (wrong credentials?)")
        else:
            print(f"❓ UNKNOWN STATE: Check the browser window to see what happened")
        
        print("\n🔍 Checking page source for errors...")
        if "error-message" in driver.page_source.lower():
            print("   ❌ Error message detected on page")
        if "challenge" in driver.page_source.lower():
            print("   ⚠️  Challenge/verification detected on page")
        
        print("\n⏸️  DEBUG MODE: Browser will stay open for 30 seconds")
        print("    Check the browser window to see what happened")
        time.sleep(30)
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("⏸️  Browser will stay open for 30 seconds")
        time.sleep(30)
    finally:
        driver.quit()
        print("\n✅ Browser closed. Check the logs above for details.")

if __name__ == "__main__":
    debug_linkedin_login()
