"""Python package folders and the first line of each `__init__.py` docstring, read with `ast`."""

from __future__ import annotations

import ast
import os

from . import repo
from .render import NO_DOC, first_line, unreadable


def docstring_line(source: bytes, name: str) -> str:
    """The first line of the module docstring, NO_DOC without one, or an unreadable note for source ast rejects."""
    try:
        tree = ast.parse(source, filename=name)
    except (SyntaxError, ValueError, RecursionError, MemoryError) as error:
        where = f" at line {error.lineno}" if isinstance(error, SyntaxError) and error.lineno else ""
        return unreadable(f"{type(error).__name__}{where}")
    doc = ast.get_docstring(tree)
    return first_line(doc) if doc else NO_DOC


def entries(top: str, files: list[str]) -> list[tuple[str, str]]:
    """(folder, synopsis) for every tracked `__init__.py` still on disk, folders relative to top."""
    found = []
    for path in files:
        if os.path.basename(path) != "__init__.py":
            continue
        try:
            source = repo.front_door(top, path)
        except OSError as error:
            found.append((os.path.dirname(path) or ".", unreadable(str(error))))
            continue
        if source is None:
            continue  # tracked but deleted in the work tree: no package there now
        found.append((os.path.dirname(path) or ".", docstring_line(source, path)))
    return found
