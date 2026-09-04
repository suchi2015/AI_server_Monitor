"""Real system metrics (psutil) + log file tailer."""
import os, time, threading, datetime, re
from typing import Callable, Optional, List
from loguru import logger
try:
    import psutil
    PSUTIL = True
except ImportError:
    PSUTIL = False

# Detect HTTP status codes in log lines and map to severity
HTTP_STATUS_RE = re.compile(r'\b([1-5]\d{2})\b')

def _severity_from_http(line: str) -> Optional[str]:
    """
    Scan a log line for HTTP status codes.
    Returns severity string if found, else None.
    """
    matches = HTTP_STATUS_RE.findall(line)
    if not matches:
        return None
    # Take the last numeric match that looks like HTTP status
    for code_str in reversed(matches):
        code = int(code_str)
        if 100 <= code <= 599:
            if code >= 500:
                return "ERROR"
            elif code == 404:
                return "WARNING"
            elif code in (401, 403):
                return "WARNING"
            elif 400 <= code < 500:
                return "WARNING"
            elif 300 <= code < 400:
                return "INFO"
            elif 200 <= code < 300:
                return "INFO"
    return None

class MetricsCollector:
    def __init__(self, callback, interval=5.0,
                 cpu_threshold=80.0, ram_threshold=85.0, disk_threshold=90.0,
                 alert_callback=None):
        self.callback       = callback
        self.alert_callback = alert_callback
        self.interval       = interval
        self.cpu_th, self.ram_th, self.disk_th = cpu_threshold, ram_threshold, disk_threshold
        self._stop = threading.Event()

    def start(self):
        self._stop.clear()
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self): self._stop.set()

    def _collect(self):
        if not PSUTIL: return {}
        cpu  = psutil.cpu_percent(interval=1)
        ram  = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        net  = psutil.net_io_counters()
        return {"cpu_percent": cpu, "ram_percent": ram.percent,
                "ram_used_gb": round(ram.used/1024**3,2), "ram_total_gb": round(ram.total/1024**3,2),
                "disk_percent": disk.percent,
                "net_sent_mb": round(net.bytes_sent/1024**2,2),
                "net_recv_mb": round(net.bytes_recv/1024**2,2),
                "timestamp": datetime.datetime.now().isoformat()}

    def _check_thresholds(self, m):
        alerts = []
        if m.get("cpu_percent",0)  >= self.cpu_th:
            alerts.append({"type":"threshold","metric":"CPU","value":m["cpu_percent"],
                "threshold":self.cpu_th,"severity":"CRITICAL" if m["cpu_percent"]>=95 else "WARNING",
                "message":f"CPU {m['cpu_percent']}% >= {self.cpu_th}%","timestamp":m["timestamp"]})
        if m.get("ram_percent",0)  >= self.ram_th:
            alerts.append({"type":"threshold","metric":"RAM","value":m["ram_percent"],
                "threshold":self.ram_th,"severity":"CRITICAL" if m["ram_percent"]>=95 else "WARNING",
                "message":f"RAM {m['ram_percent']}% >= {self.ram_th}%","timestamp":m["timestamp"]})
        if m.get("disk_percent",0) >= self.disk_th:
            alerts.append({"type":"threshold","metric":"Disk","value":m["disk_percent"],
                "threshold":self.disk_th,"severity":"CRITICAL",
                "message":f"Disk {m['disk_percent']}% >= {self.disk_th}%","timestamp":m["timestamp"]})
        for a in alerts:
            logger.warning(f"ALERT: {a['message']}")
            if self.alert_callback: self.alert_callback(a)

    def _run(self):
        while not self._stop.is_set():
            m = self._collect()
            if m:
                self.callback(m)
                self._check_thresholds(m)
            time.sleep(self.interval)


class LogTailer:
    LOG_RE = re.compile(
        r"(?P<timestamp>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}[^\s]*)?\s*"
        r"(?P<severity>DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL|FATAL)?\s*"
        r"(?P<app>[\w\-\.]+)?[:\s]+(?P<message>.+)", re.IGNORECASE)

    def __init__(self, log_paths: List[str], callback):
        self.log_paths = log_paths
        self.callback  = callback
        self._stop     = threading.Event()

    def start(self):
        self._stop.clear()
        for path in self.log_paths:
            if os.path.exists(path):
                threading.Thread(target=self._tail, args=(path,), daemon=True).start()
                logger.info(f"Tailing: {path}")
            else:
                logger.warning(f"Not found: {path}")

    def stop(self): self._stop.set()

    def _tail(self, path):
        with open(path, "r", errors="replace") as f:
            f.seek(0, 2)
            while not self._stop.is_set():
                line = f.readline()
                if not line:
                    time.sleep(0.1)
                    continue
                stripped = line.strip()
                if not stripped:
                    continue

                m = self.LOG_RE.match(stripped)

                # Determine severity:
                # 1. Try explicit keyword (ERROR, WARNING, etc.)
                # 2. Fall back to HTTP status code detection
                # 3. Default to INFO
                explicit_sev = (m.group("severity") if m else None)
                if explicit_sev:
                    severity = explicit_sev.upper()
                else:
                    http_sev = _severity_from_http(stripped)
                    severity = http_sev if http_sev else "INFO"

                entry = {
                    "raw":       stripped,
                    "timestamp": (m.group("timestamp") if m else None) or datetime.datetime.now().isoformat(),
                    "severity":  severity,
                    "app":       (m.group("app") if m else None) or os.path.basename(path),
                    "message":   stripped,
                }
                self.callback(entry)
