"""
Start / stop the isolated test stacks used to capture the report evidence.
  python stacks.py start after|pi|rai     python stacks.py stop after|pi|rai     python stacks.py status
Each stack runs its own backend, Knowledge service and Vite frontend on separate ports, against its own copy of
intelliwms.db, so the developer's running servers and database are never touched.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SCRATCH = Path(os.environ.get("CAPTURE_SCRATCH", r"C:\Users\rxrat\AppData\Local\Temp\claude\c--Users-rxrat-Documents-Sliit-Y3S2-IRWA-inteliWMS\308fa24e-fed2-4518-8278-89d334a93f85\scratchpad"))
PY = str(REPO / "venv" / "Scripts" / "python.exe")
STACKS = {
    "after": {"root": REPO, "db": SCRATCH / "db" / "after.db", "api": 8020, "kb": 8022, "web": 5175},
    "pi": {"root": SCRATCH / "wt_pi", "db": SCRATCH / "db" / "pi.db", "api": 8010, "kb": 8012, "web": 5174},
    "rai": {"root": SCRATCH / "wt_rai", "db": SCRATCH / "db" / "rai.db", "api": 8030, "kb": 8032, "web": 5176},
}
PIDS = SCRATCH / "stack_pids.json"
NO_WINDOW = 0x08000000


def _env(cfg):
    env = dict(os.environ)
    env.update({
        "DATABASE_URL": "sqlite:///" + str(cfg["db"]).replace("\\", "/"),
        "TWIN_AUTO_SETUP": "false",
        "KNOWLEDGE_SERVICE_API_KEY": "",
        "INVENTORY_DEMO_DATA": "true",   # RA-23 anomaly scenario (labelled as demo data in the answer)
        "VITE_API_BASE_URL": f"http://127.0.0.1:{cfg['api']}",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8",
    })
    return env


def _wait(url, seconds=90):
    end = time.time() + seconds
    while time.time() < end:
        try:
            with urllib.request.urlopen(url, timeout=3) as r:
                if r.status < 500:
                    return True
        except Exception:
            time.sleep(1.5)
    return False


def start(name):
    cfg = STACKS[name]
    env = _env(cfg)
    logs = SCRATCH / "logs"
    logs.mkdir(exist_ok=True)
    procs = {
        "api": [PY, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", str(cfg["api"])],
        "kb": [PY, "-m", "uvicorn", "agents.knowledge_agent.server:app", "--host", "127.0.0.1", "--port", str(cfg["kb"])],
        "web": ["node", str(cfg["root"] / "frontend" / "node_modules" / "vite" / "bin" / "vite.js"), "--port", str(cfg["web"]),
                "--strictPort", "--host", "127.0.0.1"],
    }
    pids = json.loads(PIDS.read_text()) if PIDS.exists() else {}
    pids[name] = {}
    for key, cmd in procs.items():
        cwd = cfg["root"] / "frontend" if key == "web" else cfg["root"]
        out = open(logs / f"{name}_{key}.log", "w", encoding="utf-8")
        p = subprocess.Popen(cmd, cwd=str(cwd), env=env, stdout=out, stderr=subprocess.STDOUT, creationflags=NO_WINDOW)
        pids[name][key] = p.pid
    PIDS.write_text(json.dumps(pids, indent=1))
    ok = {
        "api": _wait(f"http://127.0.0.1:{cfg['api']}/health"),
        "kb": _wait(f"http://127.0.0.1:{cfg['kb']}/health"),
        "web": _wait(f"http://127.0.0.1:{cfg['web']}/"),
    }
    print(name, "started", pids[name], "ready:", ok)


def stop(name):
    pids = json.loads(PIDS.read_text()) if PIDS.exists() else {}
    for key, pid in (pids.get(name) or {}).items():
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)], capture_output=True)
    pids.pop(name, None)
    PIDS.write_text(json.dumps(pids, indent=1))
    print(name, "stopped")


if __name__ == "__main__":
    action = sys.argv[1]
    if action == "status":
        print(PIDS.read_text() if PIDS.exists() else "{}")
    else:
        (start if action == "start" else stop)(sys.argv[2])
