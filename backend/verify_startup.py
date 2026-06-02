#!/usr/bin/env python
"""
Startup Verification - Run this BEFORE starting the backend
Checks Chrome installation and ChromeDriver compatibility
"""

import logging
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)


def main():
    print("\n" + "="*60)
    print("🔍 JOB APPLY BACKEND - STARTUP VERIFICATION")
    print("="*60 + "\n")
    
    # Step 1: Check Chrome
    print("Step 1️⃣  Checking Chrome installation...")
    from chrome_manager import verify_chrome_installation, get_chrome_version
    
    if not verify_chrome_installation():
        print("\n❌ FATAL ERROR: Chrome is not installed!")
        print("   → Install Chrome from: https://www.google.com/chrome/")
        print("   → Or get Chromium from: https://www.chromium.org/")
        sys.exit(1)
    
    print("   ✅ Chrome is installed")
    
    # Step 2: Check Chrome version
    print("\nStep 2️⃣  Detecting Chrome version...")
    chrome_ver = get_chrome_version()
    if chrome_ver:
        print(f"   ✅ Chrome version: {chrome_ver}")
    else:
        print("   ⚠️  Could not detect Chrome version (may still work)")
    
    # Step 3: Test ChromeDriver
    print("\nStep 3️⃣  Testing ChromeDriver setup...")
    try:
        from chrome_manager import setup_chrome_driver
        driver = setup_chrome_driver()
        print("   ✅ ChromeDriver initialized successfully")
        
        # Quick connectivity test
        print("\nStep 4️⃣  Testing browser connectivity...")
        driver.get("https://www.google.com")
        print("   ✅ Browser can reach the internet")
        
        driver.quit()
        print("   ✅ Driver closed successfully")
        
    except Exception as e:
        print(f"\n   ❌ ERROR: {e}")
        print("\n   Troubleshooting:")
        print("   1. Reinstall webdriver-manager:")
        print("      → pip install --upgrade webdriver-manager")
        print("   2. Reinstall Chrome or Chromium")
        print("   3. Check if Chrome/Chromium is in your PATH")
        sys.exit(1)
    
    # Success
    print("\n" + "="*60)
    print("✅ ALL CHECKS PASSED!")
    print("="*60)
    print("\nYou can now start the backend:")
    print("  → uvicorn job_apply_backend:app --reload --port 8000")
    print("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
