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
- **EVERY `.py` file MUST start with** `# -*- coding: utf-8 -*-` (line 1, or line 2 after a shebang) — unconditionally, not only files that currently contain non-ASCII. A file that lacks it and later gains a non-ASCII char fails to compile, so always add it up front and never have to think about it again.
- **Keep docstrings and dunder metadata (`__title__`, `__author__`, `__doc__`, `__tooltip__`) ASCII-only.** pyRevit's component parser (`pyrevit.extensions.genericcomps`) reads a button's docstring/metadata and ASCII-encodes it for the tooltip; a non-ASCII char there (even `§`, `—`, or Hebrew) raises `UnicodeEncodeError` and the whole extension fails to load on reload — and the coding header does **not** prevent this (it only fixes the compiler). Non-ASCII is fine inside the script *body* (string literals shown to users), where the header covers it; just never in the docstring/metadata of a `script.py`. Use `-`/`--` instead of en/em dashes and spell out symbols (`section` not `§`).
- **No pip / no CPython C-extensions** (`requests`, `pandas`, `numpy` are unavailable). HTTP goes through `System.Net.WebClient` (see `lib/HttpRequest.py`), not `requests`.
- **.NET interop** — types come from `System`, `Autodesk.Revit.DB`, `pyrevit.framework`. Strings are .NET strings; watch Unicode/`str`/`unicode` boundaries.
- Integer division, `dict.has_key`, `unicode()` and other Py2 behaviors apply.

## ⚠️ Connectivity Guardrail — ONE Backend Only

`pyBpm.extension` connects **only** to the pyBpm Azure server. It must **never** call the internal BPM ports (5050 / 3000 / 8010 / 8000) — those are reachable only inside the office LAN and would break for every external client.

- Base URL is `Config.server_url`: `http://localhost:5000/` in dev, `https://pybpm.azurewebsites.net/` in prod.
- All server traffic flows through `lib/ServerUtils.py` → `lib/HttpRequest.py` (`get`/`post`/`patch` via `WebClient`).
- Blast radius: changing the pyBpm-server API (Ch 14) breaks this extension; this is its primary client.

## ⚠️ Scripts Must Be Generic — NEVER Hardcode Model-Specific Data

**Every script here is GENERIC — it ships to many client offices and must work on ANY model, never one specific project.** Do not put model-specific data into a script — no hardcoded element IDs, link IDs, link names, model GUIDs, level names, or coordinates copied from a single model.

- **Resolve links and elements through the proper lookup** (category/discipline filters, the project's configured links, or explicit user selection) — **never by a literal `ElementId`, by name, or by index.**
- **If it is not clear which link or element is the right one — ASK. Do not decide by ID.**
- A hardcoded ID silently makes a script "work on my model" and break for every client — doubly critical here, since this extension is customer-facing.

## ⚠️ Element Lifetime — Hold `ElementId`s, Never Live References

An `Element` / `Document` object is a **handle into Revit's memory, not a value**. Once Revit frees the underlying object the handle is dead and *any* access on it throws — this is the root cause of the whole `"The referenced object is not valid"` family of crashes.

- **Store the `ElementId` and resolve the element at the point of use.** Applies anywhere the reference outlives a single operation: modeless windows, hooks, External Event inputs, module-level caches, UI state kept between button clicks.
- When a live reference is unavoidable *within* one operation — **`IsValidObject` first, always.** Every other member throws on a dead handle, **`.Equals()` included**; `IsValidObject` returns `False` instead of throwing, on both `Element` and `Document`.
- **`Document` is a live reference too** — a link's document dies on Reload/Unload, the host document on close. The `RevitLinkInstance` is the anchor: it is an element of the *host* model and survives a link reload, so keep **its** Id and call `GetLinkDocument()` again on every use. Ids harvested from inside the link re-resolve in the new document (a dead graph is repairable). Elements collected from a link — views, filters — die as one generation together with it.
- **pyRevit scope teardown:** at the end of every script that does not set `__persistentengine__ = True`, pyRevit deletes all non-dunder globals of `script.py` (imported modules are untouched). So **any code that runs after the script returns** — modeless-window handlers, WPF callbacks, External Event handlers — **must live in an imported module** (`lib/`, `ui/`), never in `script.py`. The failure is silent: `NameError` inside the handler, swallowed by an `except` whose `traceback` was deleted too; the button simply does nothing.

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

## חזק וברוך (סיום משימה)

הביטוי **"חזק וברוך"** הוא האישור לכל השלבים כאן — אין לעצור לאישור נוסף על bump/commit/merge/push. הנוהל הכללי: skill `hazak-uvaruch`. ההנחיות כאן נקבעו ע"י אייל ב-2026-08-05 והן הסמכות.

**הרצף:**

1. **version bump** — `extension.json` → `"version"`, patch. זהו קובץ הגרסה היחיד בעץ, ו-`lib/Config.py` קורא אותו בזמן ריצה.
2. **commit** — בסגנון הקיים: `Update version to 1.10.2: <מה שונה> (T-####)`
3. **merge ל-`main`**
4. **push**
5. **TaskDeck → `done-dev`**, ולשאול את אייל: להעביר ל-`done` או להוציא מייל עדכונים?

**אין שלב deploy נפרד** — ה-push ל-`main` הוא שמעמיד את הקוד ב-`main.zip`, ומשם כל מי שלוחץ `Update.smartbutton` מקבל אותו.

**עדכון רגיל מול עדכון כפוי — שני מסלולים במכוון:**

- **רגיל (ברירת המחדל):** המשתמש לוחץ `Update.smartbutton` מתי שנוח לו ומקבל את הגרסה האחרונה מ-`main`. זה מה ש"חזק וברוך" מייצר.
- **כפוי:** כשיוצא עדכון חשוב שחייב להגיע לכולם — משנים את ה-flag ‏`v-update-required` ב-`pyBpm-server/src/routes/info/index.ts`, ואז העדכון נכפה על כל המשתמשים בפתיחת Revit.

**"חזק וברוך" לא נוגע ב-flag.** הכפייה היא החלטה נפרדת של אייל לכל מקרה לגופו, ודורשת גם deploy של `pyBpm-server`. אם השינוי נראה לך כזה שמצדיק כפייה — לציין זאת בדוח הסיום ולתת לאייל להחליט.

**כללי זהירות שנשארים בתוקף:**

- בדיקה ידנית ב-Revit חי לפני ה-commit — זה השער היחיד, אין build, אין טסטים ואין CI.
- אי אפשר לבדוק את מנגנון העדכון מקומית: `Update.py` מסרב לרוץ על עץ עבודה של git.
