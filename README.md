# Jikan

Jikan brings effortless time management right to your CLI!

## Features

- Start/stop time entries from the terminal
- Organize entries with projects and tags
- View status and list entries in a table

## Install

Install with `uv` (this may change in the future):

```bash
uv tool install jikan
```

## Initialize

```bash
jikan init
```

## Quick Start

```bash
# start a timer (optionally attach a project by ID)
jikan start --title "Client kickoff" --description "Prep agenda and notes"
# Start a timer and associate it with project ID 1
jikan start --id 1 --title "Bugfix sprint"

# check current status
jikan status
# ID: 1
# Title: Client kickoff
# Description: Prep agenda and notes
# Time entry running: 00h 14m 08s
# Project: Acme Web Revamp
# Tags: meeting, prep

# stop the running entry
jikan stop
# Success: Time entry stopped at 2026-02-01 13:24:30.147055

# list entries
jikan list
# ┏━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┓
# ┃ ID ┃ Title                     ┃ Description              ┃ Start at            ┃ End at              ┃ Created at          ┃ Updated at          ┃ Project ┃
# ┡━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━┩
# │ 1  │ Acme site audit           │ Review top pages         │ 2026-01-24 08:37:30 │ 2026-01-24 09:05:40 │ 2026-01-24 08:37:30 │ 2026-01-24 09:05:40 │ 1       │
# │ 2  │ Inbox                     │                          │ 2026-01-24 09:10:00 │ 2026-01-24 09:20:10 │ 2026-01-24 09:10:00 │ 2026-01-24 09:20:10 │ None    │
# │ 3  │ Client kickoff            │ Prep agenda and notes    │ 2026-02-01 13:23:29 │ 2026-02-01 13:24:30 │ 2026-02-01 13:23:29 │ 2026-02-01 13:24:30 │ None    │
# └────┴───────────────────────────┴──────────────────────────┴─────────────────────┴─────────────────────┴─────────────────────┴─────────────────────┴─────────┘
```

## Commands

Root commands:

- `jikan init`
- `jikan start [--id] [--title] [--description]`
- `jikan stop`
- `jikan status`
- `jikan list`
- `jikan edit ID [--title] [--description] [--start] [--end] [--project] [--add-tag] [--remove-tag]`
- `jikan delete ID`
- `jikan view ID`

Project commands:

- `jikan project list`
- `jikan project add --name NAME [--description]`
- `jikan project edit ID [--name] [--description]`
- `jikan project delete ID`
- `jikan project view ID`
- `jikan project archive ID`
- `jikan project unarchive ID`

Tag commands:

- `jikan tag list`
- `jikan tag add --name NAME`
- `jikan tag edit ID --name NAME`
- `jikan tag delete ID`

## Data Location

Jikan stores data in SQLite at:

```
~/.jikan/database.db
```

## Roadmap

- [ ] Entry switching
- [ ] Reports and exports
