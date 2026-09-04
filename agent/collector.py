"""Real system metrics (psutil) + log file tailer."""
import os, time, threading, datetime, re
from typing import Callable, Optional, List
from loguru import logger
try:
    import psutil
    PSUTIL = True
except ImportError:
    PSUTIL = False

# ── HTTP status code → severity ───────────────────────────────────────────────
HTTP_STATUS_RE = re.compile(r'\b([1-5]\d{2})\b')

def _severity_from_line(line: str) -> str:
    """
    Determine severity from a log line:
    1. Check for explicit keywords (ERROR, WARNING, etc.)
    2. Check for HTTP status codes (401 → WARNING, 500 → ERROR, 200 → INFO)
    3. Default to INFO
    """
    upper = line.upper()

    # Explicit severity keywords — check these first
    for kw in ("CRITICAL", "FATAL", "ERROR", "WARNING", "WARN", "DEBUG", "INFO"):
        if kw in upper:
            return "CRITICAL" if kw == "FATAL" else kw

    # HTTP status codes
    for code_str in reversed(HTTP_STATUS_RE.findall(line)):
        code = int(code_str)
        if 500 <= code <= 599: return "ERROR"
        if 400 <= code <= 499: return "WARNING"
        if 200 <= code <= 399: return "INFO"

    return "INFO"


# ── Metrics collector ─────────────────────────────────────────────────────────
class MetricsCollector:
    def __init__(self, callback, interval=5.0,
                 cpu_threshold=80.0, ram_threshold=85.0, disk_threshold=90.0,
                 alert_callback=None):
        self.callback       = callback
        self.alert_callback = alert_callback
        self.interval       = interval
        self.cpu_th = cpu_threshold
        self.ram_th = ram_threshold
        self.disk_th = disk_threshold
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
        return {
            "cpu_percent":  cpu,
            "ram_percent":  ram.percent,
            "ram_used_gb":  round(ram.used  / 1024**3, 2),
            "ram_total_gb": round(ram.total / 1024**3, 2),
            "disk_percent": disk.percent,
            "net_sent_mb":  round(net.bytes_sent / 1024**2, 2),
            "net_recv_mb":  round(net.bytes_recv / 1024**2, 2),
            "timestamp":    datetime.datetime.now().isoformat(),
        }

    def _check_thresholds(self, m):
        alerts = []
        if m.get("cpu_percent",  0) >= self.cpu_th:
            alerts.append({"type":"threshold","metric":"CPU","value":m["cpu_percent"],
                "threshold":self.cpu_th,
                "severity":"CRITICAL" if m["cpu_percent"] >= 95 else "WARNING",
                "message":f"CPU {m['cpu_percent']}% >= {self.cpu_th}%",
                "timestamp":m["timestamp"]})
        if m.get("ram_percent",  0) >= self.ram_th:
            alerts.append({"type":"threshold","metric":"RAM","value":m["ram_percent"],
                "threshold":self.ram_th,
                "severity":"CRITICAL" if m["ram_percent"] >= 95 else "WARNING",
                "message":f"RAM {m['ram_percent']}% >= {self.ram_th}%",
                "timestamp":m["timestamp"]})
        if m.get("disk_percent", 0) >= self.disk_th:
            alerts.append({"type":"threshold","metric":"Disk","value":m["disk_percent"],
                "threshold":self.disk_th, "severity":"CRITICAL",
                "message":f"Disk {m['disk_percent']}% >= {self.disk_th}%",
                "timestamp":m["timestamp"]})
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


# ── Log file tailer ────────────────────────────────────────────────────────────
class LogTailer:
    TIMESTAMP_RE = re.compile(
        r"(?P<ts>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}[^\s]*)"
    )

    def __init__(self, log_paths: List[str], callback: Callable,
                 tail_existing: int = 100):
        """
        log_paths     : list of file paths to tail
        callback      : called with each log entry dict
        tail_existing : how many existing lines to read on startup (0 = only new lines)
        """
        self.log_paths     = log_paths
        self.callback      = callback
        self.tail_existing = tail_existing
        self._stop         = threading.Event()

    def start(self):
        self._stop.clear()
        for path in self.log_paths:
            if os.path.exists(path):
                threading.Thread(
                    target=self._tail, args=(path,), daemon=True
                ).start()
                logger.info(f"Tailing: {path}")
            else:
                logger.warning(f"Log file not found — will retry: {path}")
                threading.Thread(
                    target=self._wait_and_tail, args=(path,), daemon=True
                ).start()

    def stop(self): self._stop.set()

    def _wait_and_tail(self, path: str):
        """Wait for file to appear (up to 5 minutes), then start tailing."""
        for _ in range(300):
            if self._stop.is_set(): return
            if os.path.exists(path):
                logger.info(f"Log file appeared, starting tail: {path}")
                self._tail(path)
                return
            time.sleep(1)
        logger.error(f"Log file never appeared: {path}")

    def _parse_entry(self, line: str, app_name: str) -> dict:
        """Parse a raw log line into a structured entry dict."""
        stripped = line.strip()

        # Extract timestamp if present
        ts_match = self.TIMESTAMP_RE.search(stripped)
        timestamp = ts_match.group("ts") if ts_match else datetime.datetime.now().isoformat()

        # Determine severity
        severity = _severity_from_line(stripped)

        return {
            "raw":       stripped,
            "timestamp": timestamp,
            "severity":  severity,
            "app":       app_name,
            "message":   stripped,
        }

    def _tail(self, path: str):
        app_name = os.path.basename(path).replace(".log", "")
        try:
            with open(path, "r", errors="replace") as f:
                # ── Read last N existing lines first ──────────────────────────
                if self.tail_existing > 0:
                    all_lines = f.readlines()
                    existing = all_lines[-self.tail_existing:]
                    logger.info(f"Replaying {len(existing)} existing lines from {path}")
                    for line in existing:
                        if line.strip():
                            self.callback(self._parse_entry(line, app_name))

                # ── Now tail new lines ─────────────────────────────────────────
                f.seek(0, 2)  # seek to end for live tailing
                while not self._stop.is_set():
                    line = f.readline()
                    if not line:
                        time.sleep(0.2)
                        # Handle log rotation — reopen if file was replaced
                        try:
                            if os.stat(path).st_ino != os.fstat(f.fileno()).st_ino:
                                logger.info(f"Log rotated, reopening: {path}")
                                break
                        except OSError:
                            break
                        continue
                    if line.strip():
                        self.callback(self._parse_entry(line, app_name))

        except Exception as e:
            logger.error(f"Tailer error for {path}: {e}")
            time.sleep(2)
            if not self._stop.is_set():
                logger.info(f"Restarting tailer for {path}")
                self._tail(path)
