# Job Apply Automation - Troubleshooting Guide

## ❌ Common Issues & Solutions

### 0. **ChromeDriver Crash / Stacktrace Error**

**Error:** Long error with "chromedriver!", "GetHandleVerifier", "KERNEL32", "ntdll"

**Cause:** ChromeDriver version doesn't match your Chrome browser version, or Chrome is not properly installed on Windows.

**Solutions:**
```bash
# Fix 1: Verify Chrome and ChromeDriver
cd C:\my_project\backend
venv\Scripts\python verify_startup.py
# This will check everything and tell you what's wrong

# Fix 2: Reinstall webdriver-manager
venv\Scripts\pip install --upgrade webdriver-manager

# Fix 3: Clear ChromeDriver cache
cd venv\lib\site-packages\webdriver_manager\
# Delete the .wdm folder if it exists
# This forces webdriver-manager to download the correct version
```

### 1. **LinkedIn Login Failed - "Check credentials"**

**Cause:** LinkedIn has strong anti-bot detection. Your account might be flagged or require verification.

**Solutions:**
- ✅ **Manually log in to LinkedIn first** - Visit LinkedIn.com and log in manually to ensure your account is active and has no security warnings
- ✅ **Check 2FA (Two-Factor Authentication)** - If your account has 2FA enabled, disable it temporarily for automation
- ✅ **Verify your email** - LinkedIn may require email verification. Check your email and verify if needed
- ✅ **Use a fresh/verified account** - Old or new accounts are more likely to trigger anti-bot checks
- ✅ **Wait 24 hours** - LinkedIn may temporarily block login attempts. Try again later

### 2. **"Security Verification Required" / 2FA Error**

**Cause:** LinkedIn is requiring you to verify your identity via email or phone.

**Solution:**
```bash
1. Log out of all LinkedIn sessions
2. Open LinkedIn.com and log in manually
3. Complete any security verification (email/SMS)
4. Then try automation again
```

### 3. **Selenium/ChromeDriver Issues**

**If you see "No module named 'selenium'":**
```bash
cd C:\my_project\backend
venv\Scripts\pip install -r requirements.txt
```

**If ChromeDriver fails to download:**
```bash
venv\Scripts\pip install --upgrade webdriver-manager
```

### 4. **Backend Not Responding / Connection Error**

**Check if backend is running:**
```bash
# Terminal 1: Start the backend
cd C:\my_project\backend
venv\Scripts\uvicorn job_apply_backend:app --reload --port 8000

# Terminal 2: Check if it's running
curl http://localhost:8000/
```

### 5. **Naukri Login Issues**

Similar to LinkedIn, Naukri also has anti-bot detection:
- Manually log in to Naukri.com first
- Disable 2FA if enabled
- Wait a few hours if blocked

---

## 🔧 Debugging Tips

### Enable Browser Visibility (removes headless mode)
Edit `job_apply_backend.py` and find:
```python
options.add_argument("--headless=new")
```
**Comment it out** to see the browser window during automation:
```python
# options.add_argument("--headless=new")
```

### View Backend Logs
The terminal running the backend shows detailed logs. Look for:
- `INFO: LinkedIn: Opening login page...` - Login process started
- `LinkedIn: Current URL after login:` - Shows where you were redirected
- Any error messages with specific details

### Check API Response
Open your browser and go to:
```
http://localhost:8000/api/jobs
```
This shows all jobs in memory and their status.

---

## 📋 Credential Requirements

LinkedIn:
- ✅ Valid email (full email address)
- ✅ Correct password  
- ✅ Account should be manually verified at least once
- ✅ 2FA disabled (temporary)

Naukri:
- ✅ Valid email or username
- ✅ Correct password
- ✅ Account active
- ✅ 2FA disabled

---

## ✅ Verification Checklist

Before trying automation again:
- [ ] I logged into LinkedIn/Naukri manually and it worked
- [ ] I completed any security verification steps
- [ ] I disabled 2FA on the account
- [ ] Backend is running (shows `Uvicorn running on http://127.0.0.1:8000`)
- [ ] Frontend can connect to backend (no "Backend Offline" error)
- [ ] I'm using the exact same credentials I verified manually

---

## 🆘 Still Not Working?

1. **Check backend logs** - Run backend and note exact error message
2. **Try Manual Apply** - Use the "Manual Apply" mode in the UI while backend is working on search
3. **Use Naukri instead** - LinkedIn's anti-bot is very aggressive. Naukri may be easier
4. **Wait 48 hours** - If LinkedIn is blocking, wait and try with a different account

---

## 📚 Additional Resources

- Backend API docs: `http://localhost:8000/docs` (if you add `from fastapi.openapi.utils import get_openapi`)
- LinkedIn Job Search URL structure: Check `linkedin_login_and_search()` function
- Naukri Job Search URL structure: Check `naukri_login_and_search()` function
