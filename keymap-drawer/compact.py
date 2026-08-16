#!/usr/bin/env python3
"""Draw every user-facing layer on one shareable physical keyboard."""

from __future__ import annotations

from html import escape
import json
from math import hypot
from pathlib import Path
import sys

import yaml


KEY_SIZE = 108
MATRIX_PITCH = 108
MARGIN_X = 42
HEADER_H = 72
SPLIT_GAP = 280
CANVAS_H = 670

LAYER_SLOTS = {
    "Symbols": ("tl", "symbols", 19.0),
    "NavNum": ("tr", "navnum", 20.0),
    "Fn": ("bl", "fn", 14.5),
}

HOLD_LABELS = {
    "◆": "◆",
    "⌃": "⌃",
    "⌥": "⌥",
    "⌖": "⌖",
    "#": "#",
    "sticky": "⇧•",
}

SHORT_LABELS = {
    "Scroll": "ScrLk",
    "Print": "PrtSc",
    "Insert": "Ins",
    "Studio 🔓": "Studio🔓",
    "1 / ⇧ Clear": "1/⇧clr",
    "▽": "·",
}


def key_label(value: object) -> tuple[str, str]:
    """Return compact tap and hold labels from a keymap-drawer key value."""
    if isinstance(value, dict):
        tap = value.get("t", "")
        hold = value.get("h", "")
        if not tap and "held" in str(value.get("type", "")).split():
            tap = "●"
    else:
        tap, hold = value, ""

    tap = SHORT_LABELS.get(str(tap), str(tap))
    hold = SHORT_LABELS.get(str(hold), str(hold))
    return tap, hold


def fitted_size(value: str, maximum: float, width: float, minimum: float = 9.2) -> float:
    """Approximate a monospace fit without browser-dependent measurement."""
    if not value:
        return maximum
    return max(minimum, min(maximum, width / (len(value) * 0.61)))


def svg_text(
    x: float,
    y: float,
    value: str,
    css_class: str,
    *,
    anchor: str = "middle",
    size: float = 14,
) -> str:
    return (
        f'<text x="{x:g}" y="{y:g}" class="{css_class}" '
        f'text-anchor="{anchor}" font-size="{size:g}">{escape(value)}</text>'
    )


def physical_center(position: dict) -> tuple[float, float, float]:
    """Return a compact, readable projection of the canonical Ergogen layout."""
    row = int(position["row"])
    column = int(position["col"])
    first_center = MARGIN_X + KEY_SIZE / 2
    left_inner = first_center + 4 * MATRIX_PITCH
    right_inner = left_inner + KEY_SIZE + SPLIT_GAP

    if row < 3:
        # Preserve the characteristic column stagger but remove splay: the
        # drawing is a reference card, so aligned columns scan more quickly.
        stagger = (118, 56, 34, 52, 62)
        if column <= 4:
            x = first_center + column * MATRIX_PITCH
            y = HEADER_H + stagger[column] + row * KEY_SIZE
        else:
            mirrored_column = 9 - column
            x = right_inner + (column - 5) * MATRIX_PITCH
            y = HEADER_H + stagger[mirrored_column] + row * KEY_SIZE
        return x, y, 0

    thumb_positions = {
        3: (left_inner + 6, HEADER_H + 433, 10),
        4: (left_inner + 122, HEADER_H + 461, 18),
        5: (right_inner - 122, HEADER_H + 461, -18),
        6: (right_inner - 6, HEADER_H + 433, -10),
    }
    return thumb_positions[column]


def draw_bluetooth(x: float, y: float, profile: str, css_class: str) -> str:
    profile_size = fitted_size(profile, 14, 44, 9)
    return (
        f'<use href="#bluetooth" x="{x:g}" y="{y - 11:g}" width="11" height="22" class="{css_class}"/>'
        + svg_text(x + 15, y, profile, css_class, anchor="start", size=profile_size)
    )


