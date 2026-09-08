"""
Escalation Engine — SendGrid email alerts with acknowledge tokens.

Flow:
  Alert triggered → email Level 1 → wait N minutes
  No ack → email Level 2 → wait N minutes
  No ack → email Level 3 → wait N minutes
  No ack → raise CRITICAL incident

Acknowledge: recipient clicks link in email → token validated → escalation stops.
Tokens expire after ESC_TIMEOUT_MINUTES (default 5).
"""
import os, uuid, time, threading, sqlite3, json
from datetime import datetime, timezone
from typing import Optional
from loguru import logger

try:
    import sendgrid
    from sendgrid.helpers.mail import Mail
    SENDGRID_OK = True
except ImportError:
    SENDGRID_OK = False
    logger.warning("sendgrid not installed — email alerts disabled. pip install sendgrid")

# ── Config from .env ──────────────────────────────────────────────────────────
SENDGRID_API_KEY     = os.getenv("SENDGRID_API_KEY", "")
ALERT_FROM_EMAIL     = os.getenv("ALERT_FROM_EMAIL", "alerts@example.com")
SERVER_BASE_URL      = os.getenv("SERVER_BASE_URL",  "http://15.206.180.134")
ESC_TIMEOUT_MINUTES  = int(os.getenv("ESC_TIMEOUT_MINUTES", "5"))
ESC_DB               = os.getenv("ESC_DB", "escalations.db")

CONTACTS = [
    {
        "level": 1,
        "name":  os.getenv("ESC_L1_NAME",  "On-Call Engineer"),
        "email": os.getenv("ESC_L1_EMAIL", ""),
    },
    {
        "level": 2,
        "name":  os.getenv("ESC_L2_NAME",  "Senior Engineer"),
        "email": os.getenv("ESC_L2_EMAIL", ""),
    },
    {
        "level": 3,
        "name":  os.getenv("ESC_L3_NAME",  "Engineering Manager"),
        "email": os.getenv("ESC_L3_EMAIL", ""),
    },
]


