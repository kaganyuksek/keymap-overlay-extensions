"""
Ultima Online Outlands (Razor) importer.

Reads the ClassicUO "Assistant" (Razor) hotkey profiles and generates the
overlay's keymap structure. Each profile becomes a profile entry; hotkeys are
grouped by category (Scripts / Spells / Actions).

The Assistant data directory is auto-detected. If detection fails, add your
path to ASSISTANT_DIRS below.
"""

import ctypes
import os
import re
import sys
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
    1060586: "Close Wounds",
    1060587: "Consecrate Weapon",
    1060592: "Noble Sacrifice",
    1060589: "Divine Fury",
    1060590: "Enemy of One",
    1060591: "Holy Light",
}

# Outlands Codex stances resolved by their real name instead of the generic
# "Swords Codex Stance in position N" string from the language file.
STANCE_NAMES = {
    # Swords (positions 1-5)
    2654: "Aggressive",
    2655: "Defensive",
    2656: "Cleave",
    2657: "Warrior",
    2658: "Flaying",
    # Shield (positions 1-5)
    2661: "Shield Bash",
    2662: "Warding",
    2663: "Testudo",
    2664: "Mirror",
    2665: "Bulwark",
}

# Outlands Codex abilities (the three selectable ability slots, in order:
# Lesser, Regular, Greater).
ABILITY_NAMES = {
    2625: "Spinslash",   # Lesser Ability
    2627: "Rend",        # Regular Ability
    2629: "Chop",        # Greater Ability
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
    # OEM keys fallback (used when the runtime layout mapping is unavailable).
    186: "OemSemicolon", 187: "Oemplus", 188: "Oemcomma", 189: "OemMinus",
    190: "OemPeriod", 191: "OemQuestion", 192: "Oemtilde",
    219: "OemOpenBrackets", 220: "OemPipe", 221: "OemCloseBrackets", 222: "OemQuotes",
}

_MOUSE_KEYS = {
    -1: "Wheel Up", -2: "Wheel Down", -3: "Mouse Middle",
    -4: "Mouse XButton1", -5: "Mouse XButton2",
}

# --- Runtime keyboard-layout mapping --------------------------------------
# Maps a virtual key code to the character it produces on the active keyboard
# layout. This is what makes OEM keys display correctly (e.g. Oemplus is '-'
# on a Turkish Q layout but '=' on a US layout).


def _keysym_to_char(keysym: int):
    if 0x20 <= keysym <= 0x7E or 0xA0 <= keysym <= 0xFF:
        return chr(keysym)
    if keysym >= 0x01000000:  # Unicode keysym
        cp = keysym & 0x00FFFFFF
        if cp < 0x110000:
            try:
                return chr(cp)
            except ValueError:
                return None
    # Legacy Latin-2/3/4 keysyms (e.g. Turkish 'ş'/'ğ' on a Turkish Q layout).
    if 0x0100 <= keysym <= 0x01FF:
        return _decode_iso(keysym & 0xFF, "iso8859-2")
    if 0x0200 <= keysym <= 0x02FF:
        return _decode_iso(keysym & 0xFF, "iso8859-3")
    if 0x0300 <= keysym <= 0x03FF:
        return _decode_iso(keysym & 0xFF, "iso8859-4")
    return None


def _decode_iso(byte: int, codec: str):
    if byte < 0xA0:
        return None
    try:
        return bytes([byte]).decode(codec)
    except (UnicodeDecodeError, LookupError):
        return None


# VK code -> X keycode for the standard evdev layout (scancode + 8).
_VK_TO_X_KEYCODE = {
    186: 47, 187: 21, 188: 59, 189: 20, 190: 60, 191: 61,
    192: 49, 219: 34, 220: 51, 221: 35, 222: 48,
}

_X11_VK = {}