def draw_key(position: dict, center: tuple[float, float, float], index: int, layers: dict[str, list]) -> str:
    cx, cy, rotation = center
    half = KEY_SIZE / 2
    out = [f'<g transform="translate({cx:g} {cy:g}) rotate({rotation:g})" class="key key-{index}">']
    out.append(f'<rect x="{-half:g}" y="{-half:g}" width="{KEY_SIZE}" height="{KEY_SIZE}" rx="10"/>')

    base_tap, base_hold = key_label(layers["Base"][index])
    if base_hold == "sticky":
        base_tap, base_hold = "⇧•", ""
    base_y = -13 if base_hold else 7
    out.append(svg_text(0, base_y, base_tap, "base", size=fitted_size(base_tap, 29, 72, 14)))
    if base_hold:
        hold_label = HOLD_LABELS.get(base_hold, base_hold)
        badge_width = min(84, max(42, len(hold_label) * 7.8 + 17))
        badge_class = "hold-badge"
        if base_hold == "⌖":
            badge_class += " nav-hold"
        elif base_hold == "#":
            badge_class += " symbol-hold"
        out.append(f'<rect x="{-badge_width / 2:g}" y="6" width="{badge_width:g}" height="29" rx="14.5" class="{badge_class}"/>')
        if base_hold == "⌖":
            out.append('<use href="#navpad" x="-10" y="11" width="20" height="20" class="navnum"/>')
        else:
            out.append(svg_text(0, 21, hold_label, "base-hold", size=fitted_size(hold_label, 15.5, badge_width - 10, 10.5)))

    slots = {
        "tl": (-half + 9, -half + 17, "start"),
        "tr": (half - 9, -half + 17, "end"),
        "bl": (-half + 9, half - 11, "start"),
        "br": (half - 9, half - 11, "end"),
    }
    for layer_name, (slot, css_class, max_size) in LAYER_SLOTS.items():
        value = layers[layer_name][index]
        tap, hold = key_label(value)
        x, y, anchor = slots[slot]

        if tap == "$$bluetooth$$":
            out.append(draw_bluetooth(x, y, hold, css_class))
            continue

        # Fn-layer holds repeat the base/QWERTY modifier structure and obscure
        # the actual Fn action, so the composite only shows the tap there.
        if layer_name == "Fn" or hold == "fn":
            rendered = tap
        elif hold == "lock" and tap == "⌖":
            out.append(f'<use href="#navpad" x="{x:g}" y="{y - 13:g}" width="16" height="16" class="navnum"/>')
            out.append(svg_text(x + 19, y, "lock", "navnum", anchor="start", size=12))
            continue
        elif hold == "lock":
            rendered = f"{tap} lock"
        else:
            rendered = f"{tap}/{hold}" if hold else tap
        if rendered in {"·", "●"}:
            continue
        out.append(
            svg_text(
                x,
                y,
                rendered,
                css_class,
                anchor=anchor,
                size=fitted_size(rendered, max_size, 48, 8.8),
            )
        )

    out.append("</g>")
    return "\n".join(out)


