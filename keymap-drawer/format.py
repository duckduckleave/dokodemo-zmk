#!/usr/bin/env python3
"""Apply presentation-only formatting to keymap YAML and SVG output."""

from pathlib import Path
import re
import sys

import yaml


LEGEND_HEIGHT = 49
LEGEND = """<g class="keymap-legend">
<rect x="20" y="3" width="692" height="41" rx="6" fill="#f6f8fa" stroke="#c9cccf"/>
<text x="30" y="17" style="font-size:11px;text-anchor:start">⌃ Ctrl · ⌥ Alt · ◆ GUI · ⇧ Shift · <tspan style="fill:#9333ea;font-weight:bold">purple top = ODK output</tspan> · bottom = hold</text>
<text x="30" y="35" style="font-size:11px;text-anchor:start"><tspan style="fill:#2563eb;font-weight:bold">⌖ NavNum</tspan> · <tspan style="fill:#d97706;font-weight:bold"># Symbols</tspan> · <tspan style="fill:#15803d;font-weight:bold">fn Fn</tspan> · <tspan style="fill:#7c3aed;font-weight:bold">Gaming</tspan> · both inner thumbs = Fn</text>
</g>"""

TRIGGER_TYPES = {
    "⌖": "trigger-nav",
    "#": "trigger-symbols",
    "fn": "trigger-fn",
}

SPECIAL_TAPS = {
    "⇧", "⌫", "⎵", "⇥", "⏎", "⎋", "⌦",
    "↖", "↘", "⇞", "⇟", "↑", "↓", "←", "→",
    "⇧⎵", "⏮", "⏭", "⏯",
}


def add_type(key: dict, key_type: str) -> None:
    """Add a CSS type without discarding types assigned by keymap-drawer."""
    types = key.get("type", "").split()
    if key_type not in types:
        types.append(key_type)
    key["type"] = " ".join(types)


def format_yaml(path: Path) -> None:
    keymap = yaml.safe_load(path.read_text(encoding="utf-8"))
    layers = keymap.get("layers", {})

    # Present the persistent numeric mode as a lock of NavNum instead of the
    # parser's generic layer number + "toggle" label.
    nav_num = layers.get("NavNum")
    if nav_num and isinstance(nav_num[5], dict):
        nav_num[5] = {"t": "⌖", "h": "lock", "type": "trigger-nav nav-lock"}

    # Fold the one-shot accent layer into Base as purple shifted labels. This
    # keeps the diagram compact while showing every One Dead Key output at the
    # physical key that produces it.
    base = layers.get("Base")
    accents = layers.pop("Accents", None)
    if base and accents:
        for position, base_key in enumerate(base):
            if not isinstance(base_key, dict):
                base_key = {"t": base_key}
                base[position] = base_key

            # Keep punctuation morphs visible at the right of their base key.
            if "s" in base_key:
                base_key["right"] = base_key.pop("s")

            accent_key = accents[position]
            if isinstance(accent_key, dict):
                if accent_key.get("type") == "trans":
                    continue
                accent_key = accent_key.get("t")
            if accent_key:
                base_key["s"] = accent_key

        add_type(base[8], "odk")

    for layer in layers.values():
        for position, key in enumerate(layer):
            if not isinstance(key, dict):
                if key not in SPECIAL_TAPS:
                    continue
                key = {"t": key}
                layer[position] = key

            if key.get("t") in SPECIAL_TAPS:
                add_type(key, "special")

            trigger_type = TRIGGER_TYPES.get(key.get("h"))
            if key.get("h") == "fn":
                add_type(key, "fn-label")
            structural_types = set(key.get("type", "").split())
            if trigger_type and not structural_types.intersection({"held", "trans"}):
                add_type(key, trigger_type)

    # NumLock is a persistent helper for NavNum, not a separate conceptual
    # layer users need in the primary diagram.
    layers.pop("NumLock", None)

    ordered_layers = {}
    for name in ("Base", "Symbols", "NavNum", "Fn", "Gaming"):
        if name in layers:
            ordered_layers[name] = layers[name]
    keymap["layers"] = ordered_layers

    path.write_text(
        yaml.safe_dump(keymap, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def format_svg(path: Path) -> None:
    svg = path.read_text(encoding="utf-8")

    # keymap-drawer wraps custom SVGs in another <svg>; converting each custom
    # definition to a symbol makes <use> render consistently everywhere.
    for glyph in ("bluetooth", "gamepad"):
        svg = re.sub(
            rf'<svg id="{glyph}">\s*<svg viewBox="([^"]+)">(.*?)</svg>\s*</svg>',
            rf'<symbol id="{glyph}" viewBox="\1">\2</symbol>',
            svg,
            flags=re.DOTALL,
        )

    opening_end = svg.index(">") + 1
    opening = svg[:opening_end]

    height = re.search(r'height="([\d.]+)"', opening)
    view_box = re.search(r'viewBox="([\d.-]+) ([\d.-]+) ([\d.]+) ([\d.]+)"', opening)
    if not height or not view_box:
        raise ValueError("Could not determine SVG dimensions")

    new_height = float(height.group(1)) + LEGEND_HEIGHT
    new_view_height = float(view_box.group(4)) + LEGEND_HEIGHT
    opening = opening.replace(height.group(0), f'height="{new_height:g}"', 1).replace(
        view_box.group(0),
        f'viewBox="{view_box.group(1)} {view_box.group(2)} {view_box.group(3)} {new_view_height:g}"',
        1,
    )
    svg = opening + svg[opening_end:]

    anchors = [anchor for anchor in ("</defs>", "</style>") if anchor in svg]
    anchor_end = max(svg.index(anchor) + len(anchor) for anchor in anchors)
    svg = (
        svg[:anchor_end]
        + "\n"
        + LEGEND
        + f'\n<g transform="translate(0, {LEGEND_HEIGHT})">'
        + svg[anchor_end:-7]
        + "</g>\n</svg>\n"
    )
    path.write_text(svg, encoding="utf-8")


path = Path(sys.argv[1])
if path.suffix == ".yaml":
    format_yaml(path)
elif path.suffix == ".svg":
    format_svg(path)
else:
    raise ValueError(f"Unsupported file type: {path.suffix}")
