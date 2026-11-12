"""A small client for the public Nexus Mods GraphQL API. Reading needs no API key."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

from . import __version__

API_URL = "https://api.nexusmods.com/v2/graphql"
# Requests without a User-Agent are refused with HTTP 403.
USER_AGENT = f"cdmods/{__version__}"
# Files a mod currently offers. The other categories (OLD_VERSION, ARCHIVED, REMOVED)
# are superseded.
CURRENT_CATEGORIES = frozenset({"MAIN", "UPDATE", "OPTIONAL", "MISCELLANEOUS"})
# legacyModsByDomain returns at most 20 mods per request.
BATCH_SIZE = 20

_FILE_FIELDS = "fileId groupId name version category date sqid"
_MOD_URL = re.compile(r"nexusmods\.com/(?:games/)?(?P<game>[\w-]+)/mods/(?P<mod_id>\d+)", re.IGNORECASE | re.ASCII)


@dataclass(frozen=True)
class NexusFile:
    mod_id: int
    file_id: int
    group_id: int  # shared by every version of the same file, even across renames
    name: str
    version: str
    category: str
    date: int  # Unix upload time
    sqid: str

    @property
    def is_current(self) -> bool:
        return self.category in CURRENT_CATEGORIES


@dataclass(frozen=True)
class NexusMod:
    mod_id: int
    name: str
    status: str


class NexusError(Exception):
    pass


Transport = Callable[[dict], dict]


def http_transport(payload: dict) -> dict:
    request = urllib.request.Request(
        API_URL,
        json.dumps(payload).encode(),
        {"Content-Type": "application/json", "User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as e:
        raise NexusError(f"Nexus returned HTTP {e.code}") from e
    except OSError as e:
        raise NexusError(f"could not reach Nexus: {getattr(e, 'reason', e)}") from e
    except ValueError as e:
        raise NexusError("Nexus sent a response that isn't JSON") from e


class Nexus:
    def __init__(self, game: str, transport: Transport = http_transport):
        self.game = game
        self._transport = transport
        self._game_id: int | None = None

    def query(self, query: str, variables: dict | None = None) -> dict:
        response = self._transport({"query": query, "variables": variables or {}})
        if response.get("errors"):
            raise NexusError("; ".join(e.get("message", "unknown error") for e in response["errors"]))
        return response["data"]

    def game_id(self) -> int:
        if self._game_id is None:
            data = self.query(f"{{ game(domainName: {json.dumps(self.game)}) {{ id }} }}")
            self._game_id = int(data["game"]["id"])
        return self._game_id

    def mod_files(self, mod_ids: Iterable[int]) -> dict[int, list[NexusFile]]:
        """Every file of each mod, oldest first. A missing or hidden mod gets an empty list."""
        game_id = self.game_id()
        result = {}
        for batch in _batches(mod_ids):
            aliases = " ".join(f"m{m}: modFiles(modId: {m}, gameId: {game_id}) {{ {_FILE_FIELDS} }}" for m in batch)
            data = self.query(f"{{ {aliases} }}")
            for m in batch:
                files = [_file(m, f) for f in data.get(f"m{m}") or []]
                result[m] = sorted(files, key=lambda f: (f.date, f.file_id))
        return result

    def mods(self, mod_ids: Iterable[int]) -> dict[int, NexusMod]:
        """Mod details by ID. Missing or hidden mods are left out."""
        result = {}
        for batch in _batches(mod_ids):
            data = self.query(
                "query($ids: [CompositeDomainWithIdInput!]!) {"
                " legacyModsByDomain(ids: $ids) { nodes { modId name status } } }",
                {"ids": [{"gameDomain": self.game, "modId": m} for m in batch]},
            )
            for node in data["legacyModsByDomain"]["nodes"]:
                mod_id = int(node["modId"])
                result[mod_id] = NexusMod(mod_id, node["name"] or "", node["status"] or "")
        return result


def _file(mod_id: int, data: dict) -> NexusFile:
    file_id = int(data["fileId"])
    return NexusFile(
        mod_id=mod_id,
        file_id=file_id,
        # A file without a group is its own group; negative so it can't clash with a real one.
        group_id=int(data["groupId"] or -file_id),
        name=data["name"] or "",
        version=data["version"] or "",
        category=data["category"] or "",
        date=int(data["date"]),
        sqid=data["sqid"] or "",
    )


def _batches(mod_ids: Iterable[int]) -> Iterator[list[int]]:
    ids = sorted({int(m) for m in mod_ids})
    for start in range(0, len(ids), BATCH_SIZE):
        yield ids[start : start + BATCH_SIZE]


def mod_url(game: str, mod_id: int) -> str:
    return f"https://www.nexusmods.com/{game}/mods/{mod_id}?tab=files"


def file_url(game: str, mod_id: int, file_id: int) -> str:
    return f"https://www.nexusmods.com/{game}/mods/{mod_id}?tab=files&file_id={file_id}"


def parse_url(url: str) -> tuple[str, int, int | None]:
    """(game, mod ID, file ID or None) from a Nexus mod or file URL."""
    m = _MOD_URL.search(url)
    if not m:
        raise ValueError(f"not a Nexus Mods mod URL: {url}")
    file_ids = parse_qs(urlparse(url).query).get("file_id", [])
    file_id = int(file_ids[0]) if file_ids and file_ids[0].isascii() and file_ids[0].isdigit() else None
    return m["game"].lower(), int(m["mod_id"]), file_id
