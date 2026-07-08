"""Convert ViZDoom buffers into a compact ASCII grid (text-ASCII modality).

Follows the DOOM-Mistral / SauerkrautLM approach of a downsampled character
grid. Works on plain numpy arrays so it can be tested without the engine.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

DEFAULT_ROWS = 32
DEFAULT_COLS = 64

LEGEND = {
    ".": "floor / empty",
    "#": "wall / obstacle",
    "Z": "Zombieman",
    "S": "ShotgunGuy",
    "I": "Imp",
    "C": "Cacodemon",
    "D": "Demon / Pinky",
    "E": "other enemy",
    "+": "pickup / item",
    "^": "player facing (center)",
}

# Map ViZDoom object names -> legend chars.
_OBJECT_CHARS = {
    "Zombieman": "Z",
    "ShotgunGuy": "S",
    "DoomImp": "I",
    "Imp": "I",
    "Cacodemon": "C",
    "Demon": "D",
    "Spectre": "D",
}

_ITEM_HINTS = ("Bonus", "Health", "Armor", "Ammo", "Clip", "Shell", "Medikit", "Stimpack")


def _object_to_char(object_name: str) -> str:
    if object_name in _OBJECT_CHARS:
        return _OBJECT_CHARS[object_name]
    if any(hint in object_name for hint in _ITEM_HINTS):
        return "+"
    if object_name in ("DoomPlayer", "Player"):
        return "^"
    return "E"


@dataclass
class LabelInfo:
    """Mirror of a ViZDoom ``state.labels`` entry (subset we use)."""

    value: int
    object_name: str


def encode(
    labels_buffer: np.ndarray,
    labels: list[LabelInfo],
    depth_buffer: np.ndarray | None = None,
    rows: int = DEFAULT_ROWS,
    cols: int = DEFAULT_COLS,
    wall_depth_threshold: int = 32,
) -> str:
    """Return a ``rows``x``cols`` ASCII grid string.

    labels_buffer: HxW array of label values (0 = background).
    labels: list of LabelInfo mapping value -> object_name.
    depth_buffer: optional HxW depth (smaller = closer). Used to mark walls.
    """
    value_to_char = {li.value: _object_to_char(li.object_name) for li in labels}

    h, w = labels_buffer.shape
    cell_h = max(1, h // rows)
    cell_w = max(1, w // cols)

    grid = [["." for _ in range(cols)] for _ in range(rows)]

    for r in range(rows):
        for c in range(cols):
            y0, y1 = r * cell_h, min(h, (r + 1) * cell_h)
            x0, x1 = c * cell_w, min(w, (c + 1) * cell_w)
            block = labels_buffer[y0:y1, x0:x1]

            # Dominant non-zero label in the cell wins.
            nonzero = block[block > 0]
            if nonzero.size > 0:
                vals, counts = np.unique(nonzero, return_counts=True)
                dominant = int(vals[int(np.argmax(counts))])
                grid[r][c] = value_to_char.get(dominant, "E")
            elif depth_buffer is not None:
                dblock = depth_buffer[y0:y1, x0:x1]
                if dblock.size and float(np.mean(dblock)) < wall_depth_threshold:
                    grid[r][c] = "#"

    # Mark the player's forward view: center column of the bottom-middle.
    grid[rows - 1][cols // 2] = "^"

    return "\n".join("".join(row) for row in grid)
