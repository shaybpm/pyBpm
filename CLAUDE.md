# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

The **official, production pyRevit extension** (`pyBpm.extension`) distributed to client offices that use BPM's services. Written in **IronPython 2.7**, it runs inside Revit's IronPython engine via the pyRevit framework.

This is **NOT** the internal `DEV.extension` (`../DEV.extension/`). DEV is BPM's in-house toolbox; `pyBpm` is the customer-facing product shipped via the pyBpm Installer (Ch 13) and self-updated through the `Update.smartbutton`. Keep customer-facing scope in mind — no internal-only or experimental tooling belongs here.

- GitHub: `https://github.com/shaybpm/pyBpm.git`
- Parent project docs: `../../01_BPM-Docs/12_BPM_pyRevit_Extensions.md` (extensions) + `../../01_BPM-Docs/14_BPM_pyBpm_Azure_Server.md` (the only backend it talks to)

## ⚠️ IronPython 2.7 — Read First

All scripts run on **IronPython 2.7**, NOT CPython 3. This is the single biggest source of mistakes. The shared `bpm-revit-dev` skill documents the full gotcha list — invoke it before writing Revit/pyRevit code. The essentials:

- **Python 2 syntax only** — `print x` works, f-strings do **not**. Use `.format()` or `%`.
- **Every file with Hebrew or non-ASCII literals MUST start with** `# -*- coding: utf-8 -*-`. Most lib files already do.
- **No pip / no CPython C-extensions** (`requests`, `pandas`, `numpy` are unavailable). HTTP goes through `System.Net.WebClient` (see `lib/HttpRequest.py`), not `requests`.
- **.NET interop** — types come from `System`, `Autodesk.Revit.DB`, `pyrevit.framework`. Strings are .NET strings; watch Unicode/`str`/`unicode` boundaries.
- Integer division, `dict.has_key`, `unicode()` and other Py2 behaviors apply.

## ⚠️ Connectivity Guardrail — ONE Backend Only

`pyBpm.extension` connects **only** to the pyBpm Azure server. It must **never** call the internal BPM ports (5050 / 3000 / 8010 / 8000) — those are reachable only inside the office LAN and would break for every external client.

- Base URL is `Config.server_url`: `http://localhost:5000/` in dev, `https://pybpm.azurewebsites.net/` in prod.
- All server traffic flows through `lib/ServerUtils.py` → `lib/HttpRequest.py` (`get`/`post`/`patch` via `WebClient`).
- Blast radius: changing the pyBpm-server API (Ch 14) breaks this extension; this is its primary client.

## Environment Detection (`lib/Config.py`)

Dev vs prod is decided by inspecting `__file__`: if the path contains the BPM `Software_Development` working-tree string it returns `"dev"` (→ localhost:5000), otherwise `"prod"` (→ Azure). A deployed client copy lives outside that path, so it resolves to prod automatically.

- To force prod while testing locally, uncomment the `return "prod"` line at the top of `get_env_mode()`.
- `Config.root_path` is derived by slicing `__file__` at `.extension`; other paths (shared parameters, `extension.json`) hang off it.

## Architecture

### Tab / Panel layout (`pyBpm.tab/bundle.yaml`)
```
BPM       → Info, Custom, Update (self-update smartbutton)
BIM       → CreateWorksets, GetLOISchedules, ModelQuality (Auto/Report), SyncRoomInfo
Sections  → GetBpmSections
Openings  → GetBpmTags, LoadFamilies, OpeningExplorer, OpeningSet, TrackingOpenings
```
A second tab, `pyBpmTests.tab/DEV.panel`, holds dev/test buttons and is **gitignored** (see `.gitignore`).

### Shared libraries (`lib/`)

| Module | Purpose |
|--------|---------|
| `Config.py` | Env (dev/prod) detection, `server_url`, root/shared-parameter paths, version read |
| `HttpRequest.py` | Low-level REST client over `System.Net.WebClient` (get/post/patch/download) |
| `ServerUtils.py` | pyBpm-server API calls + `ServerPermissions` (per-project feature gating) |
| `RevitUtils.py` | Largest module (~22 KB) — Revit API abstractions: elements, geometry, views, links |
| `RevitUtilsOpenings.py` | Opening-specific Revit helpers (filters, opening elements) |
| `ExEventHandlers.py` / `ReusableExternalEvents.py` / `ExternalEventDataFile.py` | External Event pattern for modeless Revit API actions (see below) |
| `ProgressBar.py` (+ `ui/ProgressBar.xaml`) | WPF progress dialog |
| `ExcelUtils.py` / `ExcelUtilsPure.py` | Excel I/O (Pure = no Interop dependency, preferred) |
| `HtmlUtils.py` | HTML report generation (pyRevit output window) |
| `SharedParametersUtils.py` | Bind/manage shared parameters from `pyBPM_SharedParameters.txt` |
| `TransferUtility.py` | Cross-model data transfer |
| `PyRevitUtils.py` | Logger, TempElementStorage, alert wrappers |
| `LocalUserInputs.py`, `PyBpmAppUtils.py`, `UiUtils.py`, `pyUtils.py` | Misc helpers |

### External Event pattern
Revit API write operations from a modeless context (hooks, async callbacks) cannot run on the UI thread directly. The `ExEventHandlers` / `ReusableExternalEvents` / `ExternalEventDataFile` trio wraps work in `ExternalEvent` + `TransactionGroup`/`Transaction`, passing data through a temp file. Follow this pattern instead of calling the Revit API inline from a hook.

### Hooks (`hooks/`)
pyRevit fires these on Revit lifecycle events: `app-init`, `doc-opened`, `doc-changed`, `doc-syncing`, `view-activated`. Notably `app-init.py` runs the auto-updater (`Update`) in **prod** only. Hooks load `lib/` modules by appending button-specific `lib/` paths to `sys.path`.

## pyRevit Naming Conventions

Directory suffixes encode UI behavior:
- `*.pushbutton/` — simple button   · `*.smartbutton/` — button with self-init logic (e.g. Update)
- `*.pulldown/` — dropdown menu   · `*.nobutton/` — code-only, no UI button
- `*.panel/` — ribbon panel   · `*.tab/` — ribbon tab
Each button folder contains `script.py` (entry point), optional `bundle.yaml`, `icon.png`, and a local `lib/` or `ui/` folder.

## Deployment & Versioning

- **No build step** — pyRevit loads scripts directly from disk; changes take effect on the next button click (a full Revit reload is needed for `lib/` and startup hook changes).
- Distributed to clients via the **pyBpm Installer** (Ch 13); updated in place by the **`Update.smartbutton`**, which compares the local `extension.json` `version` against `https://raw.githubusercontent.com/shaybpm/pyBpm/main/extension.json`.

### Version bump — REQUIRED (unlike DEV.extension)
This extension **has** a version field: `extension.json` → `"version"`. The self-updater relies on it, so the global "every code change bumps the version" rule **applies here**. Bump the patch number in `extension.json` for any code change before committing (recent history: `Bump version to 1.9.0 …`). This is the opposite of `DEV.extension`, which has no version file.

## Working Notes

- Test in Revit before committing; reload the extension (or restart Revit) after editing `lib/` or `hooks/`.
- Keep changes small and follow existing patterns in the file — don't refactor surrounding code.
- Comments in English, only where the WHY is non-obvious.
- `.vscode`, `pybpmtests.tab`, and `fake-data` are gitignored.
