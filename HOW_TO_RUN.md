# 🚀 How to Run IntelliWMS (Full Stack)

> **Use PowerShell** for everything. Not CMD.  
> Open it from VS Code: `Ctrl + Shift + `` ` (backtick)

---

## ⚠️ One-Time Setup (Do This First, Ever)

Open **PowerShell** and run this **once** on your machine to allow scripts to run:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force
```

You only ever need to do this once. After this, everything works normally.

---

## 🖥️ Step-by-Step: Open 3 Terminals

In VS Code press **`Ctrl + Shift + `` `** to open a terminal.  
Click the **`+`** button in the terminal panel to open more tabs.  
You need **3 tabs open at the same time.**

---

## Terminal 1 — Backend API (Port 8000)

```powershell
cd C:\Users\sweeriyasanka\Documents\GitHub\inteliWMS\inteliWMS

.\venv\Scripts\python.exe -m uvicorn backend.main:app --reload --port 8000
```

✅ It's working when you see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

📄 Swagger API docs → http://localhost:8000/docs

---

## Terminal 2 — Knowledge Agent (Port 8002)

```powershell
cd C:\Users\sweeriyasanka\Documents\GitHub\inteliWMS\inteliWMS

.\venv\Scripts\python.exe -m uvicorn agents.knowledge_agent.server:app --reload --port 8002
```

✅ It's working when you see:
```
INFO:     Uvicorn running on http://127.0.0.1:8002
INFO:     Application startup complete.
```

📄 Knowledge Agent docs → http://localhost:8002/docs

---

## Terminal 3 — Frontend (Port 5173)

```powershell
cd C:\Users\sweeriyasanka\Documents\GitHub\inteliWMS\inteliWMS\frontend

npm run dev
```

✅ It's working when you see:
```
  VITE v6.x.x  ready in 600ms
  ➜  Local:   http://localhost:5173/
```

🌐 Open your browser → **http://localhost:5173**

---

## 🧭 Summary — What Runs Where

| Terminal | Command location | URL |
|---|---|---|
| 1 — Backend API | `inteliWMS\inteliWMS\` | http://localhost:8000 |
| 2 — Knowledge Agent | `inteliWMS\inteliWMS\` | http://localhost:8002 |
| 3 — Frontend | `inteliWMS\inteliWMS\frontend\` | http://localhost:5173 |

> The frontend **automatically** talks to the backend at port 8000.  
> You only ever open **http://localhost:5173** in your browser.

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
.\venv\Scripts\python.exe -m uvicorn ...
```
**Not** `python -m uvicorn ...`

---

### `Port 8000 already in use`
```powershell
# Find the process using the port
netstat -ano | findstr :8000

# Kill it (replace 12345 with the PID number you see)
taskkill /PID 12345 /F
```

---

### `npm : cannot be loaded` (script disabled)
Run the one-time fix at the top of this file, then try `npm run dev` again.

---

## 🛑 To Stop Everything

Go to each terminal and press **`Ctrl + C`**.
