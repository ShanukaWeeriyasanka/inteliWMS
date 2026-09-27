# 🐳 IntelliWMS — Docker Setup Guide for Teammates

This guide provides a single, zero-friction setup for all teammates running **IntelliWMS** across Windows, macOS, or Linux using Docker and Docker Compose.

---

## ⚡ Quick Start (Run in 3 Steps)

### Step 1: Clone the repository
```bash
git clone <repository_url>
cd inteliWMS
```

### Step 2: Create your `.env` file
Copy the example environment file:
```bash
# On Linux / macOS / Git Bash:
cp .env.example .env

# On Windows PowerShell:
Copy-Item .env.example .env
```

Open `.env` and fill in your AI API key (at least one is required for agent reasoning):
```ini
GEMINI_API_KEY=your_actual_gemini_api_key_here
# or
GROQ_API_KEY=your_groq_api_key_here
```

### Step 3: Start everything with Docker
```bash
docker compose up --build
```
> 💡 *Add `-d` if you want it to run in the background: `docker compose up --build -d`*

---

## 🌐 Services & Endpoints

Once startup completes, open your browser:

| Service | URL | Description |
|---|---|---|
| 🖥️ **Web Application (UI)** | **http://localhost:3000** | Interactive React Dashboard & Warehouse Chat |
| ⚙️ **Backend API & Swagger** | **http://localhost:8000/docs** | Interactive FastAPI Documentation |
| 🗄️ **PostgreSQL Database** | `localhost:5432` | DB: `intelliwms`, User: `intelliwms_user` |
| 🧠 **ChromaDB Vector Store** | `localhost:8001` | Semantic RAG knowledge embeddings |

---

## 🔑 Pre-Seeded Demo Accounts

The database is **automatically seeded** with warehouse test accounts on initial launch:

| Role | Username | Password | Access Level |
|---|---|---|---|
| 👷 **Staff** | `john_staff` | `pass123` | View inventory, read SOPs, basic queries |
| 👩‍💼 **Manager** | `sarah_manager` | `pass456` | Trigger reorders, approve transfers, view metrics |
| ⚙️ **Admin** | `admin_user` | `admin123` | Full access, RBAC management, audit log inspection |

---

## 🏗️ Architecture Overview

Inside Docker, the services are connected via an internal network:

```
[ Teammate's Browser ]
         │
         ├─── http://localhost:3000 ──> [ Frontend Container (Nginx) ]
         │                                       │ (Reverse Proxy /auth, /query, etc.)
         │                                       ▼
         ├─── http://localhost:8000 ──> [ Backend Container (FastAPI) ]
                                                 │
                                                 ├──> [ PostgreSQL (Port 5432) ]
                                                 └──> [ ChromaDB (Port 8000/8001) ]
```

- **Frontend Container**: Multi-stage build with Node.js 20 compiling the React/Vite app, served by high-performance Nginx. Nginx handles client-side SPA routing and transparently reverse-proxies API requests to the backend container.
- **Backend Container**: Python 3.11 with FastAPI running the Coordinator Agent, Inventory Agent, and Security layer.
- **Seeder Container**: Automatically runs once after PostgreSQL becomes healthy to create all tables and populate initial warehouse data.
- **Persistent Volumes**: `postgres_data` and `chroma_data` preserve your data between container restarts.

---

## 🛠️ Helpful Docker Commands

### Stop all services
```bash
docker compose down
```

### View live logs for a specific service
```bash
# Backend logs
docker compose logs -f backend

# Frontend logs
docker compose logs -f frontend

# Database logs
docker compose logs -f postgres
```

### Completely reset database and re-seed from scratch
```bash
docker compose down -v
docker compose up --build
```

### Execute a shell inside the backend container
```bash
docker compose exec backend bash
```

---

## ❓ Troubleshooting

### 1. `docker: command not found`
Make sure you have [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running.

### 2. Port conflict: `Bind for 0.0.0.0:8000 failed: port is already allocated`
If you have a local uvicorn or postgres process running, stop it first:
- Windows: `netstat -ano | findstr :8000` then `taskkill /PID <PID> /F`
- Linux/macOS: `lsof -i :8000` then `kill -9 <PID>`

### 3. "Network Error" on login
Ensure all containers are healthy by checking `docker compose ps`. The backend must show `(healthy)` before the frontend can communicate with it.
