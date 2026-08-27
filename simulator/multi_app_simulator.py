"""
Multi-App Simulator — generates realistic logs for:
  - food-app
  - servicenow-monitor
  - confluence-chatbot
"""
import random, time, datetime, threading

APP_TEMPLATES = {
    "food-app": [
        ("INFO",     "GET /api/menu 200 {ms}ms"),
        ("INFO",     "POST /api/orders 201 {ms}ms - Order {oid} created"),
        ("INFO",     "GET /api/restaurants 200 {ms}ms"),
        ("WARNING",  "POST /api/payment slow response {ms}ms"),
        ("ERROR",    "POST /api/orders 500 - Database connection failed"),
        ("ERROR",    "GET /api/menu 404 - Restaurant {rid} not found"),
        ("CRITICAL", "Payment service DOWN - all transactions failing"),
        ("WARNING",  "High memory usage in order processing service"),
        ("ERROR",    "Failed to connect to MongoDB: connection timeout"),
    ],
    "servicenow-monitor": [
        ("INFO",     "Polling ServiceNow incidents - found {n} new"),
        ("INFO",     "Ticket INC{tid} status updated to In Progress"),
        ("INFO",     "Auto-assigned ticket INC{tid} to team DevOps"),
        ("WARNING",  "ServiceNow API rate limit approaching: {n}/500"),
        ("ERROR",    "ServiceNow API authentication failed - token expired"),
        ("ERROR",    "Failed to update ticket INC{tid}: 500 Internal Server Error"),
        ("CRITICAL", "ServiceNow connection lost - 3 retries exhausted"),
        ("WARNING",  "Slow response from ServiceNow API: {ms}ms"),
    ],
    "confluence-chatbot": [
        ("INFO",     "User query processed: '{q}' - 200ms"),
        ("INFO",     "Fetched {n} pages from Confluence space DEVOPS"),
        ("INFO",     "Vector embeddings updated - {n} documents indexed"),
        ("WARNING",  "Low confidence response for query '{q}' score=0.42"),
        ("ERROR",    "Confluence API error: 403 Forbidden - check permissions"),
        ("ERROR",    "Embedding model timeout after 30s"),
        ("CRITICAL", "Vector DB connection failed - chatbot unavailable"),
        ("WARNING",  "Context window limit reached - truncating document"),
    ],
}

QUERIES = ["how to deploy", "reset password", "api documentation",
           "incident workflow", "deployment guide"]
ORDER_IDS = ["ORD-1234", "ORD-5678", "ORD-9012"]
RESTAURANT_IDS = ["R001", "R002", "R003"]
TICKET_IDS = ["0012345", "0067890", "0054321"]

def _fill(tmpl: str) -> str:
    return (tmpl
        .replace("{ms}",  str(random.randint(50, 8000)))
        .replace("{oid}",  random.choice(ORDER_IDS))
        .replace("{rid}",  random.choice(RESTAURANT_IDS))
        .replace("{tid}",  random.choice(TICKET_IDS))
        .replace("{n}",    str(random.randint(1, 50)))
        .replace("{q}",    random.choice(QUERIES)))

def generate_app_log(app_name: str, force_anomaly=False) -> dict:
    templates = APP_TEMPLATES.get(app_name, APP_TEMPLATES["food-app"])
    if force_anomaly:
        choices = [(s, t) for s, t in templates if s in ("ERROR","CRITICAL","WARNING")]
        severity, tmpl = random.choice(choices or templates)
    else:
        weights = [{"INFO":65,"WARNING":20,"ERROR":10,"CRITICAL":5}.get(s,5) for s,_ in templates]
        severity, tmpl = random.choices(templates, weights=weights, k=1)[0]
    msg = _fill(tmpl)
    ts  = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return {
        "raw":       f"{ts} {severity} {app_name}: {msg}",
        "app":       app_name,
        "severity":  severity,
        "message":   msg,
        "timestamp": ts,
    }

def generate_metrics(spike=False) -> dict:
    cpu  = min(100, round(random.gauss(40, 12) + (random.uniform(35, 55) if spike else 0), 1))
    ram  = min(100, round(random.gauss(58, 8)  + (random.uniform(20, 35) if spike else 0), 1))
    disk = min(100, round(random.gauss(45, 5), 1))
    return {
        "cpu_percent":  cpu,
        "ram_percent":  ram,
        "disk_percent": disk,
        "net_sent_mb":  round(random.uniform(0.1, 8.0), 2),
        "net_recv_mb":  round(random.uniform(0.1, 15.0), 2),
        "timestamp":    datetime.datetime.now().isoformat(),
    }


class MultiAppSimulator:
    def __init__(self, log_callback, metrics_callback,
                 app_names: list,
                 lines_per_second=2.0, anomaly_probability=0.08):
        self.log_cb    = log_callback
        self.met_cb    = metrics_callback
        self.apps      = app_names
        self.lps       = lines_per_second
        self.anom_prob = anomaly_probability
        self._stop     = threading.Event()

    def start(self):
        self._stop.clear()
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        self._stop.set()

    def _run(self):
        counter = 0
        while not self._stop.is_set():
            spike    = random.random() < self.anom_prob
            app_name = random.choice(self.apps)
            entry    = generate_app_log(app_name, force_anomaly=spike)
            self.log_cb(entry)
            counter += 1
            if counter % 4 == 0:
                self.met_cb(generate_metrics(spike=spike))
            time.sleep(1.0 / self.lps)
