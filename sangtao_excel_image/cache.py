"""Nho lai anh tham chieu da upload, de lan chay sau khong upload lai.

Anh upload len song 7 ngay, nen ban ghi cu hon the bi bo di. Cache luu theo noi
dung file (sha256) chu khong theo duong dan: doi ten file hay chuyen thu muc thi
van dung lai duoc, con sua noi dung anh thi tu dong upload lai.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

# De han 6 ngay thay vi 7, tru hao cho job dang chay va lech gio may chu.
TTL_SECONDS = 6 * 24 * 3600

MAX_ENTRIES = 500


class UploadCache:
    def __init__(self, path: Path):
        self.path = path
        self._entries: dict[str, dict] = {}
        self._dirty = False
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return  # cache hong thi coi nhu chua co, khong lam phien nguoi dung

        if not isinstance(data, dict):
            return

        now = time.time()
        for digest, entry in data.get("uploads", {}).items():
            if not isinstance(entry, dict):
                continue
            url = entry.get("url")
            at = entry.get("at", 0)
            if url and isinstance(at, (int, float)) and now - at < TTL_SECONDS:
                self._entries[digest] = {"url": url, "at": at}

    def get(self, digest: str) -> str | None:
        entry = self._entries.get(digest)
        if not entry:
            return None
        if time.time() - entry["at"] >= TTL_SECONDS:
            self._entries.pop(digest, None)
            self._dirty = True
            return None
        return entry["url"]

    def put(self, digest: str, url: str) -> None:
        self._entries[digest] = {"url": url, "at": time.time()}
        self._dirty = True

    def save(self) -> None:
        if not self._dirty:
            return

        entries = self._entries
        if len(entries) > MAX_ENTRIES:
            newest = sorted(entries.items(), key=lambda kv: kv[1]["at"], reverse=True)
            entries = dict(newest[:MAX_ENTRIES])

        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps({"uploads": entries}, indent=2),
                encoding="utf-8",
            )
            tmp.replace(self.path)
            self._dirty = False
        except OSError:
            pass  # khong luu duoc cache thi cung khong sao, chi cham hon
