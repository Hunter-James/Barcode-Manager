"""Persistent scan/generate history (JSON file in %APPDATA%)."""

from __future__ import annotations

import dataclasses
import json
import os
import time
from pathlib import Path


def _appdata_dir() -> Path:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    p = Path(base) / "BarcodeManager"
    p.mkdir(parents=True, exist_ok=True)
    return p


def snapshots_dir() -> Path:
    """Directory where per-scan annotated snapshots live."""
    p = _appdata_dir() / "snapshots"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _snapshot_path_for(group_id: str) -> Path | None:
    if not group_id:
        return None
    return snapshots_dir() / f"{group_id}.png"


@dataclasses.dataclass
class HistoryEntry:
    text: str
    format: str
    source: str  # 'snip' | 'file' | 'camera' | 'create'
    timestamp: float = dataclasses.field(default_factory=time.time)
    engine: str = ""
    # ``group_id`` is a uuid shared by every entry produced by a single
    # multi-code scan. Empty string means "standalone" (one code or
    # came from camera / create). ``group_size`` is the total number of
    # entries in that group — denormalised onto each row so the View
    # can show a "N codes" header without rescanning the whole list.
    group_id: str = ""
    group_size: int = 1

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "HistoryEntry":
        return cls(
            text=d.get("text", ""),
            format=d.get("format", ""),
            source=d.get("source", ""),
            timestamp=float(d.get("timestamp", time.time())),
            engine=d.get("engine", ""),
            group_id=d.get("group_id", ""),
            group_size=int(d.get("group_size", 1)),
        )


class HistoryStore:
    MAX_ENTRIES = 500

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (_appdata_dir() / "history.json")
        self._entries: list[HistoryEntry] = []
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            self._entries = []
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self._entries = [HistoryEntry.from_dict(d) for d in raw]
        except (OSError, ValueError):
            self._entries = []

    def save(self) -> None:
        data = [e.to_dict() for e in self._entries]
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def add(self, entry: HistoryEntry) -> None:
        # de-dup against the most recent identical entry within 5s window
        if self._entries:
            last = self._entries[0]
            if (
                last.text == entry.text
                and last.format == entry.format
                and entry.timestamp - last.timestamp < 5
            ):
                return
        self._entries.insert(0, entry)
        if len(self._entries) > self.MAX_ENTRIES:
            dropped = self._entries[self.MAX_ENTRIES:]
            self._entries = self._entries[: self.MAX_ENTRIES]
            # Drop snapshot files for groups whose every entry has fallen
            # off the tail.
            remaining_groups = {e.group_id for e in self._entries if e.group_id}
            for e in dropped:
                if e.group_id and e.group_id not in remaining_groups:
                    path = _snapshot_path_for(e.group_id)
                    if path is not None:
                        try:
                            path.unlink()
                        except OSError:
                            pass
        self.save()

    def clear(self) -> None:
        self._entries = []
        self.save()
        # Wipe snapshot directory too — orphaned snapshots are useless
        # and just waste disk space.
        snap_dir = snapshots_dir()
        for f in snap_dir.glob("*.png"):
            try:
                f.unlink()
            except OSError:
                pass

    def all(self) -> list[HistoryEntry]:
        return list(self._entries)
