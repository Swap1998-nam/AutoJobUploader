#!/usr/bin/env python
"""
Quick Health Check - Fast verification that everything is working
Run this if you're having issues
"""

import sys
import subprocess
from pathlib import Path

def check_python():
    """Check Python version"""
    print("✓ Checking Python version...", end=" ")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 8:
        print(f"✅ {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"❌ {version.major}.{version.minor} (need 3.8+)")
        return False

def check_imports():
    """Check all required modules are installed"""
    print("✓ Checking required modules...", end=" ")
    required = ['selenium', 'fastapi', 'uvicorn', 'bs4']  # bs4 is the import name for beautifulsoup4
    missing = []
    
    for module in required:
        try:
            __import__(module)
        except ImportError:
            missing.append(module)
    
    if not missing:
        print("✅")
        return True
    else:
        print(f"❌ Missing: {', '.join(missing)}")
        print(f"   Run: pip install {' '.join(missing)}")
        return False

def check_chrome():
    """Check Chrome is installed"""
    print("✓ Checking Chrome installation...", end=" ")
    try:
        from chrome_manager import verify_chrome_installation
        if verify_chrome_installation():
            print("✅")
            return True
        else:
            print("❌")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def check_chromedriver():
    """Check ChromeDriver compatibility"""
    print("✓ Testing ChromeDriver...", end=" ")
    try:
        from chrome_manager import setup_chrome_driver
        driver = setup_chrome_driver()
        driver.quit()
        print("✅")
        return True
    except Exception as e:
        error_msg = str(e)[:50]
        print(f"❌ {error_msg}...")
        return False

def main():
    print("\n" + "="*50)
    print("🔍 HEALTH CHECK - Job Apply Automation")
    print("="*50 + "\n")
    
    checks = [
        ("Python", check_python),
        ("Modules", check_imports),
        ("Chrome", check_chrome),
        ("ChromeDriver", check_chromedriver),
    ]
    
    passed = 0
    failed = 0
    
    for name, check_func in checks:
        try:
            if check_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ {name}: {e}")
            failed += 1
    
    print("\n" + "="*50)
    print(f"Results: ✅ {passed}/{len(checks)} passed")
    print("="*50 + "\n")
    
    if failed == 0:
        print("✅ All checks passed! You're ready to go.")
        print("\nStart the backend with:")
        print("  uvicorn job_apply_backend:app --reload --port 8000\n")
        return 0
    else:
        print(f"❌ {failed} check(s) failed. Run verify_startup.py for details.\n")
        return 1

if __name__ == "__main__":
    sys.exit(main())
