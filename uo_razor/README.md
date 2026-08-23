# Ultima Online Outlands (Razor) importer

Reads hotkey bindings from the ClassicUO "Assistant" (Razor) profiles and
generates the overlay's keymap. Each profile becomes a character; hotkeys are
grouped by category (`Scripts`, `Spells`, `Actions`).

`AUTO_IMPORT` is enabled, so the keymap is refreshed automatically at startup.

## Version

`0.1.0` — compatible with Keymap Overlay `0.x`. If distributing this plugin as
bytecode (`.pyc` / `.pyz`), build it with the same CPython `major.minor` the
app bundles (see the root [README](../README.md#building)).

## How it works

- Profiles are read from `<Assistant>/Profiles/*.xml`.
- Hotkey actions are resolved as:
  - `Play Script: X` → script name
  - `L:<id>` (id < 3000) → action name from the Razor language pack
  - `L:3002xxx` → spell name from `spells.def`
  - `L:1044xxx` → Outlands command (see `EXTRA_ACTION_NAMES` to label these)

## Configuration

The Assistant directory is auto-detected from common Wine paths. If detection
fails, add your path to the `ASSISTANT_DIRS` list in `importer.py`.

To label unresolved Outlands commands (shown as `Action 1044081` etc.), add
entries to `EXTRA_ACTION_NAMES`, for example:

```python
EXTRA_ACTION_NAMES = {
    1044081: "Smoke Bomb",
    1044106: "Mount",
}
```
