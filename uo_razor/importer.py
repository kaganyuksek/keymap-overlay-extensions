"""
Ultima Online Outlands (Razor) importer.

Reads the ClassicUO "Assistant" (Razor) hotkey profiles and generates the
overlay's keymap structure. Each profile becomes a character; hotkeys are
grouped by category (Scripts / Spells / Actions).

The Assistant data directory is auto-detected. If detection fails, add your
path to ASSISTANT_DIRS below.
"""

import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

PLUGIN_ID = "uo_outlands_razor"
PLUGIN_NAME = "Ultima Online Outlands (Razor)"
AUTO_IMPORT = True

# Candidate locations for the Assistant data directory.
ASSISTANT_DIRS = [
    # Linux (Lutris / Wine)
    Path.home() / "Games" / "ultima-online-outlands" / "drive_c"
    / "Program Files (x86)" / "Ultima Online Outlands" / "ClassicUO"
    / "Data" / "Plugins" / "Assistant",
    Path.home() / ".wine" / "drive_c" / "Program Files (x86)"
    / "Ultima Online Outlands" / "ClassicUO" / "Data" / "Plugins" / "Assistant",
    Path.home() / ".wine" / "drive_c" / "Program Files"
    / "Ultima Online Outlands" / "ClassicUO" / "Data" / "Plugins" / "Assistant",
    # Windows
    Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
    / "Ultima Online Outlands" / "ClassicUO" / "Data" / "Plugins" / "Assistant",
    Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    / "Ultima Online Outlands" / "ClassicUO" / "Data" / "Plugins" / "Assistant",
    Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
    / "Steam" / "steamapps" / "common" / "Ultima Online Outlands"
    / "ClassicUO" / "Data" / "Plugins" / "Assistant",
]

# Optional overrides for action ids that cannot be resolved automatically
# (e.g. Outlands commands stored as L:1044xxx).
EXTRA_ACTION_NAMES = {
    # 1044081: "Your command",
}

# --- Key / modifier mapping -----------------------------------------------

# Short labels for modifier keys shown in the key badge. Adjust to taste
# (e.g. use "Shift" for the full word or the unicode "⇧").
MODIFIER_LABELS = {
    "Ctrl": "Ctrl",
    "Alt": "Alt",
    "Shift": "Sh",
}

_SPECIAL_KEYS = {
    8: "Backspace", 9: "Tab", 13: "Enter", 16: "Shift", 17: "Ctrl",
    18: "Alt", 19: "Pause", 20: "CapsLock", 27: "Esc", 32: "Space",
    33: "PageUp", 34: "PageDown", 35: "End", 36: "Home",
    37: "Left", 38: "Up", 39: "Right", 40: "Down",
    44: "PrintScreen", 45: "Insert", 46: "Delete",
    # OEM keys: show the key name as-is; the produced character depends on the
    # keyboard layout (e.g. on a Turkish Q layout Oemplus is '-').
    186: "OemSemicolon", 187: "Oemplus", 188: "Oemcomma", 189: "OemMinus",
    190: "OemPeriod", 191: "OemQuestion", 192: "Oemtilde",
    219: "OemOpenBrackets", 220: "OemPipe", 221: "OemCloseBrackets", 222: "OemQuotes",
}


def _key_name(code: int) -> str:
    if 48 <= code <= 57:  # 0-9
        return chr(code)
    if 65 <= code <= 90:  # A-Z
        return chr(code)
    if 96 <= code <= 105:  # numpad 0-9
        return f"NumPad{code - 96}"
    if 112 <= code <= 123:  # F1-F12
        return f"F{code - 111}"
    mouse = {-1: "Wheel Up", -2: "Wheel Down", -3: "Mouse Middle", -4: "Mouse XButton1", -5: "Mouse XButton2"}
    if code in mouse:
        return mouse[code]
    return _SPECIAL_KEYS.get(code, f"Key({code})")


def _modifier_name(mod: int) -> str:
    parts = []
    if mod & 2:
        parts.append(MODIFIER_LABELS["Ctrl"])
    if mod & 1:
        parts.append(MODIFIER_LABELS["Alt"])
    if mod & 4:
        parts.append(MODIFIER_LABELS["Shift"])
    return "+".join(parts)


def _full_key(mod: int, code: int) -> str:
    modname = _modifier_name(mod)
    key = _key_name(code)
    return f"{modname}+{key}" if modname else key


# --- Language / spells resolution -----------------------------------------

def _parse_language(path: Path) -> dict:
    """Map action id -> name from the [strings] section of the language file."""
    result = {}
    if not path.is_file():
        return result
    in_strings = False
    for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = raw.strip()
        if line.startswith("[") and line.endswith("]"):
            in_strings = line == "[strings]"
            continue
        if not in_strings or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.isdigit():
            result[int(key)] = value.strip().lstrip(">").strip()
    return result


def _parse_spells(path: Path) -> dict:
    """Map global spell index -> name from spells.def."""
    result = {}
    if not path.is_file():
        return result
    index = 0
    for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 4:
            index += 1
            result[index] = parts[3]
    return result


def _resolve_action(raw: str, lang: dict, spells: dict) -> tuple[str, str]:
    """Return (category, label) for a hotkey action."""
    if raw.startswith("Play Script:"):
        script = raw[len("Play Script:"):].strip().replace("\\", "/")
        return "Scripts", Path(script).name
    if raw.startswith("L:"):
        try:
            action_id = int(raw[2:].strip())
        except ValueError:
            return "Actions", raw
        if 3002000 <= action_id < 3002200:  # spell cast
            idx = action_id - 3002000
            return "Spells", spells.get(idx, f"Spell {idx}")
        if action_id in EXTRA_ACTION_NAMES:
            return "Actions", EXTRA_ACTION_NAMES[action_id]
        if action_id in lang:
            return "Actions", lang[action_id]
        return "Actions", f"Action {action_id}"
    return "Actions", raw


# --- Profile parsing ------------------------------------------------------

def _parse_profile(path: Path, lang: dict, spells: dict) -> dict | None:
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return None

    groups: dict[str, list[dict]] = {"Scripts": [], "Spells": [], "Actions": []}
    for key_el in root.findall(".//hotkeys/key"):
        mod = int(key_el.get("mod", "0") or "0")
        code = int(key_el.get("key", "0") or "0")
        action = (key_el.text or "").strip()
        if not action:
            continue
        category, label = _resolve_action(action, lang, spells)
        groups[category].append(
            {"key": _full_key(mod, code), "label": label, "icon": None}
        )

    ordered_groups = [
        {"title": title, "hotkeys": hotkeys}
        for title, hotkeys in groups.items()
        if hotkeys
    ]
    if not ordered_groups:
        return None

    return {
        "id": path.stem,
        "name": path.stem,
        "groups": ordered_groups,
    }


def _find_assistant() -> Path | None:
    for candidate in ASSISTANT_DIRS:
        if (candidate / "Profiles").is_dir():
            return candidate
    return None


def import_keymap() -> dict:
    assistant = _find_assistant()
    if assistant is None:
        return {"characters": []}

    profiles_dir = assistant / "Profiles"
    lang = _parse_language(assistant / "Language" / "Razor_lang.enu")
    spells = _parse_spells(assistant / "spells.def")

    characters = []
    for profile_path in sorted(profiles_dir.glob("*.xml")):
        character = _parse_profile(profile_path, lang, spells)
        if character is not None:
            characters.append(character)

    return {"characters": characters}
