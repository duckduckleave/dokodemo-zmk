#!/usr/bin/env python3
"""Apply presentation-only formatting to keymap YAML and SVG output."""

from pathlib import Path
import re
import sys

import yaml


LEGEND_HEIGHT = 68
LEGEND = """<g class="keymap-legend">
<rect x="20" y="3" width="692" height="60" rx="6" fill="#f6f8fa" stroke="#c9cccf"/>
<text x="30" y="15" style="font-size:11px;text-anchor:start">◆ GUI · ✣ Meh · ✦ Hyper · <tspan style="fill:#9333ea;font-weight:bold">◌ ODK outputs</tspan></text>
<text x="30" y="34" style="font-size:11px;text-anchor:start"><tspan style="fill:#2563eb;font-weight:bold">⌖ Nav</tspan> · <tspan style="fill:#d97706;font-weight:bold"># Symbols</tspan> · <tspan style="fill:#0f766e;font-weight:bold">∑ Math</tspan> · <tspan style="fill:#15803d;font-weight:bold">ƒ Fn</tspan> · <tspan style="fill:#be123c;font-weight:bold">✦ Hyper</tspan></text>
<text x="30" y="53" style="font-size:11px;text-anchor:start">◎ Focus · ≡ Group · ◇ Workspace · ▣ Monitor · ▱ Float · ⛶ Fullscreen</text>
</g>"""

TRIGGER_TYPES = {
    "⌖": "trigger-nav",
    "#": "trigger-symbols",
    "∑": "trigger-math",
    "ƒ": "trigger-fn",
    "✦": "trigger-hyper",
}


def format_yaml(path: Path) -> None:
    keymap = yaml.safe_load(path.read_text(encoding="utf-8"))

    layers = keymap.get("layers", {})
    layers.pop("CAD", None)

    base = layers.get("Base")
    accents = layers.pop("Accents", None)
    if base and accents:
        for position, base_key in enumerate(base):
            if not isinstance(base_key, dict):
                base_key = {"t": base_key}
                base[position] = base_key

            # Preserve ordinary shifted output without styling it as ODK output.
            if "s" in base_key:
                base_key["right"] = base_key.pop("s")

            accent_key = accents[position]
            if isinstance(accent_key, dict):
                if accent_key.get("type") == "trans":
                    continue
                accent_key = accent_key.get("t")
            if accent_key:
                base_key["s"] = accent_key

        # Highlight the sticky one-dead-key activator itself.
        base[8]["type"] = "odk"

    for layer in layers.values():
        for key in layer:
            if not isinstance(key, dict):
                continue
            trigger_type = TRIGGER_TYPES.get(key.get("h"))
            if trigger_type and key.get("type") not in {"held", "trans"}:
                key["type"] = trigger_type

    ordered_layers = {}
    for name in ("Base", "Symbols"):
        if name in layers:
            ordered_layers[name] = layers.pop(name)
    ordered_layers.update(layers)
    keymap["layers"] = ordered_layers

    keymap["combos"] = [
        combo for combo in keymap.get("combos", []) if "CAD" not in combo.get("l", [])
    ]

    path.write_text(
        yaml.safe_dump(keymap, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def format_svg(path: Path) -> None:
    svg = path.read_text(encoding="utf-8")
    opening_end = svg.index(">") + 1
    opening = svg[:opening_end]

    height = re.search(r'height="([\d.]+)"', opening)
    view_box = re.search(r'viewBox="([\d.-]+) ([\d.-]+) ([\d.]+) ([\d.]+)"', opening)
    if not height or not view_box:
        raise ValueError("Could not determine SVG dimensions")

    new_height = float(height.group(1)) + LEGEND_HEIGHT
    new_view_height = float(view_box.group(4)) + LEGEND_HEIGHT
    opening = opening.replace(
        height.group(0), f'height="{new_height:g}"', 1
    ).replace(
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
