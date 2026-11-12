"""Command-line interface: cdmods <command>, or python -m cdmods <command>."""

from __future__ import annotations

import argparse
import csv
import html
import io
import sys
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .modlist import Entry, ModList, ModListError, load, save
from .nexus import Nexus, NexusError, NexusFile, file_url, mod_url, parse_url
from .scan import scan
from .status import State, Status, classify

DEFAULT_LIST = "modlist.json"
DEFAULT_GAME = "crimsondesert"

# Tests swap this for a fake.
make_nexus = Nexus


class CliError(Exception):
    pass


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        # Mod names can hold characters a Windows console can't show.
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    args = _parser().parse_args(argv)
    try:
        return args.handler(args)
    except (CliError, ModListError, NexusError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cdmods", description="Keep a list of your Nexus Mods downloads and see which are outdated.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--list", type=Path, default=Path(DEFAULT_LIST), help=f"mod list file (default: ./{DEFAULT_LIST})")
    commands = parser.add_subparsers(title="commands", required=True, metavar="COMMAND")

    p = commands.add_parser("scan", help="identify the mod archives in a folder and update the list")
    p.add_argument("folder", nargs="?", type=Path, help="folder with your downloaded archives (default: the last one scanned)")
    p.add_argument("--recursive", action="store_true", help="also look in subfolders")
    p.add_argument("--game", help=f"Nexus game domain for a new list (default: {DEFAULT_GAME})")
    p.set_defaults(handler=cmd_scan)

    p = commands.add_parser("check", help="show which listed files have a newer version")
    p.add_argument("--outdated", action="store_true", help="only show outdated files")
    p.set_defaults(handler=cmd_check)

    p = commands.add_parser("links", help="print download links")
    p.add_argument("--outdated", action="store_true", help="only outdated files")
    p.add_argument("--current", action="store_true", help="link the version you have, not the newest (works offline)")
    p.add_argument("--open", action="store_true", help="open the links in your browser, one at a time")
    p.set_defaults(handler=cmd_links)

    p = commands.add_parser("add", help="add a mod by its Nexus URL")
    p.add_argument("url", help="mod page URL, or a file URL with file_id=...")
    p.set_defaults(handler=cmd_add)

    p = commands.add_parser("remove", help="remove a file from the list")
    p.add_argument("mod_id", type=int)
    p.add_argument("group_id", type=int, nargs="?", help="needed when several files of the mod are listed")
    p.set_defaults(handler=cmd_remove)

    p = commands.add_parser("export", help="write the list as Markdown, CSV or an HTML page of links")
    p.add_argument("--format", choices=("md", "csv", "html"), default="md", help="html also checks for updates and marks outdated files")
    p.add_argument("-o", "--output", type=Path, help="file to write (default: print it)")
    p.set_defaults(handler=cmd_export)
    return parser


# Commands


def cmd_scan(args: argparse.Namespace) -> int:
    modlist = _load(args.list, required=False)
    if modlist and args.game and args.game != modlist.game:
        raise CliError(f"{args.list} is a list for {modlist.game}, not {args.game}")
    folder = args.folder or (Path(modlist.folder) if modlist and modlist.folder else None)
    if folder is None:
        raise CliError('give the folder to scan, e.g. cdmods scan "C:/Games/Crimson Desert mods"')
    folder = folder.expanduser().resolve()
    if not folder.is_dir():
        raise CliError(f"not a folder: {folder}")

    nexus = make_nexus(modlist.game if modlist else args.game or DEFAULT_GAME)
    if modlist is None:
        modlist = ModList(game=nexus.game, game_id=nexus.game_id())
    result = scan(folder, nexus, recursive=args.recursive)
    modlist.folder = folder.as_posix()
    merge = modlist.merge_scan(result.found)
    save(modlist, args.list)

    print(f"Scanned {result.archives} archives in {folder.as_posix()}\n")
    _section("Added", [(e.label, e.version) for e in merge.added])
    _section("Updated", [(after.label, f"{before.version} -> {after.version}") for before, after in merge.updated])
    _section(
        "No longer in the folder (still listed; `cdmods remove` drops them)",
        [(e.label, e.version) for e in merge.missing],
    )
    _section("Older copies (safe to delete)", [(name, f"newer: {e.local_file}") for name, e in result.older_copies])
    _section("Not identified (add them with `cdmods add <nexus url>`)", [(name,) for name in result.unidentified])
    print(f"Saved {args.list} ({len(modlist.entries)} files). Run `cdmods check` to look for updates.")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    modlist = _load(args.list)
    statuses = _statuses(modlist)
    by_state = {state: [s for s in statuses if s.state is state] for state in State}

    _section(
        State.OUTDATED.value,
        [(s.entry.label, f"{s.entry.version} -> {s.latest.version}", _date(s.latest.date), _latest_url(modlist, s)) for s in by_state[State.OUTDATED]],
    )
    if not args.outdated:
        gone_rows = []
        for s in by_state[State.GONE]:
            gone_rows.append((s.entry.label, s.entry.version, s.reason, mod_url(modlist.game, s.entry.mod_id)))
            if s.alternatives:
                gone_rows.append(("", "", "now offered: " + ", ".join(f.name for f in s.alternatives), ""))
        _section(State.GONE.value, gone_rows)
        _section(State.CURRENT.value, [(s.entry.label, s.entry.version, _date(s.entry.uploaded)) for s in by_state[State.CURRENT]])
    print(", ".join(f"{len(by_state[state])} {state.value.lower()}" for state in State))
    return 0


def cmd_links(args: argparse.Namespace) -> int:
    modlist = _load(args.list)
    if args.current and not args.outdated:
        links = [(e.label, file_url(modlist.game, e.mod_id, e.file_id)) for e in modlist.sorted_entries()]
    else:
        links = []
        for s in _statuses(modlist):
            if args.outdated and s.state is not State.OUTDATED:
                continue
            url = file_url(modlist.game, s.entry.mod_id, s.entry.file_id) if args.current else _latest_url(modlist, s)
            links.append((s.entry.label, url))
    if not links:
        print("Nothing to link.")
        return 0
    if not args.open:
        _rows(links, indent="")
        return 0
    for i, (label, url) in enumerate(links, 1):
        print(f"[{i}/{len(links)}] {label}\n  {url}")
        webbrowser.open(url)
        if i < len(links) and _ask("Enter for the next one, q to stop: ").strip().lower() == "q":
            break
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    try:
        game, mod_id, file_id = parse_url(args.url)
    except ValueError as e:
        raise CliError(str(e)) from e
    modlist = _load(args.list, required=False)
    if modlist and game != modlist.game:
        raise CliError(f"that's a {game} mod, but {args.list} is a list for {modlist.game}")
    nexus = make_nexus(game)
    if modlist is None:
        modlist = ModList(game=game, game_id=nexus.game_id())

    files = nexus.mod_files([mod_id])[mod_id]
    if not files:
        raise CliError(f"mod {mod_id} wasn't found on Nexus (removed or hidden?)")
    if file_id is not None:
        chosen = [f for f in files if f.file_id == file_id]
        if not chosen:
            raise CliError(f"mod {mod_id} has no file {file_id}")
    else:
        chosen = _choose_files(files)

    mod = nexus.mods([mod_id]).get(mod_id)
    for f in chosen:
        entry = Entry(f.mod_id, f.group_id, f.file_id, mod.name if mod else f.name, f.name, f.version, f.date)
        if existing := modlist.get(entry.key):
            print(f"Already listed: {existing.label} {existing.version}")
        else:
            modlist.entries.append(entry)
            print(f"Added: {entry.label} {entry.version}")
    save(modlist, args.list)
    return 0


def cmd_remove(args: argparse.Namespace) -> int:
    modlist = _load(args.list)
    matches = [e for e in modlist.entries if e.mod_id == args.mod_id and args.group_id in (None, e.group_id)]
    if not matches:
        raise CliError(f"no listed file matches mod {args.mod_id}" + (f" group {args.group_id}" if args.group_id else ""))
    if len(matches) > 1:
        print(f"Several files of mod {args.mod_id} are listed:")
        _rows([(str(e.group_id), e.label, e.version) for e in matches])
        raise CliError(f"say which one, e.g. cdmods remove {args.mod_id} {matches[0].group_id}")
    modlist.entries.remove(matches[0])
    save(modlist, args.list)
    print(f"Removed: {matches[0].label}")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    modlist = _load(args.list)
    if args.format == "html":
        text = _html(modlist, _statuses(modlist))
    else:
        text = _markdown(modlist) if args.format == "md" else _csv(modlist)
    if args.output:
        args.output.write_text(text, encoding="utf-8", newline="")
        print(f"Wrote {args.output}")
    else:
        sys.stdout.write(text)
    return 0


# Helpers


def _load(path: Path, required: bool = True) -> ModList | None:
    try:
        return load(path)
    except FileNotFoundError:
        if required:
            raise CliError(f"no mod list at {path}; create one with `cdmods scan <folder>`") from None
        return None


def _statuses(modlist: ModList) -> list[Status]:
    entries = modlist.sorted_entries()
    files = make_nexus(modlist.game).mod_files(e.mod_id for e in entries) if entries else {}
    return [classify(e, files[e.mod_id]) for e in entries]


def _latest_url(modlist: ModList, status: Status) -> str:
    if status.latest is None:
        return mod_url(modlist.game, status.entry.mod_id)
    return file_url(modlist.game, status.latest.mod_id, status.latest.file_id)


def _choose_files(files: list[NexusFile]) -> list[NexusFile]:
    offered = sorted((f for f in files if f.is_current), key=lambda f: (f.category != "MAIN", f.name.lower()))
    if not offered:
        raise CliError("this mod offers no current files; use a file URL with file_id=...")
    if len(offered) == 1:
        return offered
    print("This mod offers several files:")
    _rows([(f"{i}.", f.name, f.version, f.category.lower(), _date(f.date)) for i, f in enumerate(offered, 1)])
    answer = _ask("Which ones? (e.g. 1 or 1,3): ")
    try:
        picks = {int(part) for part in answer.replace(" ", "").split(",") if part}
    except ValueError:
        picks = set()
    if not picks or not picks <= set(range(1, len(offered) + 1)):
        raise CliError(f"expected numbers from 1 to {len(offered)}")
    return [offered[i - 1] for i in sorted(picks)]


def _ask(prompt: str) -> str:
    try:
        return input(prompt)
    except EOFError:
        raise CliError("needed an answer, but there's no input to read") from None


def _markdown(modlist: ModList) -> str:
    def cell(text: str) -> str:
        return text.replace("|", "\\|")

    has_notes = any(e.note for e in modlist.entries)
    lines = [f"# Mod list ({modlist.game})", "", "| Mod | File | Version |" + (" Note |" if has_notes else "") + " Download |"]
    lines.append("|---|---|---|" + ("---|" if has_notes else "") + "---|")
    for e in modlist.sorted_entries():
        row = f"| [{cell(e.mod_name)}]({mod_url(modlist.game, e.mod_id)}) | {cell(e.file_name)} | {cell(e.version)} |"
        if has_notes:
            row += f" {cell(e.note)} |"
        lines.append(row + f" [download]({file_url(modlist.game, e.mod_id, e.file_id)}) |")
    return "\n".join(lines) + "\n"


_HTML_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font-family: system-ui, sans-serif; max-width: 64rem; margin: 2rem auto; padding: 0 1rem; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ text-align: left; padding: .4rem .6rem; border-bottom: 1px solid #8884; }}
  tr.outdated {{ background: #f5a62326; }}
  tr.outdated .status {{ color: #c77700; font-weight: 600; }}
  tr.gone .status {{ color: #c0392b; }}
</style>
</head>
<body>
<h1>{title}</h1>
<p>{summary}</p>
<table>
<thead><tr><th>Mod</th><th>File</th><th>Version</th><th>Status</th>{note_header}<th>Link</th></tr></thead>
<tbody>
{rows}
</tbody>
</table>
</body>
</html>
"""


def _html(modlist: ModList, statuses: list[Status]) -> str:
    def link(url: str, text: str) -> str:
        return f'<a href="{html.escape(url)}" target="_blank" rel="noopener">{html.escape(text)}</a>'

    has_notes = any(s.entry.note for s in statuses)
    order = [State.OUTDATED, State.GONE, State.CURRENT]
    rows = []
    for s in sorted(statuses, key=lambda s: order.index(s.state)):
        e = s.entry
        if s.state is State.OUTDATED:
            status, link_text = f"Outdated: {e.version} → {s.latest.version}", f"Download {s.latest.version}"
        elif s.state is State.GONE:
            status, link_text = f"Gone: {s.reason}", "Mod page"
        else:
            status, link_text = "Up to date", "Download"
        cells = [
            link(mod_url(modlist.game, e.mod_id), e.mod_name),
            html.escape(e.file_name),
            html.escape(e.version),
            f'<span class="status">{html.escape(status)}</span>',
        ]
        if has_notes:
            cells.append(html.escape(e.note))
        cells.append(link(_latest_url(modlist, s), link_text))
        rows.append(f'<tr class="{s.state.name.lower()}">' + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")

    counts = {state: sum(1 for s in statuses if s.state is state) for state in State}
    checked = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return _HTML_PAGE.format(
        title=html.escape(f"Mod list ({modlist.game})"),
        summary=html.escape(
            f"{len(statuses)} files: {counts[State.OUTDATED]} outdated, {counts[State.GONE]} gone, "
            f"{counts[State.CURRENT]} up to date. Checked {checked}."
        ),
        note_header="<th>Note</th>" if has_notes else "",
        rows="\n".join(rows),
    )


def _csv(modlist: ModList) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["mod_id", "mod_name", "file_id", "file_name", "version", "uploaded", "local_file", "note", "url"])
    for e in modlist.sorted_entries():
        url = file_url(modlist.game, e.mod_id, e.file_id)
        writer.writerow([e.mod_id, e.mod_name, e.file_id, e.file_name, e.version, _date(e.uploaded), e.local_file or "", e.note, url])
    return out.getvalue()


def _date(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).strftime("%Y-%m-%d")


def _section(title: str, rows: list[tuple[str, ...]]) -> None:
    if rows:
        print(f"{title} ({sum(1 for r in rows if r[0])})")
        _rows(rows)
        print()


def _rows(rows: list[tuple[str, ...]], indent: str = "  ") -> None:
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    for row in rows:
        print(indent + "  ".join(cell.ljust(width) for cell, width in zip(row, widths)).rstrip())
