# App, Plugin, And Checkpoint Status

Date: 2026-05-25

## Completed

- Added plugin manifest boundary metadata:
  - tools
  - required permissions
  - eval suites
  - prompt fragments
  - evidence requirements
  - uninstall paths
- Added plugin manifest validation before plugin code execution.
- Added CLI plugin inspection:

```powershell
metis plugin inspect --path ./plugins/example --json
```

- Added checkpoint inspection commands:

```powershell
metis checkpoint list --state-db .metis/state.db --session-id <session-id> --json
metis checkpoint latest --state-db .metis/state.db --session-id <session-id> --json
```

- Added checkpoint resume command:

```powershell
metis resume --state-db .metis/state.db --session-id <session-id> --message "Continue from the last checkpoint"
```

- Added shared app runtime status helper.
- Added Web runtime status endpoint:

```text
GET /api/status
```

- Added TUI startup display of active tool permission configuration.
- Added Web session detail endpoint:

```text
GET /api/sessions/{session_id}
```

- Added optional app state persistence and Web state-db readback:
  - `AgentAppManifest.state_db_path`
  - `METIS_STATE_DB`
  - `metis run --state-db`
  - `metis tui --state-db`
  - `metis web --state-db`
- Added Windows-friendly UTF-8 BOM handling for user-authored JSON manifests used by app/package/plugin/repair-preflight flows.

- Added optional repair safe-command execution for verified repair plans:

```powershell
metis eval repair-execute --plan-dir ./repair-plan --phase <phase-id> --output-dir ./repair-execute --execute-safe-commands
```

## Verification

- `python -m compileall -q metis`: passed.
- `python -m pytest tests\unit\test_plugin_api.py tests\unit\test_cli_eval.py -q`: `68 passed`.
- `python -m pytest tests\unit\test_cli_eval.py tests\unit\test_state_store.py tests\integration\test_agent_loop_checkpoints.py -q`: `71 passed`.
- `python -m pytest tests\unit\test_app_runtime.py tests\unit\test_app_web.py tests\unit\test_cli_eval.py -q`: `74 passed`.
- `python -m pytest tests\unit\test_cli_eval.py tests\unit\test_app_web.py -q`: `73 passed`.
- `python -m pytest tests\unit\test_cli_eval.py tests\unit\test_state_store.py tests\integration\test_agent_loop_checkpoints.py -q`: `75 passed`.
- `python -m pytest tests\unit\test_state_store.py tests\unit\test_app_web.py tests\unit\test_app_runtime.py tests\unit\test_app_manifest.py tests\unit\test_cli_eval.py -q`: `91 passed`.
- `python -m pytest tests\unit\test_state_store.py tests\unit\test_app_web.py tests\unit\test_cli_eval.py -q`: `84 passed`.
- `python -m pytest tests\unit\test_cli_eval.py tests\unit\test_app_manifest.py tests\unit\test_app_runtime.py tests\unit\test_app_web.py -q`: `86 passed`.
- `python -m pytest tests\unit\test_app_manifest.py tests\unit\test_plugin_api.py tests\unit\test_package_lifecycle.py tests\unit\test_cli_eval.py -q`: `89 passed`.
- `python -m pytest -q`: `477 passed, 4 skipped`.

## Remaining Limits

- Resume execution now exists for persisted message continuation, but it does not yet reconstruct arbitrary mid-tool-call state.
- Repair execution can run declared no-shell safe commands and blocks known shell/destructive/inline interpreter patterns, but it does not yet synthesize or apply code patches by itself.
- App shell status and session detail visibility are implemented, but richer Web/TUI visualizations for full evidence and tool-call timelines remain future hardening work.
