"""Recognize the names Nexus Mods gives downloaded archives.

Nexus has used two formats:

  Older:    "Better Custom Markers-203-1-7-1778420608.zip"
            name-modId-version-uploadTime, with the version's dots turned into dashes.
  Current:  "Better Inventory and Trade UI 452 3.1 2026-09-07T20-00Z g7OwxhwXd.zip"
            name modId version uploadTime sqid. The sqid identifies the file exactly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

ARCHIVE_EXTENSIONS = (".zip", ".7z", ".rar")

_CURRENT = re.compile(
    r"^(?P<name>.+) (?P<mod_id>\d+) (?P<version>\S+) "
    r"(?P<date>\d{4}-\d{2}-\d{2}T\d{2}-\d{2}Z) (?P<sqid>[A-Za-z0-9]+)$",
    re.ASCII,
)
_NUMBER = re.compile(r"^\d+$", re.ASCII)
_TIMESTAMP = re.compile(r"^\d{9,11}$", re.ASCII)
# Browsers add " (1)" when the same file is downloaded twice.
_DUPLICATE_SUFFIX = re.compile(r" \(\d+\)$")


@dataclass(frozen=True)
class ParsedName:
    filename: str
    name: str
    mod_id: int
    version: str
    uploaded: int  # Unix time; only to the minute in the current format
    sqid: str | None = None


def is_archive(filename: str) -> bool:
    return filename.lower().endswith(ARCHIVE_EXTENSIONS)


def parse_candidates(filename: str) -> list[ParsedName]:
    """Possible readings of an archive name, most likely first. Empty if it isn't a Nexus name."""
    if not is_archive(filename):
        return []
    stem = _DUPLICATE_SUFFIX.sub("", filename.rsplit(".", 1)[0])
    if m := _CURRENT.match(stem):
        uploaded = datetime.strptime(m["date"], "%Y-%m-%dT%H-%MZ").replace(tzinfo=timezone.utc)
        return [ParsedName(filename, m["name"], int(m["mod_id"]), m["version"], int(uploaded.timestamp()), m["sqid"])]
    return _older_candidates(filename, stem)


def _older_candidates(filename: str, stem: str) -> list[ParsedName]:
    parts = stem.split("-")
    if len(parts) < 3 or not _TIMESTAMP.match(parts[-1]):
        return []
    uploaded = int(parts[-1])
    # The name can itself contain "-12", so any number before the timestamp could be the
    # mod ID. Prefer readings whose version is all numbers, then the shortest name.
    readings = []
    for i in range(1, len(parts) - 1):
        name, version = "-".join(parts[:i]), parts[i + 1 : -1]
        if not name or not _NUMBER.match(parts[i]):
            continue
        rank = 2 if not version else 0 if all(_NUMBER.match(p) for p in version) else 1
        readings.append((rank, i, ParsedName(filename, name, int(parts[i]), ".".join(version), uploaded)))
    return [reading for *_, reading in sorted(readings, key=lambda r: r[:2])]
