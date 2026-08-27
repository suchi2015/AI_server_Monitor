"""
Correlation Engine:
- Groups related anomalies/alerts into a single Incident
- Uses time-window (60s default) to correlate events
- Detects burst patterns (same error N times in T seconds)
"""
import time
from collections import defaultdict, deque
from typing import List, Dict, Optional
from loguru import logger


class CorrelationEngine:
    def __init__(self, time_window=60, burst_threshold=3):
        """
        time_window     : seconds to look back when correlating events
        burst_threshold : same template N times in window = burst
        """
        self.time_window     = time_window
        self.burst_threshold = burst_threshold

        # sliding window of recent events: deque of dicts
        self._events: deque = deque(maxlen=500)

        # active incidents: incident_id -> incident dict
        self.incidents: Dict[str, dict] = {}
        self._incident_counter = 0

    # ── public API ────────────────────────────────────────────────────────────

    def add_event(self, event: dict) -> Optional[dict]:
        """
        Feed one anomaly/alert event.
        Returns an Incident dict if a new or updated incident is formed,
        else returns None.
        """
        event["_ts"] = time.time()
        self._events.append(event)
        self._expire_old_events()

        incident = self._correlate(event)
        return incident

    def get_active_incidents(self) -> List[dict]:
        return list(self.incidents.values())

    # ── internals ─────────────────────────────────────────────────────────────

    def _expire_old_events(self):
        cutoff = time.time() - self.time_window
        while self._events and self._events[0]["_ts"] < cutoff:
            self._events.popleft()

    def _correlate(self, event: dict) -> Optional[dict]:
        now = time.time()
        window_events = [e for e in self._events
                         if now - e["_ts"] <= self.time_window]

        # ── 1. Burst detection: same template repeated >= burst_threshold
        tmpl = event.get("template", "")
        app  = event.get("app", "unknown")
        if tmpl:
            same = [e for e in window_events if e.get("template") == tmpl]
            if len(same) >= self.burst_threshold:
                return self._make_or_update_incident(
                    trigger_event=event,
                    related_events=same,
                    pattern="burst",
                    summary=f"Burst: '{tmpl[:60]}' repeated {len(same)}x in {self.time_window}s",
                )

        # ── 2. Multi-app cascade: anomalies in 2+ different apps in window
        anomaly_events = [e for e in window_events if e.get("is_anomaly")]
        affected_apps  = list({e.get("app","?") for e in anomaly_events})
        if len(affected_apps) >= 2:
            return self._make_or_update_incident(
                trigger_event=event,
                related_events=anomaly_events,
                pattern="cascade",
                summary=f"Cascade across {len(affected_apps)} apps: {', '.join(affected_apps[:4])}",
            )

        # ── 3. Metrics + log correlation: threshold alert + log error together
        has_metric_alert = any(e.get("type") == "threshold" for e in window_events)
        has_log_error    = any(e.get("severity") in ("ERROR","CRITICAL","FATAL")
                               for e in window_events)
        if has_metric_alert and has_log_error:
            combined = [e for e in window_events
                        if e.get("type") == "threshold"
                        or e.get("severity") in ("ERROR","CRITICAL","FATAL")]
            return self._make_or_update_incident(
                trigger_event=event,
                related_events=combined,
                pattern="resource_and_error",
                summary=f"Resource spike + application errors in [{app}]",
            )

        return None

    def _make_or_update_incident(self, trigger_event, related_events,
                                  pattern, summary) -> dict:
        # Check if an incident with same pattern + overlapping apps exists
        apps = list({e.get("app","?") for e in related_events})
        for inc_id, inc in self.incidents.items():
            if inc["pattern"] == pattern and set(inc["affected_apps"]) & set(apps):
                # update existing
                inc["event_count"]    = len(related_events)
                inc["affected_apps"]  = list(set(inc["affected_apps"]) | set(apps))
                inc["summary"]        = summary
                inc["updated_at"]     = time.time()
                inc["events"]         = related_events[-10:]  # keep last 10
                logger.info(f"Incident updated [{inc_id}]: {summary}")
                return inc

        # new incident
        self._incident_counter += 1
        inc_id = f"INC-{self._incident_counter:04d}"
        incident = {
            "incident_id":   inc_id,
            "pattern":       pattern,
            "summary":       summary,
            "affected_apps": apps,
            "event_count":   len(related_events),
            "severity":      self._calc_severity(related_events),
            "created_at":    time.time(),
            "updated_at":    time.time(),
            "events":        related_events[-10:],
            "status":        "open",
            "root_cause":    None,
            "recommendation": None,
        }
        self.incidents[inc_id] = incident
        logger.warning(f"New incident [{inc_id}] pattern={pattern}: {summary}")
        return incident

    def _calc_severity(self, events: list) -> str:
        sevs = [e.get("severity","INFO") for e in events]
        if "CRITICAL" in sevs or "FATAL" in sevs: return "CRITICAL"
        if "ERROR" in sevs:                        return "HIGH"
        if "WARNING" in sevs:                      return "MEDIUM"
        return "LOW"

    def close_incident(self, incident_id: str):
        if incident_id in self.incidents:
            self.incidents[incident_id]["status"] = "resolved"
            logger.info(f"Incident {incident_id} resolved")
