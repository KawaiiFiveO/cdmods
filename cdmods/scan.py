"""Identify the archives in a folder as Nexus files."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .filenames import ParsedName, is_archive, parse_candidates
from .modlist import Entry
from .nexus import Nexus, NexusFile


@dataclass
class ScanResult:
    archives: int = 0
    found: list[Entry] = field(default_factory=list)  # newest local file per group
    older_copies: list[tuple[str, Entry]] = field(default_factory=list)  # (file, the newer entry kept)
    unidentified: list[str] = field(default_factory=list)


def list_archives(folder: Path, recursive: bool = False) -> list[Path]:
    paths = folder.rglob("*") if recursive else folder.iterdir()
    return sorted(p for p in paths if p.is_file() and is_archive(p.name))


def match(name: ParsedName, files: list[NexusFile]) -> NexusFile | None:
    if name.sqid:
        return next((f for f in files if f.sqid == name.sqid), None)
    return next((f for f in files if f.date == name.uploaded), None)


def scan(folder: Path, nexus: Nexus, recursive: bool = False) -> ScanResult:
    archives = list_archives(folder, recursive)
    result = ScanResult(archives=len(archives))
    pending = {path: parse_candidates(path.name) for path in archives}
    matched: dict[Path, NexusFile] = {}
    files_by_mod: dict[int, list[NexusFile]] = {}

    # Try every archive's most likely reading first, then fall back to the next reading
    # for the ones that didn't match, fetching each mod's file list only once.
    attempt = 0
    while wanted := {c[attempt].mod_id for c in pending.values() if attempt < len(c)}:
        files_by_mod.update(nexus.mod_files(wanted - files_by_mod.keys()))
        for path, candidates in list(pending.items()):
            if attempt < len(candidates) and (f := match(candidates[attempt], files_by_mod.get(candidates[attempt].mod_id, []))):
                matched[path] = f
                del pending[path]
        attempt += 1
    result.unidentified = sorted(_relative(p, folder) for p in pending)

    mods = nexus.mods({f.mod_id for f in matched.values()}) if matched else {}
    newest: dict[tuple[int, int], tuple[Path, NexusFile]] = {}
    older: list[tuple[Path, tuple[int, int]]] = []
    for path, f in sorted(matched.items(), key=lambda item: (item[1].date, item[1].file_id)):
        key = (f.mod_id, f.group_id)
        if key in newest:
            older.append((newest[key][0], key))
        newest[key] = (path, f)

    entries: dict[tuple[int, int], Entry] = {}
    for key, (path, f) in newest.items():
        mod = mods.get(f.mod_id)
        entries[key] = Entry(
            mod_id=f.mod_id,
            group_id=f.group_id,
            file_id=f.file_id,
            mod_name=mod.name if mod else f.name,
            file_name=f.name,
            version=f.version,
            uploaded=f.date,
            local_file=_relative(path, folder),
        )
    result.found = list(entries.values())
    result.older_copies = sorted(((_relative(p, folder), entries[key]) for p, key in older), key=lambda item: item[0])
    return result


def _relative(path: Path, folder: Path) -> str:
    return path.relative_to(folder).as_posix()