def mock_key(center_x: float, center_y: float) -> str:
    """A single key in the split explains every fixed legend position."""
    return f'''<g class="mock-key" transform="translate({center_x:g} {center_y:g})">
<rect x="-70" y="-66" width="140" height="132" rx="13" class="mock-cap"/>
{svg_text(0, -12, "BASE", "mock-base", size=22)}
<rect x="-34" y="4" width="68" height="25" rx="12.5" class="hold-badge"/>
{svg_text(0, 17, "HOLD", "base-hold", size=12)}
<g class="mock-pill symbols"><rect x="-130" y="-78" width="96" height="25" rx="12.5"/>{svg_text(-82, -65, "SYMBOLS ↖", "", size=12)}</g>
<g class="mock-pill navnum"><rect x="34" y="-78" width="96" height="25" rx="12.5"/>{svg_text(82, -65, "↗ NAVNUM", "", size=12)}</g>
<g class="mock-pill fn"><rect x="-101" y="53" width="66" height="25" rx="12.5"/>{svg_text(-68, 66, "FN ↙", "", size=12.5)}</g>
<g class="modifier-legend">
{svg_text(0, 97, "center = tap  ·  badge = hold", "legend-help", size=14)}
{svg_text(0, 120, "◆ GUI   ⌃ CTRL   ⌥ ALT", "modifier-key", size=15)}
{svg_text(0, 143, "⇧•  sticky Shift (next key)", "sticky-key", size=14)}
</g>
<g class="combo-key">
{svg_text(-68, 171, "⎋", "combo-key-icon", size=21)}
{svg_text(-48, 171, "ESCAPE", "combo-key-name", anchor="start", size=13.5)}
{svg_text(34, 171, "↵", "combo-key-icon", size=22)}
{svg_text(55, 171, "ENTER", "combo-key-name", anchor="start", size=13.5)}
{svg_text(0, 195, "Z + / → CAPS WORD  ·  ALL LAYERS", "caps-key-help", size=13)}
</g>
<g class="activation-key">
{svg_text(-8, 222, "hold # → Symbols", "symbols", anchor="end", size=13)}
{svg_text(8, 222, "hold", "navnum", anchor="start", size=13)}
<use href="#navpad" x="42" y="214" width="16" height="16" class="navnum"/>
{svg_text(62, 222, "→ NavNum", "navnum", anchor="start", size=13)}
{svg_text(0, 246, "hold both inner thumbs → Fn", "fn-activation", size=14)}
</g>
</g>'''


def gaming_callout(target_x: float, target_y: float, width: float) -> str:
    """Explain the gaming layer once and point back to its physical combo."""
    x = width - 315
    y = 524
    return f'''<g class="gaming-callout">
<path d="M {target_x - 14:g} {target_y + 10:g} L {x + 24:g} {y - 5:g}"/>
<use href="#gamepad" x="{x:g}" y="{y - 11:g}" width="25" height="25"/>
{svg_text(x + 34, y + 1, "GAMING", "gaming-title", anchor="start", size=14)}
{svg_text(x + 34, y + 24, "toggle: . + / combo", "gaming-copy", anchor="start", size=14)}
{svg_text(x + 34, y + 45, "QWERTY · instant left keys", "gaming-copy", anchor="start", size=14)}
{svg_text(x + 34, y + 66, "left thumbs: ⇧ + Space", "gaming-copy", anchor="start", size=14)}
</g>'''


def icon_badge(x: float, y: float, icon: str, css_class: str, width: float = 36) -> str:
    """Draw a standalone icon pill without implying extra key connections."""
    return f'''<g class="combo-bridge {css_class}">
<rect x="{x - width / 2:g}" y="{y - 14:g}" width="{width:g}" height="28" rx="14"/>
<use href="#{icon}" x="{x - 10:g}" y="{y - 10:g}" width="20" height="20" class="{css_class}"/>
</g>'''


