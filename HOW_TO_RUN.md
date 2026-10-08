# 🚀 How to Run IntelliWMS & ML Forecasting Model

> **Use PowerShell** for everything. Not CMD.  
> Open it from VS Code: `Ctrl + Shift + `` ` (backtick)

---

## ⚠️ One-Time Setup (Do This First, Ever)

Open **PowerShell** in the project root directory and run this **once** on your machine to allow scripts to run:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force
```

You only ever need to do this once. After this, everything works normally.

---

## 🤖 How to Run the ML Model Separately (DemandIQ Standalone)

The ML Model service (**DemandIQ Amazon Product Demand Forecasting**) is an independent, self-contained service featuring a pre-trained XGBoost regression model (31 features) and its own built-in web UI dashboard.

### Option 1: Run ML Model Alongside IntelliWMS (Port 8001 — Recommended)
When running together with the main IntelliWMS backend (which occupies port 8000), run the ML model on **port 8001**:

```powershell
# 1. Navigate to the ML-MODEL folder from the repository root
cd ML-MODEL

# 2. Start the Uvicorn server on port 8001
..\venv\Scripts\python.exe -m uvicorn app:app --reload --port 8001
```

✅ It's working when you see:
```
INFO:     Uvicorn running on http://127.0.0.1:8001 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

- 🌐 **Interactive Dashboard UI**: [http://localhost:8001](http://localhost:8001)
- 📄 **Swagger API Docs**: [http://localhost:8001/docs](http://localhost:8001/docs)
- 🩺 **Health Check**: [http://localhost:8001/api/health](http://localhost:8001/api/health)

#### Run Automated Sanity Test for ML Model:
In another PowerShell tab (inside `ML-MODEL`):
```powershell
..\venv\Scripts\python.exe test_api.py
```

---

### Option 2: Run ML Model Purely Standalone (Port 8000)
If you are **not** running the main IntelliWMS backend API simultaneously, you can run the ML service on default **port 8000**:

```powershell
cd ML-MODEL
..\venv\Scripts\python.exe -m uvicorn app:app --reload --port 8000
```

- 🌐 **Interactive Dashboard UI**: [http://localhost:8000](http://localhost:8000)
- 📄 **Swagger API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- 🧪 **Sanity Test**:
```powershell
..\venv\Scripts\python.exe test_api.py http://127.0.0.1:8000
```

---

## 🖥️ Full Stack IntelliWMS: Step-by-Step Terminals

Open terminals in VS Code (`Ctrl + Shift + `` `) using the **`+`** button to open multiple tabs.

### Terminal 1 — Backend API (Port 8000)

```powershell
# In project root:
.\venv\Scripts\python.exe -m uvicorn backend.main:app --reload --port 8000
```

✅ It's working when you see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

📄 Swagger API docs → [http://localhost:8000/docs](http://localhost:8000/docs)

---

### Terminal 2 — Knowledge Agent (Port 8002)

```powershell
# In project root:
.\venv\Scripts\python.exe -m uvicorn agents.knowledge_agent.server:app --reload --port 8002
```

✅ It's working when you see:
```
INFO:     Uvicorn running on http://127.0.0.1:8002
INFO:     Application startup complete.
```

📄 Knowledge Agent docs → [http://localhost:8002/docs](http://localhost:8002/docs)

---

### Terminal 3 — Frontend (Port 5173)

```powershell
cd frontend
npm run dev
```

✅ It's working when you see:
```
  VITE v6.x.x  ready in 600ms
  ➜  Local:   http://localhost:5173/
```

🌐 Open your browser → **[http://localhost:5173](http://localhost:5173)**

---

### Terminal 4 (Optional) — ML Model / DemandIQ (Port 8001)

```powershell
cd ML-MODEL
..\venv\Scripts\python.exe -m uvicorn app:app --reload --port 8001
```

🌐 Open your browser → **[http://localhost:8001](http://localhost:8001)**

---

## 🧭 Summary — What Runs Where

| Terminal / Service | Working Directory | Command | URL / Port |
|---|---|---|---|
| **Terminal 1: Backend API** | Project Root (`inteliWMS\`) | `.\venv\Scripts\python.exe -m uvicorn backend.main:app --reload --port 8000` | [http://localhost:8000](http://localhost:8000) |
| **Terminal 2: Knowledge Agent** | Project Root (`inteliWMS\`) | `.\venv\Scripts\python.exe -m uvicorn agents.knowledge_agent.server:app --reload --port 8002` | [http://localhost:8002](http://localhost:8002) |
| **Terminal 3: Frontend** | `frontend\` | `npm run dev` | [http://localhost:5173](http://localhost:5173) |
| **Terminal 4: ML Model (DemandIQ)** | `ML-MODEL\` | `..\venv\Scripts\python.exe -m uvicorn app:app --reload --port 8001` | [http://localhost:8001](http://localhost:8001) |

> 💡 **Notes:**
> - The IntelliWMS frontend automatically communicates with the backend at port 8000.
> - The ML Model service contains its own complete web UI and can be accessed independently at [http://localhost:8001](http://localhost:8001) (or port 8000 when running standalone).

---

## ❌ Common Errors & Fixes

### `cannot be loaded because running scripts is disabled`
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force
```
Then re-run your command.

---

### `ModuleNotFoundError: No module named 'fastapi'`
You ran `python` instead of the venv python.  
Always use:
```powershell
# From project root:
.\venv\Scripts\python.exe -m uvicorn ...

# Or from ML-MODEL:
..\venv\Scripts\python.exe -m uvicorn ...
```
**Not** `python -m uvicorn ...`

---

### `Port already in use` (e.g. 8000 or 8001)
```powershell
# Find the process using the port (e.g. 8001)
netstat -ano | findstr :8001

# Kill it (replace 12345 with the PID number in the last column)
taskkill /PID 12345 /F
```

---

### `npm : cannot be loaded` (script disabled)
Run the one-time fix at the top of this file, then try `npm run dev` again.

---

## 🛑 To Stop Any Service

Go to the respective terminal tab and press **`Ctrl + C`**.
