# Keymap Overlay Extensions

Community plugins (importers) for
[Keymap Overlay](https://github.com/kaganyuksek/keymap-overlay).

A plugin reads hotkey data from an external source (for example, a game's
profile files) and generates the overlay's `data/keymap.json`. This keeps the
core app generic while game-specific import logic lives here.

## Installing a plugin

1. Install [Keymap Overlay](https://github.com/kaganyuksek/keymap-overlay).
2. Copy the plugin into the overlay's `plugins/` directory. Either drop the
   source folder/file directly, or use a compiled `.pyc`/`.pyz` (see
   [Building](#building)):

   ```bash
   git clone https://github.com/kaganyuksek/keymap-overlay-extensions.git
   cp -r keymap-overlay-extensions/uo_razor /path/to/keymap-overlay/plugins/
   ```

3. Run the overlay and use the tray's **Import** menu (or let `AUTO_IMPORT`
   plugins run automatically at startup).

See [PLUGINS.md](https://github.com/kaganyuksek/keymap-overlay/blob/main/PLUGINS.md)
in the main repository for the plugin API and the full list of supported
layouts (single file, folder, `.pyc`, `.pyz`/`.zip`).

## Plugins

- **[uo_razor](uo_razor/)** — Ultima Online Outlands (Razor / ClassicUO
  Assistant) profile importer. Reads hotkey bindings from the Assistant
  profiles and groups them by category.

## Versioning

Plugins in this repository are versioned to stay compatible with specific
Keymap Overlay releases.

- **Plugin version**: each plugin documents its own version in
  `uo_razor/README.md`. The overlay does not enforce it, but keep it in sync
  with the app version the plugin was tested against.
- **App compatibility**: the `import_keymap()` return shape is the public
  contract (`{"profiles": [...]}`). Breaking changes to this shape are released
  as a new app major/minor; plugins list the app version they require.
- **Python / bytecode version**: if you distribute a plugin as compiled
  bytecode (`.pyc` / `.pyz`), it **must** be built with the same CPython
  `major.minor` that the bundled Keymap Overlay executable embeds. Bytecode
  from a different Python version is silently ignored at load time. Check the
  release notes for the Python version a given app build bundles.

## Building

Build compiled plugins (`*.pyc` / `*.pyz`) to distribute without source. All
builds must target the app's embedded Python version.

### Single file

```bash
cd uo_razor
python -m py_compile importer.py
# produces __pycache__/importer.cpython-<ver>.pyc
cp __pycache__/importer.cpython-<ver>.pyc ../dist/uo_razor.pyc
```

### Folder

```bash
cd uo_razor
python -m py_compile importer.py
mkdir -p ../dist/uo_razor
cp __pycache__/importer.cpython-<ver>.pyc ../dist/uo_razor/importer.pyc
# copy any sibling helper modules the same way
```

### Archive (`.pyz`)

A `.pyz` is a zip whose root contains an `importer` module (entry point) plus
any sibling modules it imports. `zipimport` expects plain module names, so
rename the versioned `__pycache__` files first:

```bash
cd uo_razor
python -m py_compile importer.py
cp __pycache__/importer.cpython-<ver>.pyc importer.pyc
zip ../dist/uo_razor.pyz importer.pyc
```

The overlay discovers `dist/uo_razor.pyz`, executes the `importer` module, and
its `import_keymap()` output becomes the keymap.
