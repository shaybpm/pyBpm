---
name: revit-live-verify
description: When the user asks Claude to verify/check pyRevit or Revit-API logic "for itself" against reality, do it by running against the LIVE Revit model through the Revit-Connector MCP — not by re-reading the code. Trigger when, in a pyRevit/Revit context, the user says "תבדוק בעצמך", "בדוק בעצמך", "תוודא בעצמך", "תבדוק מול Revit", "תבדוק על המודל", "תריץ ותראה", "check yourself", "verify it yourself", "verify against the live model", "actually run it", or asks whether some Revit-API assumption is true on the real model. NOT for static code review (use /code-review) and NOT when Revit is irrelevant.
---

# Revit live verify — check against the open model via the MCP

The user wants you to **stop reasoning about the code and observe what Revit
actually does**. Use the `Revit-Connector` MCP, which runs Revit API calls
against the live, open model.

> Setup is machine-specific. If the `mcp__Revit-Connector__*` tools are not
> available at all, this machine hasn't connected the Revit MCP — tell the
> user that and stop; do not pretend code-reading is verification.

## Step 1 — confirm the model is reachable (always first)

Call `mcp__Revit-Connector__get_revit_status`.

- If it returns `healthy` / `revit_available: true` → proceed.
- If it errors or times out → **do NOT guess and do NOT fall back to
  reading code as if it were verification.** Tell the user plainly:
  "Revit לא נגיש דרך ה-MCP — ודא ש-Revit פתוח עם מודל ושה-Routes Server
  של pyRevit פעיל (פורט 48884)." Then stop and wait.
- Check the `Document` field is the model the user means. If a different
  model is open, say so before drawing conclusions.

## Step 2 — verify with the most specific tool first

Prefer the purpose-built read-only tools over raw code:

- `get_revit_model_info` — categories, levels, links, views, project info
- `get_current_view_elements` / `get_current_view_info` — what's in the active view
- `list_category_parameters` — does a category expose a given parameter?
- `list_levels`, `list_families`, `list_family_categories`, `list_revit_views`

For anything they don't cover — geometry, a specific element by id, host
detection, reference probing — use `execute_revit_code` with a **read-only**
snippet that prints what you need, then read the printout.

`execute_revit_code` runs in Revit's IronPython 2.7 engine, so the snippet
MUST follow `.claude/rules/ironpython-syntax.md` (no f-strings, `.format()`
only, `print()` with parens, etc.). This is real execution — a snippet that
runs here is genuine evidence the API call works.

## Step 3 — report observed vs expected

State what you expected from the code, what Revit actually returned, and
whether they match. A mismatch IS the finding — don't soften it. Quote the
real values (ids, parameter values, orientations) so the user can see the
evidence.

## Hard guardrail — read-only by default

These tools mutate the open model: `execute_revit_code` (when it writes),
`place_family`, `color_splash`, `clear_colors`, `save_document`,
`sync_with_central`, `close_document`, `open_document`, `launch_revit`.

- Verification is a READ operation. Default to read-only API calls — no
  transaction needed for introspection.
- **Never modify, color, save, sync, or close the model to "verify"
  something without explicit user approval.** If a check genuinely requires
  a write (e.g. "does placing this tag succeed"), describe the write and ask
  first. The user's model is live project data.

## Tie-in to the opening dimensioner

The Phase-3 work (see the `opening-sheets` skill) has explicit open items to
validate on a real model — e.g. do BPM circular-opening families expose
`CenterLeftRight`/`CenterFrontBack` references, and are structural slabs
`OST_Floors` or `OST_StructuralFoundation`. These are exactly the questions
to answer with `execute_revit_code` against the open model rather than by
guessing.
