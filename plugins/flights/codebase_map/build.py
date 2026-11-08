"""A repository's map entries: the names at its root and in each root folder, from the paths git lists."""

from __future__ import annotations

from . import repo

# A background build's own bound for each git command it runs.
BUILD_TIMEOUT = 120.0


def _ordered(names: dict[str, bool]) -> list[str]:
    """Folders first, then files, each group by name in byte order (str order is code point order, UTF-8's byte
    order); a folder's name ends in /."""
    folders = sorted(name for name, is_folder in names.items() if is_folder)
    files = sorted(name for name, is_folder in names.items() if not is_folder)
    return [f"{name}/" for name in folders] + files


def entries(top: str, env: dict[str, str]) -> list[tuple[str, list[str] | None]]:
    """(name, children) per root entry, in render order; children is a root folder's own entries in the same order,
    None for a file."""
    root: dict[str, bool] = {}
    inside: dict[str, dict[str, bool]] = {}
    for path, is_folder in repo.listed_paths(top, env, BUILD_TIMEOUT):
        parts = path.split("/")
        root[parts[0]] = root.get(parts[0], False) or len(parts) > 1 or is_folder
        if len(parts) > 1:
            children = inside.setdefault(parts[0], {})
            children[parts[1]] = children.get(parts[1], False) or len(parts) > 2 or is_folder
    return [(name, _ordered(inside.get(name.rstrip("/"), {})) if name.endswith("/") else None) for name in _ordered(root)]
