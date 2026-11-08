"""The injected text: the header, the tree of names (every root entry, the first SHOWN entries of each root folder), the
empty map and the unavailable line."""

from __future__ import annotations

# Each root folder lists this many of its own entries, then counts the rest.
SHOWN = 6
HEADER = (
    f"Codebase map (every entry at this repository's root, and the first {SHOWN} entries of each folder under it;"
    " folders end in /; reuse what exists):"
)
EMPTY = "Codebase map: git lists no file in this repository's work tree."
UNAVAILABLE = "Codebase map unavailable: "


def render(entries: list[tuple[str, list[str] | None]]) -> str:
    """The tree: each root entry on its own line, a folder's own entries indented two spaces under it.

    entries is (name, children) per root entry, in order, a folder's name ending in /; children is the folder's own
    entries in order, None for a file."""
    if not entries:
        return EMPTY
    lines = [HEADER]
    for name, children in entries:
        lines.append(name)
        for child in (children or [])[:SHOWN]:
            lines.append(f"  {child}")
        if children and len(children) > SHOWN:
            lines.append(f"  … {len(children) - SHOWN} more")
    return "\n".join(lines)