def adjacent_combo(
    a: tuple[float, float, float],
    b: tuple[float, float, float],
    label: str,
    css_class: str,
    *,
    width: float = 58,
    y_offset: float = 0,
    icon: str = "",
    label_size: float = 13,
) -> str:
    x = (a[0] + b[0]) / 2
    y = (a[1] + b[1]) / 2 + y_offset
    distance = hypot(b[0] - a[0], b[1] - a[1])
    unit_x = (b[0] - a[0]) / distance
    unit_y = (b[1] - a[1]) / distance
    start_x, start_y = a[0] + unit_x * 47, a[1] + unit_y * 47
    end_x, end_y = b[0] - unit_x * 47, b[1] - unit_y * 47
    icon_svg = ""
    label_x = x
    if icon:
        icon_svg = f'<use href="#{icon}" x="{x - 13:g}" y="{y - 10:g}" width="20" height="20" class="{css_class}"/>'
        label_x = x + 9
    return f'''<g class="combo-bridge {css_class}">
<path d="M {start_x:g} {start_y:g} L {x:g} {y:g} L {end_x:g} {end_y:g}"/>
<rect x="{x - width / 2:g}" y="{y - 14:g}" width="{width:g}" height="28" rx="14"/>
{icon_svg}{svg_text(label_x, y + .5, label, "combo-label", size=label_size)}
</g>'''


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit("usage: compact.py KEYMAP_YAML LAYOUT_JSON OUTPUT_SVG")

    keymap_path, layout_path, output_path = map(Path, sys.argv[1:])
    keymap = yaml.safe_load(keymap_path.read_text(encoding="utf-8"))
    layout_data = json.loads(layout_path.read_text(encoding="utf-8"))
    positions = layout_data["layouts"]["dokodemo"]["layout"]
    layers = keymap["layers"]

    required_layers = ("Base", *LAYER_SLOTS)
    missing = [name for name in required_layers if name not in layers]
    if missing:
        raise ValueError(f"Missing layers for compact keymap: {', '.join(missing)}")
    if any(len(layers[name]) != len(positions) for name in required_layers):
        raise ValueError("Layer and physical-layout key counts differ")

    centers = [physical_center(position) for position in positions]
    left_edge = min(center[0] - KEY_SIZE / 2 for center in centers)
    right_edge = max(center[0] + KEY_SIZE / 2 for center in centers)
    width = left_edge + right_edge
    center_x = width / 2
    keys = "\n".join(
        draw_key(position, centers[index], index, layers)
        for index, position in enumerate(positions)
    )
    gaming_offset = 18
    gaming_x = (centers[28][0] + centers[29][0]) / 2
    gaming_y = (centers[28][1] + centers[29][1]) / 2 + gaming_offset
    combo_lines = "\n".join(
        (
            adjacent_combo(centers[21], centers[22], "⎋", "combo-default", width=38, label_size=21),
            adjacent_combo(centers[27], centers[28], "↵", "combo-default", width=38, label_size=22),
            icon_badge(gaming_x, gaming_y, "gamepad", "gaming-combo"),
            adjacent_combo(centers[31], centers[32], "fn", "fn-combo", width=48, label_size=13),
        )
    )

    svg = f'''<svg width="{width:g}" height="{CANVAS_H}" viewBox="0 0 {width:g} {CANVAS_H}" xmlns="http://www.w3.org/2000/svg">
<title>DokoDemo compact composite keymap</title>
<defs>
  <filter id="shadow" x="-20%" y="-20%" width="140%" height="150%"><feDropShadow dx="0" dy="2" stdDeviation="2" flood-color="#000" flood-opacity=".28"/></filter>
  <symbol id="bluetooth" viewBox="0 0 256 512"><path fill="currentColor" d="M164.9 260L257.5 156.7 111.6 0 111.6 206.3 25.4 120.2-6 151.6 102.1 260-6 368.4 25.4 399.8 111.6 313.7 114.3 512 262.8 363.4 164.9 260zm40.9-103-50 50-.3-100.3 50.3 50.3zm-50 156 50 50-50.3 50.3.3-100.3z"/></symbol>
  <symbol id="navpad" viewBox="0 0 24 24"><path fill="currentColor" d="M12 1.5 7.5 7h9L12 1.5ZM12 22.5 16.5 17h-9l4.5 5.5ZM1.5 12 7 16.5v-9L1.5 12ZM22.5 12 17 7.5v9l5.5-4.5Z"/><circle cx="12" cy="12" r="2.2" fill="currentColor"/></symbol>
  <symbol id="gamepad" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" d="M8 8h8a5 5 0 0 1 4.7 3.3l1.1 3.1a3 3 0 0 1-5.2 2.8L15 15H9l-1.6 2.2a3 3 0 0 1-5.2-2.8l1.1-3.1A5 5 0 0 1 8 8Z M7 11v4 M5 13h4 M16.5 11.5h.01 M18.5 13.5h.01"/></symbol>
</defs>
<style>
  svg {{ font-family: SFMono-Regular,Consolas,Liberation Mono,Menlo,monospace; fill: #f8fafc; background: #181d27; }}
  .background {{ fill: #181d27; }}
  .key {{ filter: url(#shadow); }}
  .key rect {{ fill: #252c38; stroke: #526071; stroke-width: 1.6; }}
  text {{ dominant-baseline: middle; }}
  .base {{ fill: #f8fafc; font-weight: 700; }}
  .key rect.hold-badge, .mock-key rect.hold-badge {{ fill: #111827; stroke: #94a3b8; stroke-width: 1.7; }}
  .key rect.hold-badge.nav-hold {{ stroke: #60a5fa; }}
  .key rect.hold-badge.symbol-hold {{ stroke: #fbbf24; }}
  .base-hold {{ fill: #e2e8f0; font-weight: 750; letter-spacing: -.25px; }}
  .symbols {{ fill: #fbbf24; color: #fbbf24; font-weight: 700; }}
  .navnum {{ fill: #60a5fa; color: #60a5fa; font-weight: 750; }}
  .fn {{ fill: #86b99c; color: #86b99c; font-weight: 600; }}
  .gaming {{ fill: #a98ac2; color: #a98ac2; font-weight: 550; }}
  .title {{ font: 750 27px system-ui,sans-serif; letter-spacing: -.3px; }}
  .subtitle {{ font: 12px system-ui,sans-serif; fill: #9aa7b7; letter-spacing: .6px; }}
  .mock-cap {{ fill: #222a35; stroke: #7b899b; stroke-width: 1.8; filter: url(#shadow); }}
  .mock-base {{ fill: #f8fafc; font-weight: 750; }}
  .mock-pill rect {{ fill: #181d27; stroke: currentColor; stroke-width: 1.5; }}
  .mock-pill text {{ fill: currentColor; font-family: system-ui,sans-serif; font-weight: 700; }}
  .mock-pill.fn, .mock-pill.gaming {{ opacity: .78; }}
  .legend-help {{ fill: #b3bdc9; font-family: system-ui,sans-serif; }}
  .modifier-key {{ fill: #cbd5e1; font-family: system-ui,sans-serif; font-weight: 700; }}
  .sticky-key {{ fill: #b3bdc9; font-family: system-ui,sans-serif; font-weight: 650; }}
  .combo-key-icon {{ fill: #7dd3fc; font-family: system-ui,sans-serif; font-weight: 750; }}
  .combo-key-name {{ fill: #dbe4ee; font-family: system-ui,sans-serif; font-weight: 700; letter-spacing: .4px; }}
  .caps-key-help {{ fill: #94a3b8; font-family: system-ui,sans-serif; }}
  .fn-activation {{ fill: #9bc9ac; font-family: system-ui,sans-serif; font-weight: 650; }}
  .gaming-callout {{ color: #a98ac2; }}
  .gaming-callout path {{ fill: none; stroke: #82669a; stroke-width: 1.8; stroke-linecap: round; }}
  .gaming-title {{ fill: #a98ac2; font-family: system-ui,sans-serif; font-weight: 750; letter-spacing: .8px; }}
  .gaming-copy {{ fill: #bac2cc; font-family: system-ui,sans-serif; }}
  .combo-bridge path {{ fill: none; stroke-width: 4; stroke-linecap: round; }}
  .combo-bridge rect {{ fill: #111827; stroke-width: 2.2; }}
  .combo-default path, .combo-default rect {{ stroke: #38bdf8; }}
  .gaming-combo path, .gaming-combo rect {{ stroke: #a98ac2; }}
  .fn-combo path, .fn-combo rect {{ stroke: #78a98a; }}
  .gaming-combo {{ color: #d8b4fe; }}
  .combo-label {{ fill: #f8fafc; font-family: system-ui,sans-serif; font-weight: 750; letter-spacing: .15px; }}
</style>
<rect class="background" width="100%" height="100%" rx="14"/>
<text x="36" y="29" class="title">DokoDemo · Colemak-DH</text>
{keys}
{combo_lines}
{mock_key(center_x, 160)}
{gaming_callout(gaming_x, gaming_y, width)}
</svg>
'''
    output_path.write_text(svg, encoding="utf-8")


if __name__ == "__main__":
    main()
