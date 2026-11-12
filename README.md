# cdmods

A command-line mod list for Nexus Mods downloads.

cdmods reads the mod archive names, looks them up on Nexus, and keeps a `modlist.json`. Then it can tell you which files have a newer version and give you the download links.

Originally made for Crimson Desert, but works with any game.

## Setup

Requires Python 3.11+. No other dependencies.

```sh
pip install -e .        # optional: adds a `cdmods` command
python -m cdmods --help # works without installing, from this folder
```

## Usage

```sh
cdmods scan "C:/Games/Crimson Desert mods"    # identify archives, create/update modlist.json
cdmods check                                  # outdated / gone / up to date
cdmods links --outdated                       # download pages for the newer versions
cdmods links --outdated --open                # open them in your browser, one at a time
cdmods add https://www.nexusmods.com/crimsondesert/mods/146   # add a mod you have no archive for
cdmods remove 146                             # remove it again
cdmods export -o modlist.md                   # a readable list with links (or --format csv)
cdmods export --format html -o modlist.html   # a page of links, outdated files marked and listed
```

- `scan` looks only at the top of the folder. Add `--recursive` to include subfolders. Later scans reuse the folder, so `cdmods scan` is enough.
- The list is `./modlist.json` by default; use `--list PATH` to keep it somewhere else.
- `modlist.json` is plain JSON. You can edit the `note` of any entry.

## Other games

`cdmods` works for any game on Nexus Mods. To start a list for another game, give its Nexus domain: the part of the URL after `nexusmods.com/`, like `skyrimspecialedition`. You can give it with `--game` on the first scan, or add a mod by its URL:

```sh
cdmods --list skyrim.json scan "D:/Skyrim mods" --game skyrimspecialedition
cdmods --list skyrim.json add https://www.nexusmods.com/skyrimspecialedition/mods/266
```

After saving the list, later commands only need `--list skyrim.json`. Use a separate list file for each game.

## Notes

- **Names:** Nexus names downloads either `Name-203-1-7-1778420608.zip` (mod ID, version, upload time) or `Name 452 3.1 2026-09-07T20-00Z g7OwxhwXd.zip` (mod ID, version, upload time, and a file code). `cdmods` matches these to the exact Nexus file.
- **Updates:** Nexus keeps every version of a file in one "file group", even if the author renames it. A file is **outdated** when its group has a newer file. It's **gone** when the group no longer offers any file. `check` then lists what the mod offers now.
- **Data:** everything comes from the public Nexus GraphQL API (`api.nexusmods.com/v2/graphql`).

This program doesn't download or install mods. Use the links with your browser, then your mod manager (JSON Mod Manager, Crimson Sharp, ...).