class EscalationManager:
    def __init__(self, incident_callback=None):
        """
        incident_callback: called when all levels exhausted — receives alert dict
        """
        self.incident_callback = incident_callback
        self._init_db()

    # ── public API ────────────────────────────────────────────────────────────

    def trigger(self, alert: dict):
        """
        Start escalation for a threshold alert.
        Only triggers if no active escalation for same metric exists.
        """
        metric = alert.get("metric", "unknown")
        if self._has_active(metric):
            logger.info(f"Escalation already active for {metric} — skipping")
            return

        esc_id = str(uuid.uuid4())[:8].upper()
        token  = str(uuid.uuid4())
        now    = time.time()

        self._save_escalation({
            "esc_id":       esc_id,
            "metric":       metric,
            "alert":        json.dumps(alert),
            "current_level": 1,
            "status":       "active",
            "token":        token,
            "token_expires": now + ESC_TIMEOUT_MINUTES * 60,
            "created_at":   now,
            "updated_at":   now,
            "acked_by":     "",
        })

        logger.warning(f"Escalation [{esc_id}] started for {metric}")
        self._send_level(esc_id, 1, alert, token)

        # Start background watcher
        threading.Thread(
            target=self._watch, args=(esc_id,), daemon=True
        ).start()

    def acknowledge(self, token: str) -> dict:
        """
        Called when someone clicks the acknowledge link in the email.
        Returns status dict.
        """
        esc = self._load_by_token(token)
        if not esc:
            return {"status": "error", "message": "Invalid or expired token"}

        now = time.time()
        if now > esc["token_expires"]:
            return {"status": "expired", "message": "This acknowledge link has expired"}

        if esc["status"] != "active":
            return {"status": "already_resolved",
                    "message": f"Already {esc['status']} by {esc['acked_by']}"}

        level   = esc["current_level"]
        contact = CONTACTS[level - 1]
        self._update_escalation(esc["esc_id"], {
            "status":    "acknowledged",
            "acked_by":  contact["name"],
            "updated_at": now,
        })

        logger.info(f"Escalation [{esc['esc_id']}] acknowledged by {contact['name']}")
        return {
            "status":  "ok",
            "message": f"Alert acknowledged by {contact['name']}. Thank you!",
            "esc_id":  esc["esc_id"],
        }

    def get_all(self, limit=20) -> list:
        con = sqlite3.connect(ESC_DB)
        rows = con.execute(
            "SELECT * FROM escalations ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        con.close()
        cols = ["esc_id","metric","alert","current_level","status","token",
                "token_expires","created_at","updated_at","acked_by"]
        result = []
        for row in rows:
            d = dict(zip(cols, row))
            d["alert"] = json.loads(d.get("alert","{}"))
            result.append(d)
        return result

    # ── internals ─────────────────────────────────────────────────────────────

    def _watch(self, esc_id: str):
        """Background thread: check every 30s if ack happened, escalate if not."""
        timeout = ESC_TIMEOUT_MINUTES * 60
        time.sleep(timeout)

        esc = self._load(esc_id)
        if not esc or esc["status"] != "active":
            return  # acknowledged or already resolved

        current = esc["current_level"]
        alert   = json.loads(esc["alert"])

        if current < 3:
            # Escalate to next level
            next_level = current + 1
            new_token  = str(uuid.uuid4())
            now        = time.time()
            self._update_escalation(esc_id, {
                "current_level": next_level,
                "token":         new_token,
                "token_expires": now + ESC_TIMEOUT_MINUTES * 60,
                "updated_at":    now,
            })
            logger.warning(f"Escalation [{esc_id}] escalating to Level {next_level}")
            self._send_level(esc_id, next_level, alert, new_token)
            # Watch again for next level
            threading.Thread(
                target=self._watch, args=(esc_id,), daemon=True
            ).start()
        else:
            # All levels exhausted — raise critical incident
            logger.error(f"Escalation [{esc_id}] — all levels unresponsive. Raising critical incident.")
            self._update_escalation(esc_id, {
                "status":     "incident_raised",
                "updated_at": time.time(),
            })
            if self.incident_callback:
                self.incident_callback({
                    **alert,
                    "severity": "CRITICAL",
                    "message":  f"[AUTO-INCIDENT] {alert.get('message','')} — no response from escalation chain",
                    "esc_id":   esc_id,
                })

    def _send_level(self, esc_id: str, level: int, alert: dict, token: str):
        contact = CONTACTS[level - 1]
        if not contact["email"]:
            logger.warning(f"No email for Level {level} — skipping")
            return

        ack_url  = f"{SERVER_BASE_URL}/AIMonitor-api/escalation/ack/{token}"
        metric   = alert.get("metric", "Server")
        value    = alert.get("value", 0)
        thresh   = alert.get("threshold", 0)
        sev      = alert.get("severity", "WARNING")
        ts       = alert.get("timestamp", datetime.now().isoformat())[:19]
        prev_msg = ""
        if level > 1:
            prev_contact = CONTACTS[level - 2]
            prev_msg = f"<p style='color:#f59e0b'>⚠ Level {level-1} ({prev_contact['name']}) did not respond within {ESC_TIMEOUT_MINUTES} minutes.</p>"

        html = f"""
<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#0d1117;color:#e6edf3;border-radius:12px;overflow:hidden">
  <div style="background:#161b22;padding:24px;border-bottom:1px solid #30363d">
    <h2 style="margin:0;color:#f85149">🚨 Server Alert — Level {level} Escalation</h2>
    <p style="margin:4px 0 0;color:#8b949e">AI Server Monitor — {ts}</p>
  </div>
  <div style="padding:24px">
    {prev_msg}
    <div style="background:#21262d;border-radius:8px;padding:16px;margin-bottom:20px;border-left:4px solid {'#f85149' if sev=='CRITICAL' else '#f59e0b'}">
      <div style="font-size:13px;color:#8b949e;margin-bottom:8px">ALERT DETAILS</div>
      <div style="font-size:20px;font-weight:bold;color:{'#f85149' if sev=='CRITICAL' else '#f59e0b'}">{metric} at {value:.1f}%</div>
      <div style="color:#8b949e;margin-top:4px">Threshold: {thresh}% | Severity: {sev}</div>
      <div style="color:#8b949e;margin-top:4px">Server: {SERVER_BASE_URL}</div>
    </div>
    <p style="color:#e6edf3">Hi {contact['name']},</p>
    <p style="color:#8b949e">This is a Level {level} escalation. Please acknowledge this alert within <strong style="color:#fff">{ESC_TIMEOUT_MINUTES} minutes</strong> or it will be escalated further.</p>
    <div style="text-align:center;margin:28px 0">
      <a href="{ack_url}" style="background:#238636;color:white;padding:14px 32px;border-radius:8px;text-decoration:none;font-size:16px;font-weight:bold;display:inline-block">
        ✅ Acknowledge Alert
      </a>
    </div>
    <p style="color:#6e7681;font-size:12px;text-align:center">
      This link expires in {ESC_TIMEOUT_MINUTES} minutes.<br>
      Escalation ID: {esc_id} | View dashboard: <a href="{SERVER_BASE_URL}/AIMonitor/" style="color:#58a6ff">{SERVER_BASE_URL}/AIMonitor/</a>
    </p>
  </div>
</div>
"""
        self._send_email(
            to_email=contact["email"],
            to_name=contact["name"],
            subject=f"[{sev}] {metric} Alert — Level {level} Escalation (ESC-{esc_id})",
            html=html,
        )

    def _send_email(self, to_email: str, to_name: str, subject: str, html: str):
        if not SENDGRID_OK:
            logger.warning(f"SendGrid not available — would send to {to_email}: {subject}")
            return
        if not SENDGRID_API_KEY:
            logger.warning("SENDGRID_API_KEY not set — skipping email")
            return
        try:
            sg  = sendgrid.SendGridAPIClient(api_key=SENDGRID_API_KEY)
            msg = Mail(
                from_email=ALERT_FROM_EMAIL,
                to_emails=to_email,
                subject=subject,
                html_content=html,
            )
            resp = sg.client.mail.send.post(request_body=msg.get())
            logger.info(f"Email sent to {to_email} — status {resp.status_code}")
        except Exception as e:
            logger.error(f"Email send failed: {e}")

    # ── DB ────────────────────────────────────────────────────────────────────

    def _init_db(self):
        con = sqlite3.connect(ESC_DB)
        con.execute("""
            CREATE TABLE IF NOT EXISTS escalations (
                esc_id         TEXT PRIMARY KEY,
                metric         TEXT,
                alert          TEXT,
                current_level  INTEGER,
                status         TEXT,
                token          TEXT,
                token_expires  REAL,
                created_at     REAL,
                updated_at     REAL,
                acked_by       TEXT
            )
        """)
        con.commit()
        con.close()

    def _save_escalation(self, d: dict):
        con = sqlite3.connect(ESC_DB)
        con.execute("""
            INSERT INTO escalations
            (esc_id,metric,alert,current_level,status,token,token_expires,created_at,updated_at,acked_by)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (d["esc_id"],d["metric"],d["alert"],d["current_level"],d["status"],
              d["token"],d["token_expires"],d["created_at"],d["updated_at"],d["acked_by"]))
        con.commit()
        con.close()

    def _update_escalation(self, esc_id: str, fields: dict):
        sets  = ", ".join(f"{k}=?" for k in fields)
        vals  = list(fields.values()) + [esc_id]
        con   = sqlite3.connect(ESC_DB)
        con.execute(f"UPDATE escalations SET {sets} WHERE esc_id=?", vals)
        con.commit()
        con.close()

    def _load(self, esc_id: str) -> Optional[dict]:
        con  = sqlite3.connect(ESC_DB)
        row  = con.execute("SELECT * FROM escalations WHERE esc_id=?", (esc_id,)).fetchone()
        con.close()
        if not row: return None
        cols = ["esc_id","metric","alert","current_level","status","token",
                "token_expires","created_at","updated_at","acked_by"]
        return dict(zip(cols, row))

    def _load_by_token(self, token: str) -> Optional[dict]:
        con  = sqlite3.connect(ESC_DB)
        row  = con.execute("SELECT * FROM escalations WHERE token=?", (token,)).fetchone()
        con.close()
        if not row: return None
        cols = ["esc_id","metric","alert","current_level","status","token",
                "token_expires","created_at","updated_at","acked_by"]
        return dict(zip(cols, row))

    def _has_active(self, metric: str) -> bool:
        con = sqlite3.connect(ESC_DB)
        row = con.execute(
            "SELECT esc_id FROM escalations WHERE metric=? AND status='active'", (metric,)
        ).fetchone()
        con.close()
        return row is not None
