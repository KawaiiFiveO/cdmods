# cdmods

A command-line mod list for Nexus Mods downloads, made for Crimson Desert.

It reads the archive names Nexus gives your downloads, looks them up on Nexus, and keeps a `modlist.json`. Then it can tell you which files have a newer version and give you the download links.

## Setup

Requires Python 3.11+. There are no dependencies.

```sh
pip install -e .        # optional: adds a `cdmods` command
python -m cdmods --help # works without installing, from this folder
```

## Usage

```sh
cdmods scan "C:/Games/Crimson Desert mods"   # identify your archives, create/update modlist.json
cdmods check                                  # outdated / gone / up to date
cdmods links --outdated                       # download pages for the newer versions
cdmods links --outdated --open                # open them in your browser, one at a time
cdmods add https://www.nexusmods.com/crimsondesert/mods/146   # add a mod you have no archive for
cdmods remove 146                             # remove it again
cdmods export -o modlist.md                   # a readable list with links (or --format csv)
cdmods export --format html -o modlist.html   # a page of links, outdated files marked and listed first
```

- `scan` looks only at the top of the folder. Add `--recursive` to include subfolders. Later scans reuse the folder, so plain `cdmods scan` is enough.
- The list is `./modlist.json` by default; use `--list PATH` to keep it somewhere else.
- `modlist.json` is plain JSON. You can edit the `note` of any entry, and scans keep it.

## How it works

- **Names:** Nexus names downloads either `Name-203-1-7-1778420608.zip` (mod ID, version, upload time) or `Name 452 3.1 2026-09-07T20-00Z g7OwxhwXd.zip` (mod ID, version, upload time, and a file code). `cdmods` matches either form to the exact Nexus file.
- **Updates:** Nexus keeps every version of a file in one "file group", even if the author renames it. A file is **outdated** when its group has a newer file. It's **gone** when the group no longer offers any file, because the author archived it or started a new file in its place. `check` then lists what the mod offers now.
- **Data:** everything comes from the public Nexus GraphQL API (`api.nexusmods.com/v2/graphql`), which needs no key.

This program doesn't download or install mods. Use the links with your browser, then your mod manager (JSON Mod Manager, Crimson Sharp, ...).

## Development

```sh
python -m unittest      # run the tests
```
