"""
ChromeDriver Manager - Handles Chrome setup with Windows compatibility.
Kills orphan chromedriver.exe processes before every launch to prevent
the GetHandleVerifier crash that happens after idle periods.
"""

import logging
import subprocess
import os
import platform
import tempfile

logger = logging.getLogger(__name__)



def get_chrome_version():
    """Get installed Chrome version on Windows"""
    try:
        import winreg
        for root, path in [
            (winreg.HKEY_CURRENT_USER,  r"Software\Google\Chrome\BLBeacon"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Google\Chrome\BLBeacon"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Google\Chrome\BLBeacon"),
        ]:
            try:
                hkey = winreg.OpenKey(root, path)
                version, _ = winreg.QueryValueEx(hkey, "version")
                winreg.CloseKey(hkey)
                logger.info(f"✅ Chrome version detected: {version}")
                return version
            except (FileNotFoundError, OSError):
                continue
    except Exception as e:
        logger.warning(f"⚠️  Could not detect Chrome version: {e}")
    return None


def kill_orphan_drivers():
    """
    Kill leftover chromedriver.exe AND automation chrome.exe processes.

    Orphan chromedriver/chrome processes are the #1 cause of GetHandleVerifier
    crashes on Windows. They appear when driver.quit() doesn't fully clean up
    (e.g. after a crash or abrupt network timeout).

    We kill:
    1. ALL chromedriver.exe processes (they are only ever spawned by automation)
    2. chrome.exe processes whose command line contains 'chrome_autoapply_' —
       the unique prefix we use for temp user-data-dirs, so we never touch
       the user's own browser windows.
    """
    if platform.system() != "Windows":
        return

    # Kill all chromedriver.exe (safe — only automation spawns these)
    try:
        result = subprocess.run(
            ["taskkill", "/F", "/IM", "chromedriver.exe", "/T"],
            capture_output=True, text=True, timeout=5
        )
        if "SUCCESS" in result.stdout:
            logger.info("🧹 Killed orphan chromedriver.exe processes")
    except Exception:
        pass

    # Kill chrome.exe instances launched by our automation (identified by temp profile prefix)
    try:
        ps_cmd = (
            "Get-WmiObject Win32_Process -Filter \"Name='chrome.exe'\" | "
            "Where-Object { $_.CommandLine -like '*chrome_autoapply_*' } | "
            "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
            capture_output=True, text=True, timeout=10
        )
        logger.info("🧹 Cleaned up orphan automation chrome.exe processes")
    except Exception:
        pass  # non-fatal — best-effort cleanup


def setup_chrome_driver(headless: bool = True):
    """
    Launch a fresh Chrome session with Windows-safe options.

    Uses Selenium Manager (built into Selenium 4.6+) to auto-download the
    ChromeDriver that exactly matches the installed Chrome version. This avoids
    the GetHandleVerifier crash caused by a build-number mismatch between
    Chrome and ChromeDriver (e.g. Chrome 147.x.x.138 vs ChromeDriver 147.x.x.117).

    headless=False runs a visible Chrome window — more reliable on Windows
    when headless mode crashes (GetHandleVerifier).
    """
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    logger.info(f"🔧 Setting up ChromeDriver (headless={headless})...")

    # ── Step 1: clean up orphan processes ──────────────────────────────────
    kill_orphan_drivers()

    try:
        chrome_version = get_chrome_version()
        if chrome_version:
            logger.info(f"Chrome version: {chrome_version}")

        options = Options()

        # Unique throw-away profile — prevents sessions from colliding
        tmp_profile = tempfile.mkdtemp(prefix="chrome_autoapply_")
        options.add_argument(f"--user-data-dir={tmp_profile}")

        if headless:
            options.add_argument("--headless=new")

        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")

        if platform.system() == "Windows":
            logger.info("🪟 Applying Windows compatibility fixes...")

            # ── Pin Chrome binary so ChromeDriver attaches the right build ──
            for _cp in [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
                os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"),
            ]:
                if os.path.exists(_cp):
                    options.binary_location = _cp
                    logger.info(f"📍 Chrome binary pinned: {_cp}")
                    break

            # ── GPU: fully disabled — no GPU subprocess to crash ───────────
            # NOTE: --in-process-gpu contradicts --disable-gpu; never combine them.
            # NOTE: VizDisplayCompositor was REMOVED in Chrome 136+; disabling it
            #       in Chrome 147 causes a startup crash — do NOT add it here.
            options.add_argument("--disable-gpu")
            options.add_argument("--disable-gpu-sandbox")
            options.add_argument("--disable-software-rasterizer")

            # ── Background & network processes ─────────────────────────────
            options.add_argument("--disable-background-networking")
            options.add_argument("--disable-background-timer-throttling")
            options.add_argument("--disable-renderer-backgrounding")
            options.add_argument("--disable-ipc-flooding-protection")

            # ── Feature / extension housekeeping ───────────────────────────
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-default-apps")
            options.add_argument("--disable-sync")
            options.add_argument("--disable-component-update")
            options.add_argument("--no-first-run")
            options.add_argument("--no-default-browser-check")
            options.add_argument("--mute-audio")
            options.add_argument("--log-level=3")

        # Match the actual installed Chrome version in the user-agent
        ua_version = (chrome_version or "147").split(".")[0]
        options.add_argument(
            f"--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            f"AppleWebKit/537.36 (KHTML, like Gecko) "
            f"Chrome/{ua_version}.0.0.0 Safari/537.36"
        )

        # Selenium Manager (Selenium 4.6+) auto-downloads the ChromeDriver that
        # exactly matches the pinned Chrome binary — no manual version tracking needed.
        logger.info("🚀 Launching Chrome via Selenium Manager...")
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(60)

        logger.info("✅ ChromeDriver initialized successfully")
        return driver

    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ ChromeDriver setup failed: {error_msg}")
        if "chrome" in error_msg.lower():
            logger.error("   → Ensure Chrome is installed at the standard path")
        elif "timeout" in error_msg.lower():
            logger.error("   → Timeout. Try again in a moment.")
        raise Exception(f"Failed to initialize ChromeDriver: {error_msg}")


def verify_chrome_installation():
    """Verify Chrome is installed and accessible"""
    import shutil

    logger.info("🔍 Verifying Chrome installation...")

    if shutil.which("chrome") or shutil.which("google-chrome"):
        logger.info("✅ Chrome found in PATH")
        return True

    common_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe"),
    ]
    for path in common_paths:
        if os.path.exists(path):
            logger.info(f"✅ Chrome found at: {path}")
            return True

    if get_chrome_version():
        logger.info("✅ Chrome found via registry")
        return True

    logger.error("❌ Chrome not found! Install from https://www.google.com/chrome/")
    return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("\n🔍 Chrome Verification Tool\n")
    if verify_chrome_installation():
        print("\n✅ Chrome is installed")
        get_chrome_version()
        try:
            print("\n🚀 Testing ChromeDriver setup...")
            driver = setup_chrome_driver()
            driver.get("https://www.google.com")
            print("✅ ChromeDriver working correctly!")
            driver.quit()
        except Exception as e:
            print(f"❌ Error: {e}")
    else:
        print("\n⚠️  Please install Chrome first")
