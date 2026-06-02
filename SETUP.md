# Frontend-Backend Connection Setup

## Overview
- **Frontend**: React app running on `http://localhost:3000`
- **Backend**: FastAPI server running on `http://localhost:8000`
- **Connection**: Frontend communicates to backend via API calls to `http://localhost:8000`

---

## Prerequisites

### Backend Requirements
- Python 3.9+
- Google Chrome installed (required for Selenium automation)
- Required packages: `fastapi`, `uvicorn`, `selenium`, `webdriver-manager`, `requests`, `beautifulsoup4`, `pydantic`

### Frontend Requirements
- Node.js 14+
- npm or yarn

---

## Backend Setup

### 1. Install Dependencies
```bash
cd c:\my_project\backend
pip install -r requirements.txt
```

If `requirements.txt` doesn't exist, install manually:
```bash
pip install fastapi uvicorn selenium webdriver-manager requests beautifulsoup4 pydantic
```

### 2. Start the Backend Server
```bash
cd c:\my_project\backend
python job_apply_backend.py
```

Or using uvicorn directly:
```bash
uvicorn job_apply_backend:app --reload --host 0.0.0.0 --port 8000
```

**Expected Output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Application startup complete
```

**Backend API Documentation:**
- Once running, visit: http://localhost:8000/docs (interactive API docs)
- Or: http://localhost:8000/redoc (ReDoc documentation)

---

## Frontend Setup

### 1. Install Dependencies
```bash
cd c:\my_project\frontend
npm install
```

### 2. Environment Configuration
The following files have been created for you:

- `.env` - Development environment
- `.env.production` - Production environment
- Both contain: `REACT_APP_API_URL=http://localhost:8000`

### 3. Start the Frontend Dev Server
```bash
cd c:\my_project\frontend
npm start
```

**Expected Output:**
```
On Your Network: http://localhost:3000
Local:           http://localhost:3000
```

The app will open automatically in your default browser.

---

## Connection Testing

### 1. Verify Backend is Running
```bash
curl http://localhost:8000/
```

Expected response:
```json
{"message": "Job Auto-Apply API is running 🚀"}
```

### 2. Open Frontend in Browser
Navigate to: **http://localhost:3000**

### 3. Login
- Choose platform: **LinkedIn** or **Naukri**
- Enter credentials (works with demo data if backend is unavailable)
- Click **Search Jobs** to test the connection

---

## Available API Endpoints

The frontend communicates with these backend endpoints:

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/search-jobs` | Search and fetch jobs from LinkedIn/Naukri |
| `GET` | `/api/jobs` | List all stored jobs |
| `POST` | `/api/apply/{job_id}` | Apply to a single job |
| `POST` | `/api/bulk-apply` | Start bulk auto-apply in background |
| `GET` | `/api/apply-log` | Get application history |
| `GET` | `/api/stats` | Get dashboard statistics |
| `DELETE` | `/api/jobs` | Clear all stored jobs |

---

## Troubleshooting

### "Backend not running" Message
- **Issue**: Frontend shows "Backend offline" message
- **Solution**: 
  1. Verify backend is running: `python job_apply_backend.py`
  2. Check port 8000 is available: `netstat -ano | findstr :8000`
  3. Frontend falls back to demo data automatically

### CORS Errors
- The backend has CORS enabled for all origins (`allow_origins=["*"]`)
- This is configured in `job_apply_backend.py`

### Port Already in Use
- **Backend port 8000 in use**:
  ```bash
  # Find process using port 8000
  netstat -ano | findstr :8000
  # Kill it (replace PID)
  taskkill /PID <PID> /F
  ```
- **Frontend port 3000 in use**:
  ```bash
  PORT=3001 npm start
  ```

### Chrome/Selenium Issues
- Ensure Google Chrome is installed
- Selenium will automatically download ChromeDriver
- If headless mode fails, check Chrome installation

---

## Running Both Together (Recommended)

### Terminal 1: Backend
```bash
cd c:\my_project\backend
python job_apply_backend.py
```

### Terminal 2: Frontend
```bash
cd c:\my_project\frontend
npm start
```

Both services will run simultaneously and communicate over `localhost:8000`.

---

## Production Deployment

### Building Frontend for Production
```bash
cd c:\my_project\frontend
npm run build
```

This creates an optimized build in `frontend/build/` ready for deployment.

### Production API Configuration
Update `REACT_APP_API_URL` in `.env.production` to point to your production backend URL:
```env
REACT_APP_API_URL=https://api.example.com
```

---

## File Structure

```
my_project/
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── components/
│   │   │   └── JobApplyDashboard.jsx
│   │   ├── App.js
│   │   └── index.js
│   ├── .env                  (← Backend URL)
│   ├── .env.production       (← Production backend URL)
│   └── package.json          (← Proxy configured)
│
└── backend/
    ├── job_apply_backend.py  (← FastAPI app, port 8000)
    └── venv/                 (← Virtual environment)
```

---

## Support

For issues or questions:
1. Check backend logs at `http://localhost:8000/docs`
2. Check browser console for frontend errors (F12)
3. Verify both services are running with correct ports
4. See troubleshooting section above

