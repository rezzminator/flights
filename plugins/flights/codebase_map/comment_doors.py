"""Folders whose front door is index.ts/index.js or lib.rs/mod.rs, and that file's leading comment's first line.

Only the comment opening the file is read, as a comment: the standard library has no TypeScript or
Rust parser, and a leading comment needs no grammar beyond its delimiters, so no code is guessed at.
"""

from __future__ import annotations

import os

from . import repo
from .render import NO_DOC, first_line, unreadable

# Front-door file name -> comment style; within one folder the first listed wins.
DOORS = {"index.ts": "block", "index.js": "block", "lib.rs": "rust", "mod.rs": "rust"}


def _block(text: str) -> str | None:
    if text.startswith("/*"):
        end = text.find("*/")
        if end < 0:
            return None
        lines = [line.strip().lstrip("*").strip() for line in text[2:end].splitlines()]
    elif text.startswith("//"):
        lines = []
        for line in text.splitlines():
            if not line.strip().startswith("//"):
                break
            lines.append(line.strip()[2:].strip())
    else:
        return None
    # A JSDoc tag line (@module, @packageDocumentation) is markup, not the sentence.
    prose = "\n".join(line for line in lines if not line.startswith("@"))
    return first_line(prose) or None


def _rust(text: str) -> str | None:
    lines = []
    for line in text.splitlines():
        if not line.strip().startswith("//!"):
            break
        lines.append(line.strip()[3:].strip())
    return first_line("\n".join(lines)) or None


def leading_comment(text: str, style: str) -> str:
    """The first prose line of the comment opening text, else NO_DOC."""
    text = text.lstrip("﻿")
    if text.startswith("#!"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
    text = text.lstrip()
    # A TypeScript triple-slash directive (`/// <reference ... />`) opens many index.ts files and is no doc.
    while style == "block" and text.startswith("/// <"):
        text = text.split("\n", 1)[1].lstrip() if "\n" in text else ""
    found = _block(text) if style == "block" else _rust(text)
    return found or NO_DOC


def entries(top: str, files: list[str]) -> list[tuple[str, str]]:
    """(folder, synopsis) for every tracked front-door file still on disk, folders relative to top."""
    rank = {name: at for at, name in enumerate(DOORS)}
    doors: dict[str, str] = {}
    for path in files:
        name = os.path.basename(path)
        if name not in DOORS:
            continue
        folder = os.path.dirname(path) or "."
        if folder not in doors or rank[name] < rank[os.path.basename(doors[folder])]:
            doors[folder] = path
    found = []
    for folder, path in sorted(doors.items()):
        try:
            source = repo.front_door(top, path)
        except OSError as error:
            found.append((folder, unreadable(str(error))))
            continue
        if source is None:
            continue  # tracked but deleted in the work tree
        found.append((folder, leading_comment(source.decode("utf-8", "replace"), DOORS[os.path.basename(path)])))
    return found
