from collections import deque
import threading

class AppState:
    def __init__(self):
        self.lock          = threading.Lock()
        self.logs          = deque(maxlen=2000)
        self.anomalies     = deque(maxlen=500)
        self.metrics       = deque(maxlen=300)
        self.alerts        = deque(maxlen=500)
        self.app_stats     = {}   # app_name -> stats dict
        self.model         = None
        self.incident_mgr  = None
        self.training_done = False

state = AppState()
