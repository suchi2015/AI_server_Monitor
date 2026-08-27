"""Generates realistic fake server logs + metrics for demo."""
import random, time, datetime, threading
from typing import Callable, Optional

APPS = {
    "nginx": [
        ("INFO",     "{ip} - [{ts}] GET /api/v1/users 200"),
        ("INFO",     "{ip} - [{ts}] POST /api/v1/login 200"),
        ("WARNING",  "{ip} - [{ts}] GET /admin 403"),
        ("ERROR",    "{ip} - [{ts}] GET /api/v1/data 500"),
        ("ERROR",    "connect() failed (111: Connection refused) upstream"),
        ("WARNING",  "upstream response time 30.123s from 10.0.0.5:8080"),
    ],
    "postgres": [
        ("INFO",     "connection received: host={ip} port=54321"),
        ("INFO",     "statement: SELECT * FROM users WHERE id=$1"),
        ("WARNING",  "slow query 5432ms: SELECT * FROM orders"),
        ("ERROR",    "FATAL: too many connections"),
        ("ERROR",    "duplicate key violates unique constraint users_pkey"),
        ("CRITICAL", "PANIC: No space left on device pg_wal"),
    ],
    "app-service": [
        ("INFO",     "User {uid} logged in successfully"),
        ("INFO",     "Processing payment order {oid}"),
        ("WARNING",  "Retry attempt 3/5 for external API call"),
        ("ERROR",    "NullPointerException at PaymentService.java:142"),
        ("ERROR",    "Failed to connect to Redis: Connection timed out"),
        ("CRITICAL", "OutOfMemoryError: Java heap space"),
    ],
    "redis": [
        ("INFO",     "Accepted {ip}:43210"),
        ("WARNING",  "MISCONF Redis configured to save RDB but cannot"),
        ("ERROR",    "Failed opening RDB file on /data"),
        ("WARNING",  "Memory usage 75pct of maxmemory"),
    ],
    "system": [
        ("INFO",     "systemd: Started Daily apt download activities"),
        ("WARNING",  "kernel: TCP out of memory"),
        ("ERROR",    "kernel: EXT4-fs error device sda1 ext4_find_entry"),
        ("INFO",     "sshd: Accepted publickey for ubuntu from {ip}"),
        ("CRITICAL", "kernel: Out of memory: Kill process 1234 score 900"),
    ],
}

IPS   = ["10.0.0.1","10.0.0.2","192.168.1.100","172.16.0.5"]
UIDS  = ["u1001","u2342","u9921","u0012"]
OIDS  = ["ord-441","ord-882","ord-119"]

def _fill(t):
    ts = datetime.datetime.now().strftime("%d/%b/%Y:%H:%M:%S")
    return (t.replace("{ip}", random.choice(IPS))
             .replace("{ts}", ts)
             .replace("{uid}", random.choice(UIDS))
             .replace("{oid}", random.choice(OIDS)))

def generate_log_line(force_anomaly=False):
    app = random.choice(list(APPS.keys()))
    templates = APPS[app]
    if force_anomaly:
        choices = [(s,t) for s,t in templates if s in ("ERROR","CRITICAL","WARNING")]
        severity, tmpl = random.choice(choices or templates)
    else:
        weights = [{"INFO":70,"WARNING":20,"ERROR":8,"CRITICAL":2}.get(s,5) for s,_ in templates]
        severity, tmpl = random.choices(templates, weights=weights, k=1)[0]
    msg = _fill(tmpl)
    ts  = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return {"raw": f"{ts} {severity} {app}: {msg}",
            "app": app, "severity": severity, "message": msg, "timestamp": ts}

def generate_metrics(spike=False):
    cpu  = min(100, round(random.gauss(45, 15) + (random.uniform(30,50) if spike else 0), 1))
    ram  = min(100, round(random.gauss(60, 10) + (random.uniform(20,35) if spike else 0), 1))
    disk = min(100, round(random.gauss(55,  5), 1))
    return {"cpu_percent": cpu, "ram_percent": ram, "disk_percent": disk,
            "net_sent_mb": round(random.uniform(0.1,5.0),2),
            "net_recv_mb": round(random.uniform(0.1,10.0),2),
            "timestamp":   datetime.datetime.now().isoformat()}

class LogSimulator:
    def __init__(self, log_callback, metrics_callback,
                 lines_per_second=2.0, anomaly_probability=0.06):
        self.log_cb     = log_callback
        self.met_cb     = metrics_callback
        self.lps        = lines_per_second
        self.anom_prob  = anomaly_probability
        self._stop      = threading.Event()
        self._thread    = None

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _run(self):
        counter = 0
        while not self._stop.is_set():
            spike = random.random() < self.anom_prob
            self.log_cb(generate_log_line(force_anomaly=spike))
            counter += 1
            if counter % 5 == 0:
                self.met_cb(generate_metrics(spike=spike))
            time.sleep(1.0 / self.lps)
