# CLI acceptance tests

Run `uv run pytest -q tests/e2e`. CI runs this after lint and unit/command tests.
Every command is a real subprocess using a temporary `HOME` and a child-only
`JIKAN_TEST_NOW=2026-10-21T09:00:00+09:00`. Setup writes an explicit Asia/Tokyo
configuration. Tests may override the child clock to create history without sleeps.
The PTY live-update tests alone omit the fixed clock so real elapsed seconds advance;
they wait for actual rendered frames with bounded deadlines, then send terminal Ctrl+C.
No test changes the parent environment or mocks product functionality.

The scenario specification is `docs/e2e-acceptance-scenarios.md`, section 5;
section 4 describes the superseded CLI. Existing lifecycle/deletion tests remain in
`test_cli.py`, updated to explicit ID compatibility flags and `list --all`.

| Scenario | Public CLI test |
| --- | --- |
| SET-01 | `test_recording.py::test_set_01` |
| CMP-01 | `test_completion.py::test_cmp_01_dynamic_protocol`, `test_cmp_01_missing_database_and_no_candidates_are_safe` |
| STR-01 | `test_recording.py::test_str_01_sts_01_stp_01` |
| STR-02 | `test_recording.py::test_str_02_sts_02_stp_02` |
| STR-03 | `test_recording.py::test_str_03_swt_03_invalid_classification_is_atomic` |
| STR-04 | `test_recording.py::test_str_04_swt_01` |
| SWT-01 | `test_recording.py::test_str_04_swt_01` |
| SWT-02 | `test_recording.py::test_swt_02` |
| SWT-03 | `test_recording.py::test_str_03_swt_03_invalid_classification_is_atomic` |
| STS-01 | `test_recording.py::test_str_01_sts_01_stp_01` |
| STS-02 | `test_recording.py::test_str_02_sts_02_stp_02` |
| STP-01 | `test_recording.py::test_str_01_sts_01_stp_01` |
| STP-02 | `test_recording.py::test_str_02_sts_02_stp_02` |
| TMR-01 | `test_timer.py::test_tmr_01_02_03_public_cli_pty[80-24]` |
| TMR-02 | `test_timer.py::test_tmr_01_02_03_public_cli_pty` |
| TMR-03 | `test_timer.py::test_tmr_01_02_03_public_cli_pty[40-12]`, `test_timer.py::test_tmr_03_empty_state`, `test_recording.py::test_multiple_running_is_detected_without_mutation[timer]` |
| LST-01 | `test_history.py::test_lst_01_exp_01_same_filters_and_totals` |
| EDT-01 | `test_history.py::test_edt_01_named_and_legacy_edit` |
| EDT-02 | `test_history.py::test_edt_02_all_fields_and_links_unchanged` |
| RPT-01 | `test_history.py::test_rpt_01_105_minutes_exclusive_projects_overlapping_tags` |
| RPT-02 | `test_history.py::test_rpt_02_tz_month_boundary_whole_duration_and_empty`, `test_rpt_02_respects_nondefault_configured_timezone` |
| EXP-01 | `test_history.py::test_lst_01_exp_01_same_filters_and_totals`, `test_exp_01_csv_quoting_aware_timestamps_and_pure_stdout` |

Failure checks compare complete SQLite dumps (all fields, tags and links), not just
counts. Multiple-running corruption is injected only as test data, and each public
recording command must detect it without writes. Completion requests use Typer's
Zsh protocol (`_JIKAN_COMPLETE=complete_zsh`, `_TYPER_COMPLETE_ARGS`) as generated
by `--show-completion zsh`, including repeated `--tag` and a missing database.

## Verification

The completed MVP passed all **345 tests**, including the **68 subprocess and
PTY acceptance cases** mapped above. The final full suite completed in 279.18
seconds. Ruff lint, formatting, and `git diff --check` also passed.

CI runs lint, unit/command tests, and subprocess/PTY tests as separate steps in
`ci.yml`.
