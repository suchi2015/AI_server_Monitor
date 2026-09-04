"""
Incident Manager:
- Wraps CorrelationEngine + RootCause + Recommender
- Persists incidents to SQLite (free, no external DB needed)
- Provides clean API for backend/main.py
"""
import sqlite3, json, time, os, threading
from typing import List, Optional
from loguru import logger

from model.correlator  import CorrelationEngine
from model.root_cause  import analyze as get_root_cause
from model.recommender import get_recommendations


DB_PATH = os.getenv("INCIDENT_DB", "incidents.db")


class IncidentManager:
    def __init__(self, time_window=60, burst_threshold=3):
        self.lock       = threading.Lock()
        self.correlator = CorrelationEngine(time_window=time_window,
                                            burst_threshold=burst_threshold)
        self._init_db()

    # ── public API ────────────────────────────────────────────────────────────

    def process_event(self, event: dict) -> Optional[dict]:
        """
        Feed an anomaly/alert event.
        Returns enriched incident if one is formed/updated.
        """
        with self.lock:
            incident = self.correlator.add_event(event)
        if incident:
            self._enrich(incident)
            self._save(incident)
            logger.warning(
                f"[{incident['incident_id']}] {incident['summary']} | "
                f"root_cause={incident['root_cause'][:60] if incident['root_cause'] else 'N/A'}..."
            )
        return incident

    def get_all(self, limit=50) -> List[dict]:
        return self._load(limit)

    def get_open(self) -> List[dict]:
        return [i for i in self._load(100) if i.get("status") == "open"]

    def resolve(self, incident_id: str):
        with self.lock:
            self.correlator.close_incident(incident_id)
        self._update_status(incident_id, "resolved")

    def clear_all(self):
        """Delete all incidents from DB and reset correlator state."""
        with self.lock:
            self.correlator = CorrelationEngine(
                time_window=self.correlator.time_window,
                burst_threshold=self.correlator.burst_threshold
            )
        try:
            con = sqlite3.connect(DB_PATH)
            con.execute("DELETE FROM incidents")
            con.commit()
            con.close()
            logger.info("All incidents cleared.")
        except Exception as e:
            logger.error(f"Clear error: {e}")

    # ── enrichment ────────────────────────────────────────────────────────────

    def _enrich(self, incident: dict):
        """Add root cause and recommendations if not already set."""
        if not incident.get("root_cause"):
            incident["root_cause"]      = get_root_cause(incident)
            incident["recommendation"]  = get_recommendations(incident["root_cause"])

    # ── SQLite persistence ────────────────────────────────────────────────────

    def _init_db(self):
        con = sqlite3.connect(DB_PATH)
        con.execute("""
            CREATE TABLE IF NOT EXISTS incidents (
                incident_id  TEXT PRIMARY KEY,
                pattern      TEXT,
                summary      TEXT,
                severity     TEXT,
                affected_apps TEXT,
                event_count  INTEGER,
                root_cause   TEXT,
                recommendation TEXT,
                status       TEXT,
                created_at   REAL,
                updated_at   REAL
            )
        """)
        con.commit()
        con.close()

    def _save(self, inc: dict):
        con = sqlite3.connect(DB_PATH)
        con.execute("""
            INSERT OR REPLACE INTO incidents
            (incident_id, pattern, summary, severity, affected_apps,
             event_count, root_cause, recommendation, status, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (
            inc["incident_id"],
            inc["pattern"],
            inc["summary"],
            inc["severity"],
            json.dumps(inc.get("affected_apps", [])),
            inc.get("event_count", 0),
            inc.get("root_cause", ""),
            json.dumps(inc.get("recommendation", [])),
            inc.get("status", "open"),
            inc.get("created_at", time.time()),
            inc.get("updated_at", time.time()),
        ))
        con.commit()
        con.close()

    def _load(self, limit=50) -> List[dict]:
        try:
            con = sqlite3.connect(DB_PATH)
            rows = con.execute(
                "SELECT * FROM incidents ORDER BY updated_at DESC LIMIT ?", (limit,)
            ).fetchall()
            con.close()
            cols = ["incident_id","pattern","summary","severity","affected_apps",
                    "event_count","root_cause","recommendation","status",
                    "created_at","updated_at"]
            result = []
            for row in rows:
                d = dict(zip(cols, row))
                d["affected_apps"]   = json.loads(d.get("affected_apps","[]"))
                d["recommendation"]  = json.loads(d.get("recommendation","[]"))
                result.append(d)
            return result
        except Exception as e:
            logger.error(f"DB read error: {e}")
            return []

    def _update_status(self, incident_id: str, status: str):
        con = sqlite3.connect(DB_PATH)
        con.execute("UPDATE incidents SET status=?, updated_at=? WHERE incident_id=?",
                    (status, time.time(), incident_id))
        con.commit()
        con.close()
