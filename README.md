# Keymap Overlay Extensions

Community plugins (importers) for
[Keymap Overlay](https://github.com/kaganyuksek/keymap-overlay).

A plugin reads hotkey data from an external source (for example, a game's
profile files) and generates the overlay's `data/keymap.json`. This keeps the
core app generic while game-specific import logic lives here.

## Installing a plugin

1. Install [Keymap Overlay](https://github.com/kaganyuksek/keymap-overlay).
2. Copy the plugin folder into the overlay's `plugins/` directory:

   ```bash
   git clone https://github.com/kaganyuksek/keymap-overlay-extensions.git
   cp -r keymap-overlay-extensions/uo_razor /path/to/keymap-overlay/plugins/
   ```

3. Run the overlay and use the tray's **Import** menu (or let `AUTO_IMPORT`
   plugins run automatically at startup).

See [PLUGINS.md](https://github.com/kaganyuksek/keymap-overlay/blob/main/PLUGINS.md)
in the main repository for the plugin API.

## Plugins

- **[uo_razor](uo_razor/)** — Ultima Online Outlands (Razor / ClassicUO
  Assistant) profile importer. Reads hotkey bindings from the Assistant
  profiles and groups them by category.
