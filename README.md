# Jikan

Jikan is a local CLI for tracking work, correcting records, and reviewing time by project and tag. It stores entries in SQLite; no account or server is required.

## Install and setup

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
# Install the current checkout as a command available on your PATH.
uv tool install .
jikan --help

# Initialize the database (safe to repeat; existing records are preserved).
jikan init
jikan project add --name client-web --description "Client website"
jikan project add --name jikan
jikan tag add --name development
jikan tag add --name frontend
jikan tag add --name review
jikan project list
jikan tag list
```

For development, run `uv sync --dev`, then use `uv run jikan` in place of `jikan`. Run the tests with `uv run pytest -q` and checks with `uv run ruff check .` and `uv run ruff format --check .`.

## Enable and check shell completion

Run this from your interactive shell (Zsh, Bash, Fish, or PowerShell):

```bash
jikan --install-completion
```

Restart the shell after installation, or reload its startup file (`source ~/.zshrc` for Zsh, `source ~/.bashrc` for Bash). The installer reports the generated completion file. `jikan --show-completion` displays the script for the current shell. If `jikan --help` shows that these options take a shell argument, use, for example, `jikan --install-completion zsh` instead.

To verify activation, type the following and press Tab where indicated; do not type the literal `<Tab>`:

```text
jikan start --project cli<Tab>                 # offers client-web
jikan start --project client-web --tag f<Tab>  # offers frontend
jikan start --tag frontend --tag r<Tab>        # offers review
```

Project and tag candidates come from the local database on each request and are filtered by the typed prefix. Name completion also works for `switch`, `edit`, and history filters; `edit --remove-tag` completes tag names. Before initialization, or if the database cannot be read, completion safely returns no candidates. Full names work without shell completion.

## Record work

```bash
jikan start --title "Build login page" --project client-web \
  --tag development --tag frontend
jikan status

# Stop the previous task and start the next task at the same instant.
jikan switch --title "Review PR #43" --project jikan --tag review

# Open a live view in a terminal; Ctrl+C closes the view and keeps recording.
jikan timer
jikan stop
```

`start` and `switch` accept `--description` (`-d`) and `--title` (`-t`). Projects and tags are optional; unclassified work appears as `Unassigned`. Names must already exist: use `project add` or `tag add` to register them. Repeat `--tag` to attach multiple tags.

Only one entry can run at a time. A second `start` fails without changing the running record and suggests `switch` or `stop`. `switch` starts a new entry when none is running; if validation or saving fails, the previous record stays running. Classification is specified for each new task.

`status` shows the title, project, tags, start time, and elapsed time. `stop` shows the stopped task, end time, and final duration. `timer` updates the elapsed clock every second, uses large digits when space allows, and prioritizes the clock in a small terminal. It displays `Untitled task` for a blank title. An empty `status` or `timer` exits successfully with a start example; an empty `stop` exits with an error.

## Review and edit

```bash
jikan list                         # today in the configured timezone
jikan list --today
jikan list --all                    # full history
jikan list --from 2026-10-01 --to 2026-10-31
jikan list --from 2026-10-01 --project client-web --tag development
jikan list --all --tag development --tag frontend
jikan view 42                      # replace 42 with an ID from list

