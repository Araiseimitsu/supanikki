import json
import os
import threading
import time
from datetime import datetime
from typing import List, Dict, Optional

import config

QUEUE_FILE = os.path.join(config.BASE_DIR, "offline_queue.json")

class OfflineQueue:
    def __init__(self):
        self._lock = threading.Lock()
        self._queue: List[Dict] = self._load_queue()

    def _load_queue(self) -> List[Dict]:
        if not os.path.exists(QUEUE_FILE):
            return []
        try:
            with open(QUEUE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load offline queue: {e}")
            return []

    def _save_queue(self):
        try:
            with open(QUEUE_FILE, "w", encoding="utf-8") as f:
                json.dump(self._queue, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to save offline queue: {e}")

    def add(self, text: str, timestamp: str = None):
        if timestamp is None:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
        entry = {
            "text": text,
            "timestamp": timestamp,
            "added_at": time.time()
        }
        with self._lock:
            self._queue.append(entry)
            self._save_queue()
        print(f"Added to offline queue: {text[:20]}...")

    def peek(self) -> Optional[Dict]:
        with self._lock:
            return self._queue[0] if self._queue else None

    def pop(self) -> Optional[Dict]:
        with self._lock:
            if not self._queue:
                return None
            item = self._queue.pop(0)
            self._save_queue()
            return item

    def is_empty(self) -> bool:
        with self._lock:
            return len(self._queue) == 0

    def get_all(self) -> List[Dict]:
        with self._lock:
            return list(self._queue)
