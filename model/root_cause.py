"""
Root Cause Engine:
- Pattern matching against known failure signatures
- No LLM — pure deterministic rules based on incident patterns,
  affected apps, log templates, and metric values
"""
from typing import Optional


# ── Knowledge base of failure signatures ──────────────────────────────────────
# Each entry: (match_fn, root_cause_str)
# match_fn receives the incident dict and returns True if it matches

SIGNATURES = [

    # ── Memory / OOM ──────────────────────────────────────────────────────────
    (
        lambda inc: _has_keyword(inc, ["OutOfMemory","heap space","OOM","Kill process",
                                        "Cannot allocate memory"]),
        "Memory exhaustion: application or OS ran out of available memory. "
        "Likely causes: memory leak, insufficient RAM for workload, or sudden traffic spike."
    ),

    # ── Connection pool / DB ──────────────────────────────────────────────────
    (
        lambda inc: _has_keyword(inc, ["too many connections","connection pool",
                                        "Connection refused","FATAL:.*connect"]),
        "Database connection pool exhausted: too many concurrent clients. "
        "Likely causes: connection leak in application code, or DB max_connections too low."
    ),

    # ── Disk full ────────────────────────────────────────────────────────────
    (
        lambda inc: _has_keyword(inc, ["No space left","disk full","EXT4-fs error",
                                        "pg_wal","ENOSPC"]),
        "Disk space exhaustion: filesystem is full or nearly full. "
        "Likely causes: log files not rotated, database WAL accumulation, or insufficient disk."
    ),

    # ── Redis / Cache ─────────────────────────────────────────────────────────
    (
        lambda inc: _has_keyword(inc, ["Redis","MISCONF","maxmemory","RDB file",
                                        "READONLY"]),
        "Cache layer failure: Redis is misconfigured or out of memory. "
        "Likely causes: maxmemory limit hit, persistence config error, or Redis crash."
    ),

    # ── High CPU ──────────────────────────────────────────────────────────────
    (
        lambda inc: _metric_above(inc, "CPU", 85),
        "High CPU utilization: server is CPU-bound. "
        "Likely causes: infinite loop, heavy computation, traffic surge, or runaway process."
    ),

    # ── High RAM ──────────────────────────────────────────────────────────────
    (
        lambda inc: _metric_above(inc, "RAM", 88),
        "High RAM utilization: server memory pressure detected. "
        "Likely causes: memory leak, too many processes, or insufficient instance size."
    ),

    # ── Slow query / DB performance ──────────────────────────────────────────
    (
        lambda inc: _has_keyword(inc, ["slow query","query time","lock wait",
                                        "deadlock","timeout"]),
        "Database performance degradation: slow or locked queries detected. "
        "Likely causes: missing indexes, N+1 query problem, table lock contention, or large dataset scan."
    ),

    # ── Network / upstream ────────────────────────────────────────────────────
    (
        lambda inc: _has_keyword(inc, ["upstream","Connection timed out","502","504",
                                        "connect() failed","ECONNREFUSED"]),
        "Network/upstream failure: downstream service or proxy cannot reach upstream. "
        "Likely causes: upstream service down, firewall rule, or network partition."
    ),

    # ── Auth / permission ─────────────────────────────────────────────────────
    (
        lambda inc: _has_keyword(inc, ["403","401","permission denied","Access denied",
                                        "authentication failed"]),
        "Authentication/authorization failure: requests being rejected. "
        "Likely causes: expired credentials, misconfigured permissions, or security policy change."
    ),

    # ── Cascade (multi-app) ──────────────────────────────────────────────────
    (
        lambda inc: inc.get("pattern") == "cascade" and len(inc.get("affected_apps",[])) >= 3,
        "Service cascade failure: multiple services failing simultaneously. "
        "Likely causes: shared dependency (DB/cache) is down, or network-level issue affecting all services."
    ),

    # ── Burst / repeated error ────────────────────────────────────────────────
    (
        lambda inc: inc.get("pattern") == "burst",
        "Repeated error burst: same failure occurring rapidly in a loop. "
        "Likely causes: retry storm, misconfiguration causing immediate re-failure, or external dependency unavailable."
    ),
]


def analyze(incident: dict) -> str:
    """
    Returns root cause string for the given incident.
    Tries each signature in order, returns first match.
    Falls back to generic message.
    """
    for match_fn, cause in SIGNATURES:
        try:
            if match_fn(incident):
                return cause
        except Exception:
            continue
    return ("Unknown root cause. Review the correlated events and metrics "
            "in the incident timeline for manual investigation.")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _has_keyword(incident: dict, keywords: list) -> bool:
    """Check if any event message/template in incident contains any keyword."""
    import re
    events = incident.get("events", [])
    for event in events:
        text = " ".join([
            str(event.get("message", "")),
            str(event.get("template", "")),
            str(event.get("raw", "")),
            str(event.get("explanation", "")),
        ]).lower()
        for kw in keywords:
            if re.search(kw.lower(), text):
                return True
    return False


def _metric_above(incident: dict, metric: str, threshold: float) -> bool:
    """Check if any threshold alert event in incident has metric above threshold."""
    events = incident.get("events", [])
    for event in events:
        if (event.get("type") == "threshold"
                and event.get("metric", "").upper() == metric.upper()
                and float(event.get("value", 0)) >= threshold):
            return True
    return False
