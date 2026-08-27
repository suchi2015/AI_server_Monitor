"""
AI Server Monitor v2 — FastAPI Backend
Monitors: food-app, servicenow-monitor, confluence-chatbot
"""
import os, sys, asyncio, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from loguru import logger
from dotenv import load_dotenv
load_dotenv()

from state import state
from incidents import IncidentManager
from model.log_model import LogModel

# ── Config
DEMO_MODE      = os.getenv("DEMO_MODE", "True").lower() == "true"
CPU_THRESHOLD  = float(os.getenv("CPU_THRESHOLD",  "80"))
RAM_THRESHOLD  = float(os.getenv("RAM_THRESHOLD",  "85"))
DISK_THRESHOLD = float(os.getenv("DISK_THRESHOLD", "90"))
WINDOW_SIZE    = int(os.getenv("WINDOW_SIZE", "10"))

APPS = {
    "food-app":             os.getenv("FOOD_APP_LOG",       "/var/log/food-app/app.log"),
    "servicenow-monitor":   os.getenv("SERVICENOW_LOG",     "/var/log/servicenow-monitor/app.log"),
    "confluence-chatbot":   os.getenv("CONFLUENCE_LOG",     "/var/log/confluence-chatbot/app.log"),
}

app = FastAPI(title="AI Server Monitor v2", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

_loop = None


# ── WebSocket manager
class WSManager:
    def __init__(self): self.active = []
    async def connect(self, ws):
        await ws.accept(); self.active.append(ws)
    def disconnect(self, ws):
        if ws in self.active: self.active.remove(ws)
    async def broadcast(self, data):
        dead = []
        for ws in self.active:
            try:    await ws.send_json(data)
            except: dead.append(ws)
        for ws in dead: self.active.remove(ws)

manager = WSManager()

def _broadcast(data):
    if _loop:
        _loop.call_soon_threadsafe(asyncio.ensure_future, manager.broadcast(data))


# ── Callbacks
def on_log(entry: dict):
    with state.lock:
        result = state.model.ingest_line(entry["raw"])
    result["timestamp"] = result.get("timestamp") or entry.get("timestamp", "")
    result["app"]       = entry.get("app", result.get("app", "unknown"))

    with state.lock:
        state.logs.append(result)
        app_name = result["app"]
        if app_name not in state.app_stats:
            state.app_stats[app_name] = {
                "name": app_name, "total": 0, "errors": 0,
                "warnings": 0, "anomalies": 0, "last_seen": ""
            }
        state.app_stats[app_name]["total"]     += 1
        state.app_stats[app_name]["last_seen"]  = result["timestamp"]
        sev = result.get("severity", "INFO")
        if sev in ("ERROR", "CRITICAL", "FATAL"):
            state.app_stats[app_name]["errors"] += 1
        elif sev == "WARNING":
            state.app_stats[app_name]["warnings"] += 1

        if result.get("is_anomaly"):
            state.app_stats[app_name]["anomalies"] += 1
            state.anomalies.append(result)
            alert = {
                "type": "anomaly", "app": result["app"],
                "severity": result["severity"],
                "message": result.get("explanation") or result["message"],
                "timestamp": result["timestamp"],
                "anomaly_score": result.get("anomaly_score", 0),
                "template": result.get("template", ""),
                "raw": result.get("raw", ""),
                "is_anomaly": True,
            }
            state.alerts.append(alert)
            incident = state.incident_mgr.process_event(alert)
            if incident:
                _broadcast({"type": "incident", "data": _clean(incident)})

    _broadcast({"type": "log", "data": result})


def on_metrics(metrics: dict):
    with state.lock:
        state.metrics.append(metrics)
    alerts = []
    if metrics.get("cpu_percent",  0) >= CPU_THRESHOLD:
        alerts.append({
            "type": "threshold", "metric": "CPU",
            "value": metrics["cpu_percent"], "threshold": CPU_THRESHOLD,
            "severity": "CRITICAL" if metrics["cpu_percent"] >= 95 else "WARNING",
            "message": f"CPU {metrics['cpu_percent']:.1f}% exceeds {CPU_THRESHOLD}%",
            "timestamp": metrics.get("timestamp", ""),
        })
    if metrics.get("ram_percent",  0) >= RAM_THRESHOLD:
        alerts.append({
            "type": "threshold", "metric": "RAM",
            "value": metrics["ram_percent"], "threshold": RAM_THRESHOLD,
            "severity": "CRITICAL" if metrics["ram_percent"] >= 95 else "WARNING",
            "message": f"RAM {metrics['ram_percent']:.1f}% exceeds {RAM_THRESHOLD}%",
            "timestamp": metrics.get("timestamp", ""),
        })
    if metrics.get("disk_percent", 0) >= DISK_THRESHOLD:
        alerts.append({
            "type": "threshold", "metric": "Disk",
            "value": metrics["disk_percent"], "threshold": DISK_THRESHOLD,
            "severity": "CRITICAL",
            "message": f"Disk {metrics['disk_percent']:.1f}% exceeds {DISK_THRESHOLD}%",
            "timestamp": metrics.get("timestamp", ""),
        })
    with state.lock:
        for a in alerts: state.alerts.append(a)
    for a in alerts:
        state.incident_mgr.process_event(a)
        _broadcast({"type": "alert", "data": a})
    _broadcast({"type": "metrics", "data": metrics})


def _clean(inc: dict) -> dict:
    safe = {k: v for k, v in inc.items() if k != "events"}
    safe["events"] = [{k2: v2 for k2, v2 in e.items() if k2 != "_ts"}
                      for e in inc.get("events", [])]
    return safe


# ── Startup
@app.on_event("startup")
async def startup():
    global _loop
    _loop = asyncio.get_event_loop()
    logger.info("Starting AI Server Monitor v2...")

    state.model        = LogModel(window_size=WINDOW_SIZE)
    state.incident_mgr = IncidentManager()

    # Init app stats for known apps
    for app_name in APPS:
        state.app_stats[app_name] = {
            "name": app_name, "total": 0, "errors": 0,
            "warnings": 0, "anomalies": 0, "last_seen": ""
        }

    if DEMO_MODE:
        from simulator.log_simulator import LogSimulator, generate_log_line
        logger.info("Demo mode: pre-training on 300 logs...")
        normal = [generate_log_line(force_anomaly=False)["raw"] for _ in range(300)]
        await _loop.run_in_executor(None,
            lambda: state.model.train_on_logs(normal, epochs=30))
        state.training_done = True
        from simulator.multi_app_simulator import MultiAppSimulator
        sim = MultiAppSimulator(on_log, on_metrics, list(APPS.keys()))
        sim.start()
        app.state.simulator = sim
        logger.info("Demo simulator started.")
    else:
        from agent.collector import MetricsCollector, LogTailer
        for app_name, log_path in APPS.items():
            if os.path.exists(log_path):
                LogTailer([log_path], lambda e, a=app_name: on_log({**e, "app": a})).start()
                logger.info(f"Tailing {app_name}: {log_path}")
            else:
                logger.warning(f"Log not found for {app_name}: {log_path}")
        MetricsCollector(on_metrics,
                         cpu_threshold=CPU_THRESHOLD,
                         ram_threshold=RAM_THRESHOLD,
                         disk_threshold=DISK_THRESHOLD).start()
        state.training_done = True


# ── REST API
@app.get("/api/status")
def get_status():
    with state.lock:
        return {
            "model_trained":   state.training_done,
            "num_templates":   state.model.parser.get_num_classes() if state.model else 0,
            "total_logs":      len(state.logs),
            "total_anomalies": len(state.anomalies),
            "total_alerts":    len(state.alerts),
            "open_incidents":  len(state.incident_mgr.get_open()),
            "demo_mode":       DEMO_MODE,
        }

@app.get("/api/apps")
def get_apps():
    with state.lock:
        stats = list(state.app_stats.values())
    result = []
    for s in stats:
        total = s["total"] or 1
        errors   = s["errors"]
        warnings = s["warnings"]
        status = "healthy"
        if errors > 0 or s["anomalies"] > 0: status = "critical"
        elif warnings > 0:                    status = "warning"
        result.append({**s, "status": status,
                        "error_rate": round(errors / total * 100, 1)})
    return {"apps": result}

@app.get("/api/apps/{app_name}/logs")
def get_app_logs(app_name: str, limit: int = 50):
    with state.lock:
        logs = [l for l in state.logs if l.get("app") == app_name][-limit:]
    return {"logs": logs[::-1]}

@app.get("/api/apps/{app_name}/anomalies")
def get_app_anomalies(app_name: str, limit: int = 20):
    with state.lock:
        anoms = [a for a in state.anomalies if a.get("app") == app_name][-limit:]
    return {"anomalies": anoms[::-1]}

@app.get("/api/logs")
def get_logs(limit: int = 100):
    with state.lock: data = list(state.logs)[-limit:]
    return {"logs": data[::-1]}

@app.get("/api/anomalies")
def get_anomalies(limit: int = 50):
    with state.lock: data = list(state.anomalies)[-limit:]
    return {"anomalies": data[::-1]}

@app.get("/api/metrics")
def get_metrics(limit: int = 60):
    with state.lock: data = list(state.metrics)[-limit:]
    return {"metrics": data}

@app.get("/api/alerts")
def get_alerts(limit: int = 50):
    with state.lock: data = list(state.alerts)[-limit:]
    return {"alerts": data[::-1]}

@app.get("/api/incidents")
def get_incidents(limit: int = 50):
    return {"incidents": state.incident_mgr.get_all(limit)}

@app.get("/api/incidents/open")
def get_open_incidents():
    incs = state.incident_mgr.get_open()
    return {"incidents": incs, "count": len(incs)}

@app.post("/api/incidents/{incident_id}/resolve")
def resolve_incident(incident_id: str):
    state.incident_mgr.resolve(incident_id)
    return {"status": "resolved"}

class TrainReq(BaseModel):
    epochs: int = 50

@app.post("/api/train")
async def train(req: TrainReq):
    from fastapi.concurrency import run_in_threadpool
    with state.lock:
        logs = [l["raw"] for l in state.logs if l.get("raw")]
    if len(logs) < 50:
        return {"status": "error", "message": "Need at least 50 logs"}
    await run_in_threadpool(lambda: state.model.train_on_logs(logs, epochs=req.epochs))
    with state.lock: state.training_done = True
    return {"status": "done", "log_count": len(logs)}

@app.websocket("/ws/live")
async def ws_live(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True: await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)
