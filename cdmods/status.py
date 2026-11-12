"""Decide whether each listed file is up to date."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .modlist import Entry
from .nexus import NexusFile


class State(Enum):
    OUTDATED = "Outdated"
    GONE = "Gone"
    CURRENT = "Up to date"


@dataclass(frozen=True)
class Status:
    entry: Entry
    state: State
    latest: NexusFile | None = None  # newest file the mod offers in the entry's group
    reason: str = ""
    alternatives: tuple[NexusFile, ...] = ()  # what the mod offers instead, when GONE


def latest_in_group(files: list[NexusFile], group_id: int) -> NexusFile | None:
    current = [f for f in files if f.group_id == group_id and f.is_current]
    return max(current, key=lambda f: (f.date, f.file_id), default=None)


def classify(entry: Entry, files: list[NexusFile]) -> Status:
    """files: every file of the entry's mod, as Nexus.mod_files returns them."""
    if not files:
        return Status(entry, State.GONE, reason="mod removed or hidden")
    latest = latest_in_group(files, entry.group_id)
    if latest is None:
        alternatives = tuple(sorted((f for f in files if f.is_current), key=lambda f: (f.category != "MAIN", f.name)))
        return Status(entry, State.GONE, reason="file no longer offered", alternatives=alternatives)
    if latest.file_id != entry.file_id and (latest.date, latest.file_id) > (entry.uploaded, entry.file_id):
        return Status(entry, State.OUTDATED, latest)
    return Status(entry, State.CURRENT, latest)
