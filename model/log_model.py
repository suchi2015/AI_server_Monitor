"""
Core model: Drain3 log parser + DeepLog LSTM anomaly detector.
"""
import os, re, math, shelve, numpy as np
from collections import defaultdict, Counter
from functools import lru_cache
from typing import Optional, List, Tuple
import torch
from torch import nn
from loguru import logger


class LogParser:
    def __init__(self, checkpoint_path=None):
        from drain3.file_persistence import FilePersistence
        from drain3 import TemplateMiner
        persistence = FilePersistence(checkpoint_path) if checkpoint_path else None
        self.miner = TemplateMiner(persistence_handler=persistence)
        self.template_counter = defaultdict(int)

    def add_log(self, line: str) -> int:
        result = self.miner.add_log_message(line)
        cluster_id = result["cluster_id"] - 1
        tmpl = self.get_template_by_id(cluster_id)
        self.template_counter[tmpl] += 1
        return cluster_id

    def get_template_by_id(self, idx: int) -> str:
        templates = [c.get_template() for c in self.miner.drain.clusters]
        return templates[idx] if idx < len(templates) else f"<unknown_{idx}>"

    def get_num_classes(self) -> int:
        return len(list(self.miner.drain.clusters))

    def get_all_templates(self) -> list:
        return [c.get_template() for c in self.miner.drain.clusters]


class DeepLogNet(nn.Module):
    def __init__(self, num_keys, hidden_size=64, num_layers=2):
        super().__init__()
        self.lstm = nn.LSTM(1, hidden_size, num_layers, batch_first=True)
        self.fc   = nn.Linear(hidden_size, num_keys)

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :])


class LogModel:
    LOG_PATTERN = re.compile(
        r"(?P<timestamp>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}[^\s]*)?\s*"
        r"(?P<severity>DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL|FATAL)?\s*"
        r"(?P<app>[\w\-\.]+)?[:\s]+(?P<message>.+)",
        re.IGNORECASE,
    )
    SEV = {"DEBUG":0,"INFO":1,"WARNING":2,"WARN":2,"ERROR":3,"CRITICAL":4,"FATAL":4}

    def __init__(self, window_size=10, num_candidates=9, hidden_size=64,
                 num_layers=2, checkpoint_path=None, drain_checkpoint=None):
        self.window_size    = window_size
        self.num_candidates = num_candidates
        self.hidden_size    = hidden_size
        self.num_layers     = num_layers
        self.parser         = LogParser(drain_checkpoint)
        self.sequence: List[int] = []
        self.model          = None
        self.num_classes    = 0
        self.is_trained     = False
        if checkpoint_path and os.path.exists(checkpoint_path):
            self.load(checkpoint_path)

    def parse_line(self, line: str) -> dict:
        m = self.LOG_PATTERN.match(line.strip())
        if m:
            return {
                "timestamp": m.group("timestamp") or "",
                "severity":  (m.group("severity") or "INFO").upper(),
                "app":       m.group("app") or "unknown",
                "message":   m.group("message") or line.strip(),
                "raw":       line.strip(),
            }
        return {"timestamp":"","severity":"INFO","app":"unknown",
                "message":line.strip(),"raw":line.strip()}

    def train_on_logs(self, log_lines: List[str], epochs=50, lr=0.001):
        logger.info(f"Training on {len(log_lines)} lines...")
        all_ids = [self.parser.add_log(l) for l in log_lines]
        self.num_classes = max(self.parser.get_num_classes(), 10)
        X, Y = [], []
        for i in range(len(all_ids) - self.window_size):
            X.append(all_ids[i:i+self.window_size])
            Y.append(all_ids[i+self.window_size])
        if not X:
            logger.warning("Not enough log lines.")
            return
        self.model = DeepLogNet(self.num_classes, self.hidden_size, self.num_layers)
        opt = torch.optim.Adam(self.model.parameters(), lr=lr)
        criterion = nn.CrossEntropyLoss()
        Xt = torch.tensor(X, dtype=torch.float).unsqueeze(-1)
        Yt = torch.clamp(torch.tensor(Y, dtype=torch.long), 0, self.num_classes-1)
        self.model.train()
        for ep in range(epochs):
            opt.zero_grad()
            loss = criterion(self.model(Xt), Yt)
            loss.backward()
            opt.step()
            if (ep+1) % 10 == 0:
                logger.info(f"  epoch {ep+1}/{epochs}  loss={loss.item():.4f}")
        self.is_trained = True
        logger.info("Training complete.")

    def ingest_line(self, line: str) -> dict:
        parsed = self.parse_line(line)
        tid    = self.parser.add_log(line)
        self.sequence.append(tid)
        result = {**parsed, "template_id": tid,
                  "template": self.parser.get_template_by_id(tid),
                  "is_anomaly": False, "anomaly_score": 0.0, "explanation": ""}
        sw = self.SEV.get(parsed["severity"], 0)
        if sw >= 3:
            result["is_anomaly"]    = True
            result["anomaly_score"] = 0.7 + (sw-3)*0.15
            result["explanation"]   = (
                f"{parsed['severity']} in [{parsed['app']}]: {parsed['message'][:120]}")
        if self.is_trained and len(self.sequence) >= self.window_size+1:
            window = self.sequence[-(self.window_size+1):-1]
            score, bad = self._predict_anomaly(window, tid)
            if bad:
                result["is_anomaly"]    = True
                result["anomaly_score"] = max(result["anomaly_score"], score)
                result["explanation"]   = (
                    f"Unusual log sequence in [{parsed['app']}]. "
                    f"Template \"{result['template'][:60]}\" was unexpected. "
                    f"Score={score:.2f}. " + result["explanation"])
        return result

    def _predict_anomaly(self, window, actual_next):
        self.model.eval()
        with torch.no_grad():
            x     = torch.tensor(window, dtype=torch.float).unsqueeze(0).unsqueeze(-1)
            probs = torch.softmax(self.model(x), dim=1)[0]
            top_k = torch.argsort(probs, descending=True)[:self.num_candidates].tolist()
            bad   = actual_next not in top_k
            actual_c = min(actual_next, self.num_classes-1)
            score = float(1.0 - probs[actual_c].item())
        return score, bad

    def save(self, path: str):
        if self.model is None:
            return
        torch.save({"state_dict":self.model.state_dict(),"num_classes":self.num_classes,
                    "window_size":self.window_size,"hidden_size":self.hidden_size,
                    "num_layers":self.num_layers}, path)
        logger.info(f"Saved to {path}")

    def load(self, path: str):
        ck = torch.load(path, map_location="cpu")
        self.num_classes = ck["num_classes"]
        self.window_size = ck.get("window_size", self.window_size)
        self.hidden_size = ck.get("hidden_size", self.hidden_size)
        self.num_layers  = ck.get("num_layers",  self.num_layers)
        self.model = DeepLogNet(self.num_classes, self.hidden_size, self.num_layers)
        self.model.load_state_dict(ck["state_dict"])
        self.model.eval()
        self.is_trained = True
        logger.info(f"Loaded from {path}")
