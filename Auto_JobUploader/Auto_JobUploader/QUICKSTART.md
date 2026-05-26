# Quick Start Guide

## TL;DR - Start Both Services in 2 Steps

### Step 1: Start Backend (Terminal 1)
```bash
cd c:\my_project\backend
python job_apply_backend.py
```

Wait for message: `Application startup complete`

### Step 2: Start Frontend (Terminal 2)
```bash
cd c:\my_project\frontend
npm install
npm start
```

Frontend opens at: http://localhost:3000

---

## Testing the Connection

1. Open http://localhost:3000 in browser
2. Select **LinkedIn** or **Naukri** platform
3. Enter test credentials
4. Click **Search Jobs**
5. If successful, jobs appear in dashboard
6. If backend is down, demo data shows automatically

---

## API Health Check

Backend is running if this returns `{"message": "Job Auto-Apply API is running 🚀"}`:
```bash
curl http://localhost:8000/
```

Interactive API docs: http://localhost:8000/docs

---

## Common Issues

| Issue | Solution |
|-------|----------|
| "Backend not found" | Start backend first with `python job_apply_backend.py` |
| Port 8000 in use | Kill process: `taskkill /PID <pid> /F` |
| Module not found | Run `pip install fastapi uvicorn selenium webdriver-manager` |
| Chrome not found | Install Google Chrome (required for Selenium) |

---

See [SETUP.md](SETUP.md) for detailed configuration and troubleshooting.