def _x11_vk_to_char(code: int):
    if code not in _VK_TO_X_KEYCODE:
        return None
    if "dpy" not in _X11_VK:
        try:
            xlib = ctypes.CDLL("libX11.so.6")
            xlib.XOpenDisplay.restype = ctypes.c_void_p
            xlib.XOpenDisplay.argtypes = [ctypes.c_char_p]
            xlib.XDisplayKeycodes.argtypes = [
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_int),
                ctypes.POINTER(ctypes.c_int),
            ]
            xlib.XGetKeyboardMapping.restype = ctypes.POINTER(ctypes.c_ulong)
            xlib.XGetKeyboardMapping.argtypes = [
                ctypes.c_void_p, ctypes.c_ubyte, ctypes.c_int,
                ctypes.POINTER(ctypes.c_int),
            ]
            xlib.XFree.argtypes = [ctypes.c_void_p]
            dpy = xlib.XOpenDisplay(None)
            if not dpy:
                return None
            _X11_VK["dpy"] = dpy
            _X11_VK["xlib"] = xlib
        except OSError:
            return None
    xlib = _X11_VK["xlib"]
    dpy = _X11_VK["dpy"]

    if "mapping" not in _X11_VK:
        min_kc = ctypes.c_int()
        max_kc = ctypes.c_int()
        xlib.XDisplayKeycodes(dpy, ctypes.byref(min_kc), ctypes.byref(max_kc))
        per = ctypes.c_int()
        ptr = xlib.XGetKeyboardMapping(
            dpy, min_kc.value, max_kc.value - min_kc.value + 1, ctypes.byref(per)
        )
        if not ptr:
            return None
        n = (max_kc.value - min_kc.value + 1) * per.value
        mapping = [ptr[i] for i in range(n)]
        xlib.XFree(ptr)
        _X11_VK["mapping"] = mapping
        _X11_VK["min"] = min_kc.value
        _X11_VK["per"] = per.value

    keycode = _VK_TO_X_KEYCODE[code]
    idx = (keycode - _X11_VK["min"]) * _X11_VK["per"]
    if idx < 0 or idx >= len(_X11_VK["mapping"]):
        return None
    return _keysym_to_char(_X11_VK["mapping"][idx])


def _win32_vk_to_char(code: int):
    user32 = ctypes.windll.user32
    user32.GetKeyboardLayout.restype = ctypes.c_void_p
    user32.GetKeyboardLayout.argtypes = [ctypes.c_uint]
    user32.MapVirtualKeyExW.restype = ctypes.c_uint
    user32.MapVirtualKeyExW.argtypes = [
        ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p
    ]
    hkl = user32.GetKeyboardLayout(0)
    ch = user32.MapVirtualKeyExW(code, 2, hkl)  # MAPVK_VK_TO_CHAR
    if ch and ch < 0x110000:
        return chr(ch)
    return None


def vkey_to_char(code: int):
    if sys.platform.startswith("linux"):
        # Letters and digits are layout-stable on QWERTY; OEM keys are mapped
        # through X11 using the active layout.
        if 48 <= code <= 57 or 65 <= code <= 90:
            return chr(code)
        return _x11_vk_to_char(code)
    if sys.platform == "win32":
        return _win32_vk_to_char(code)
    return None


def _key_name(code: int) -> str:
    if code in _MOUSE_KEYS:
        return _MOUSE_KEYS[code]
    if 96 <= code <= 105:  # numpad 0-9
        return f"NumPad{code - 96}"
    if 112 <= code <= 123:  # F1-F12
        return f"F{code - 111}"
    # Character-producing keys: use the active keyboard layout.
    if (48 <= code <= 57) or (65 <= code <= 90) or (186 <= code <= 222):
        char = vkey_to_char(code)
        if char:
            return char
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
        if action_id in STANCE_NAMES:
            return "Actions", STANCE_NAMES[action_id]
        if action_id in ABILITY_NAMES:
            return "Actions", ABILITY_NAMES[action_id]
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
        return {"profiles": []}

    profiles_dir = assistant / "Profiles"
    lang = _parse_language(assistant / "Language" / "Razor_lang.enu")
    spells = _parse_spells(assistant / "spells.def")

    profiles = []
    for profile_path in sorted(profiles_dir.glob("*.xml")):
        profile = _parse_profile(profile_path, lang, spells)
        if profile is not None:
            profiles.append(profile)

    return {"profiles": profiles}
