"""The mod list file, modlist.json."""

from __future__ import annotations

import dataclasses
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

LIST_VERSION = 1
_TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


class ModListError(Exception):
    pass


@dataclass
class Entry:
    """One file you have (or want), identified by its mod and file group."""

    mod_id: int
    group_id: int
    file_id: int  # the version you have
    mod_name: str
    file_name: str
    version: str
    uploaded: int  # Unix upload time of the version you have
    local_file: str | None = None  # relative to the scanned folder; None if added by URL
    note: str = ""

    @property
    def key(self) -> tuple[int, int]:
        return (self.mod_id, self.group_id)

    @property
    def label(self) -> str:
        if not self.file_name or self.file_name == self.mod_name:
            return self.mod_name or self.file_name
        return f"{self.mod_name} / {self.file_name}"

    def to_json(self) -> dict:
        return {
            "modId": self.mod_id,
            "modName": self.mod_name,
            "groupId": self.group_id,
            "fileId": self.file_id,
            "fileName": self.file_name,
            "version": self.version,
            "uploaded": datetime.fromtimestamp(self.uploaded, timezone.utc).strftime(_TIME_FORMAT),
            "localFile": self.local_file,
            "note": self.note,
        }

    @classmethod
    def from_json(cls, data: dict) -> Entry:
        uploaded = datetime.strptime(data["uploaded"], _TIME_FORMAT).replace(tzinfo=timezone.utc)
        return cls(
            mod_id=int(data["modId"]),
            group_id=int(data["groupId"]),
            file_id=int(data["fileId"]),
            mod_name=data.get("modName", ""),
            file_name=data.get("fileName", ""),
            version=data.get("version", ""),
            uploaded=int(uploaded.timestamp()),
            local_file=data.get("localFile"),
            note=data.get("note", ""),
        )


@dataclass
class MergeResult:
    added: list[Entry] = field(default_factory=list)
    updated: list[tuple[Entry, Entry]] = field(default_factory=list)  # (before, after)
    missing: list[Entry] = field(default_factory=list)


@dataclass
class ModList:
    game: str
    game_id: int
    folder: str | None = None
    entries: list[Entry] = field(default_factory=list)

    def get(self, key: tuple[int, int]) -> Entry | None:
        return next((e for e in self.entries if e.key == key), None)

    def sorted_entries(self) -> list[Entry]:
        return sorted(self.entries, key=lambda e: (e.label.lower(), e.mod_id, e.group_id))

    def merge_scan(self, found: list[Entry]) -> MergeResult:
        """Update the list from a folder scan. The folder decides which version you have.

        Notes are kept. Entries whose archive is no longer in the folder stay listed, with
        their local file cleared; entries added by URL are left alone.
        """
        result = MergeResult()
        found_keys = {e.key for e in found}
        for entry in self.entries:
            if entry.local_file and entry.key not in found_keys:
                entry.local_file = None
                result.missing.append(entry)
        for new in found:
            old = self.get(new.key)
            if old is None:
                self.entries.append(new)
                result.added.append(new)
                continue
            before = dataclasses.replace(old)
            for f in dataclasses.fields(Entry):
                if f.name != "note":
                    setattr(old, f.name, getattr(new, f.name))
            if before.file_id != old.file_id:
                result.updated.append((before, old))
        return result

    def to_json(self) -> dict:
        return {
            "version": LIST_VERSION,
            "game": self.game,
            "gameId": self.game_id,
            "folder": self.folder,
            "entries": [e.to_json() for e in self.sorted_entries()],
        }

    @classmethod
    def from_json(cls, data: dict) -> ModList:
        if data.get("version") != LIST_VERSION:
            raise ModListError(f"unsupported mod list version {data.get('version')!r}")
        return cls(
            game=data["game"],
            game_id=int(data["gameId"]),
            folder=data.get("folder"),
            entries=[Entry.from_json(e) for e in data.get("entries", [])],
        )


def load(path: Path) -> ModList:
    try:
        return ModList.from_json(json.loads(path.read_text(encoding="utf-8")))
    except FileNotFoundError:
        raise
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise ModListError(f"{path} isn't a valid mod list: {e}") from e


def save(modlist: ModList, path: Path) -> None:
    # Write to a temporary file first so a crash never leaves a half-written list.
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(modlist.to_json(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)
