"""
ServiceNow Integration — creates incidents automatically when
CPU / RAM / Disk thresholds are breached.

Incident is created once per metric breach (deduplication).
Stores SNOW sys_id in local SQLite to avoid duplicates on restart.
"""
import os, time, threading, sqlite3, datetime
from typing import Optional
from loguru import logger

import requests
from requests.auth import HTTPBasicAuth

# ── Config ────────────────────────────────────────────────────────────────────
SNOW_INSTANCE    = os.getenv("SNOW_INSTANCE",    "")
SNOW_USER        = os.getenv("SNOW_USER",        "")
SNOW_PASSWORD    = os.getenv("SNOW_PASSWORD",    "")
SNOW_GROUP       = os.getenv("SNOW_GROUP",       "Ai-Server-Monitor")
SNOW_DB          = os.getenv("SNOW_DB",          "snow_incidents.db")
SERVER_BASE_URL  = os.getenv("SERVER_BASE_URL",  "http://15.206.180.134")

# Cooldown — don't create duplicate incident for same metric within N seconds
COOLDOWN_SECONDS = int(os.getenv("SNOW_COOLDOWN_SECONDS", "300"))  # 5 minutes

# Possible causes per metric — real, honest descriptions
CAUSES = {
    "CPU": [
        "Sudden traffic spike causing all worker threads to be busy",
        "A runaway or leaked process consuming excessive CPU cycles",
        "Background job or cron task executing at peak load time",
        "Memory pressure causing excessive CPU-bound garbage collection",
        "Insufficient instance size for current application workload",
    ],
    "RAM": [
        "Memory leak in application code — heap growing over time",
        "Too many concurrent requests holding data in memory",
        "Large dataset loaded into memory without pagination",
        "Insufficient swap space configured on the instance",
        "Multiple services competing for limited RAM on t2.micro (1GB)",
    ],
    "Disk": [
        "Log files growing without rotation — filling up /var/log",
        "Application generating large temporary files",
        "Database WAL or journal files accumulating",
        "Old deployment artifacts or Docker images not cleaned up",
        "Insufficient disk size for current data volume",
    ],
}


class ServiceNowClient:
    def __init__(self):
        self._init_db()
        self._lock = threading.Lock()

    # ── public ────────────────────────────────────────────────────────────────

    def create_incident(self, alert: dict) -> Optional[str]:
        """
        Create a ServiceNow incident for a threshold alert.
        Returns SNOW incident number (e.g. INC0010042) or None if skipped/failed.
        """
        if not SNOW_INSTANCE or not SNOW_USER or not SNOW_PASSWORD:
            logger.warning("ServiceNow not configured — set SNOW_INSTANCE, SNOW_USER, SNOW_PASSWORD in .env")
            return None

        metric = alert.get("metric", "Unknown")
        value  = alert.get("value", 0)
        thresh = alert.get("threshold", 0)
        sev    = alert.get("severity", "WARNING")
        ts     = alert.get("timestamp", datetime.datetime.now().isoformat())[:19]

        with self._lock:
            if self._is_cooldown_active(metric):
                logger.info(f"SNOW cooldown active for {metric} — skipping duplicate incident")
                return None

        short_desc = f"[AI Monitor] {metric} usage at {value:.1f}% on {SERVER_BASE_URL}"

        causes_text = "\n".join(
            f"  {i+1}. {c}" for i, c in enumerate(CAUSES.get(metric, ["Unknown cause"]))
        )

        description = f"""AI Server Monitor detected a {metric} threshold breach.

ALERT DETAILS
=============
Metric    : {metric}
Value     : {value:.1f}%
Threshold : {thresh}%
Severity  : {sev}
Time      : {ts}
Server    : {SERVER_BASE_URL}
Dashboard : {SERVER_BASE_URL}/AIMonitor/

POSSIBLE CAUSES
===============
{causes_text}

RECOMMENDED ACTIONS
===================
1. SSH into the server and run: top -b -n1 | head -20
2. Check top processes: ps aux --sort=-{"cpu" if metric=="CPU" else "mem"} | head -10
3. Review application logs in the AI Monitor dashboard
4. Check if a recent deployment or code change caused this
5. If sustained, consider upgrading the EC2 instance type

This incident was automatically raised by AI Server Monitor.
Assign to group: {SNOW_GROUP}
"""

        impact   = "2" if sev == "CRITICAL" else "3"   # 1=High 2=Medium 3=Low
        urgency  = "2" if sev == "CRITICAL" else "3"
        priority = "2" if sev == "CRITICAL" else "3"

        payload = {
            "short_description":  short_desc,
            "description":        description,
            "category":           "infrastructure",
            "subcategory":        "os",
            "impact":             impact,
            "urgency":            urgency,
            "priority":           priority,
            "assignment_group":   SNOW_GROUP,
            "caller_id":          SNOW_USER,
            "cmdb_ci":            "AI Server Monitor",
        }

        try:
            url  = f"{SNOW_INSTANCE}/api/now/table/incident"
            resp = requests.post(
                url,
                json=payload,
                auth=HTTPBasicAuth(SNOW_USER, SNOW_PASSWORD),
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                timeout=15,
            )
            if resp.status_code in (200, 201):
                data       = resp.json().get("result", {})
                inc_number = data.get("number", "")
                sys_id     = data.get("sys_id", "")
                logger.info(f"SNOW incident created: {inc_number} for {metric} ({value:.1f}%)")
                with self._lock:
                    self._record(metric, inc_number, sys_id, alert)
                return inc_number
            else:
                logger.error(f"SNOW API error {resp.status_code}: {resp.text[:200]}")
                return None
        except Exception as e:
            logger.error(f"SNOW request failed: {e}")
            return None

    def get_recent(self, limit=20) -> list:
        con  = sqlite3.connect(SNOW_DB)
        rows = con.execute(
            "SELECT * FROM snow_incidents ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        con.close()
        cols = ["id","metric","inc_number","sys_id","value","threshold","severity","created_at"]
        return [dict(zip(cols, r)) for r in rows]

    # ── DB ────────────────────────────────────────────────────────────────────

    def _init_db(self):
        con = sqlite3.connect(SNOW_DB)
        con.execute("""
            CREATE TABLE IF NOT EXISTS snow_incidents (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                metric      TEXT,
                inc_number  TEXT,
                sys_id      TEXT,
                value       REAL,
                threshold   REAL,
                severity    TEXT,
                created_at  REAL
            )
        """)
        con.commit()
        con.close()

    def _record(self, metric: str, inc_number: str, sys_id: str, alert: dict):
        con = sqlite3.connect(SNOW_DB)
        con.execute(
            "INSERT INTO snow_incidents (metric,inc_number,sys_id,value,threshold,severity,created_at) VALUES (?,?,?,?,?,?,?)",
            (metric, inc_number, sys_id,
             alert.get("value", 0), alert.get("threshold", 0),
             alert.get("severity", "WARNING"), time.time())
        )
        con.commit()
        con.close()

    def _is_cooldown_active(self, metric: str) -> bool:
        """Returns True if an incident was already created for this metric within cooldown window."""
        cutoff = time.time() - COOLDOWN_SECONDS
        con    = sqlite3.connect(SNOW_DB)
        row    = con.execute(
            "SELECT id FROM snow_incidents WHERE metric=? AND created_at > ?",
            (metric, cutoff)
        ).fetchone()
        con.close()
        return row is not None
