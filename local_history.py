import json
import os
import threading
from typing import List, Dict

import config

HISTORY_FILE = os.path.join(config.BASE_DIR, "local_history.json")
MAX_HISTORY = 10

class LocalHistory:
    def __init__(self):
        self._lock = threading.Lock()
        self._history: List[str] = self._load_history()

    def _load_history(self) -> List[str]:
        if not os.path.exists(HISTORY_FILE):
            return []
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load local history: {e}")
            return []

    def _save_history(self):
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(self._history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to save local history: {e}")

    def add(self, text: str):
        if not text:
            return
        
        with self._lock:
            # 重複排除（直近と同じなら追加しない）
            if self._history and self._history[0] == text:
                return
            
            self._history.insert(0, text)
            if len(self._history) > MAX_HISTORY:
                self._history = self._history[:MAX_HISTORY]
            self._save_history()

    def get_latest(self, count: int = 5) -> List[str]:
        with self._lock:
            return self._history[:count]

    def clear(self):
        with self._lock:
            self._history = []
            self._save_history()