jikan edit 42 --title "Build login form" --description "Corrected notes"
jikan edit 42 --project client-web --remove-tag frontend --tag review
jikan edit 42 --start "2026-10-21 09:00:00" --end "2026-10-21 09:42:18"
jikan edit 42 --start "2026-10-21T09:00:00+09:00"
jikan delete 42                    # asks for confirmation
```

`list` includes ID, date, status (`Running`/`Done`), duration, title, project, tags, applied filters, and total time. Running entries use elapsed time at the moment of the query.

`edit` supports title, description, start/end time, project, and tag additions/removals. Changes are saved together; an invalid time range or unknown classification (including a nonexistent removal ID) leaves the entry unchanged. Removing an existing tag that is not attached is a warning and a no-op; other valid edits still apply. The end must be on or after the start. Datetimes without an offset use the configured timezone; ISO-8601 values with an offset specify an exact instant. The legacy `YYYY/MM/DD HH:MM:SS` format is also accepted. Use explicit offsets around daylight-saving clock changes to disambiguate local times.

## Reports and CSV

```bash
jikan report --from 2026-10-01 --to 2026-10-31
jikan report --from 2026-10-01 --to 2026-10-31 --project client-web
jikan report --all --tag development --tag frontend
jikan export --from 2026-10-01 --to 2026-10-31 --format csv > october.csv
jikan export --all --project client-web --tag review > reviews.csv
```

`list`, `report`, and `export` share the same period and classification filters:

- With no period flags, they select **today** in the configured timezone. Use `--all` for every date.
- `--from YYYY-MM-DD` and `--to YYYY-MM-DD` include both boundary dates. Either end may be omitted for an open range. Do not combine a date range with `--today` or `--all`.
- Selection uses the entry's **start time** in the configured timezone. An included entry contributes its **entire duration**, even across midnight or beyond the requested end date. A record started before the period is excluded even if it ends inside it.
- `--project NAME` matches an exact project name. Repeated `--tag NAME` filters use **AND**: the entry must have every requested tag. Project and tag filters are combined.

Reports include the period, timezone, total, project totals, and tag totals. Each entry belongs to at most one project, so project totals add up to the overall total. Each attached tag receives the entry's full duration, so tag totals can exceed the overall total. Entries without a project or tags are included under `Unassigned` in the respective breakdown.

CSV stdout contains only the following header and data rows; conditions, warnings, and empty-result explanations go to stderr:

```csv
id,start_at,end_at,duration,title,project,tags
42,2026-10-21T09:00:00+09:00,2026-10-21T09:42:18+09:00,00:42:18,Build login page,client-web,"development,frontend"
```

Timestamps include UTC offsets. Duration is `HH:MM:SS` with total hours (it does not wrap at 24 hours). Running entries have an empty `end_at`; their duration is elapsed time. Missing projects/tags are empty fields. Tags occupy one comma-separated field; CSV quoting protects commas, quotes, and newlines in values. Empty queries succeed: reports/lists show an empty result and zero total; exports emit the header only.

## Project and tag management

```text
jikan project list
jikan project add --name NAME [--description TEXT]
jikan project edit ID [--name NAME] [--description TEXT]
jikan project view ID
jikan project delete ID
jikan project archive ID
jikan project unarchive ID

jikan tag list
jikan tag add --name NAME
jikan tag edit ID --name NAME
jikan tag delete ID
```

Project and tag names are unique. Deletions ask for confirmation. Archived projects are hidden from `project list`; their existing entries remain available in history and reports.

## Storage and timezone

Data is stored in `~/.jikan/database.db`. Optional configuration lives at `~/.jikan/config.toml`:

```toml
timezone = "Asia/Tokyo"
```

`Asia/Tokyo` is the default. Set another IANA timezone, such as `America/New_York`, to change local display, date selection, and interpretation of offset-free edit times. Stored times represent UTC instants. Changing the timezone changes which local date an entry belongs to; it does not shift the recorded instant.

Tests can set `JIKAN_TEST_NOW` to an ISO-8601 timestamp **with an offset**, for example `2026-10-21T09:00:00+09:00`. This fixes the application clock across CLI processes, including elapsed-time queries; unset it for normal use. `JIKAN_HOME` is not supported; tests isolate storage through the child process's `HOME`.

## Compatibility and migration

Existing SQLite data is reused; `jikan init` does not clear it. Back up the database before upgrading or editing important records.

| Earlier usage | Current usage |
| --- | --- |
| `jikan list` for all records | `jikan list --all`; the default is now today |
| `jikan start --id 1` | Still accepted; prefer `--project NAME` or explicit `--project-id 1` |
| `jikan edit 42 --project 1` | Prefer `--project NAME` or `--project-id 1` |
| `jikan edit 42 --add-tag 2` | Still accepted as an ID; prefer `--tag NAME` |
| `jikan edit 42 --remove-tag 2` | Prefer `--remove-tag NAME` or unambiguous `--remove-tag-id 2` |

For `edit`, numeric `--project` and `--remove-tag` values resolve a matching name first, then fall back to a legacy ID. Use the explicit ID options when numeric names exist. `switch` also accepts `--project-id` and the legacy `--id` alias. Do not combine project name and ID options. `--tag` always takes a name.

Removing a nonexistent tag ID now fails the entire edit; older versions only warned and could save other fields. Check `jikan tag list` and retry with a valid tag.

The MVP covers the first three stages of the [user flow](docs/user-flow-mvp.md): recording, reviewing/correcting, and reporting/exporting. Suggestions based on recent use, classification inheritance, forgotten-stop detection, bulk edits, and customized exports/invoicing are future improvements. See the [requirements](docs/ui-ux-requirements.md) and [acceptance scenarios](docs/e2e-acceptance-scenarios.md) for the feature contracts.
