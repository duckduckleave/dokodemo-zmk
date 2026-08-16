# ZMK Configuration for DokoDemo

This repository contains the default DokoDemo firmware and keymap. The keymap
uses firmware-level Colemak-DH on a QWERTY host and is inspired by Selenium's
compact layer design.

Highlights:

- bilateral home-row mods in GUI, Ctrl, Alt order;
- sticky Shift plus dual Backspace/Space NavNum thumb keys;
- a shared navigation and numpad layer;
- Selenium-style Symbols and Fn/Media layers; and
- Caps Word, Escape, and Enter combos.

## Current keymap

![DokoDemo keymap](keymap-drawer/keymap.svg)

Regenerate the parsed keymap and SVG with:

```sh
make keymap
```

This uses the globally installed `keymap` executable. Saving
`keymap-drawer/keymap.yaml` in VS Code also redraws the SVG when the recommended
Run on Save extension is installed.

Create a three-page, print-ready A4 PDF with:

```sh
make keymap-print
```

The PDF is written to `keymap-drawer/keymap-print.pdf`. This target requires GNU
Make, the global `keymap` executable, Python 3 with PyYAML, and Chromium. Set
`CHROMIUM=/path/to/browser` if the executable has a different name.
