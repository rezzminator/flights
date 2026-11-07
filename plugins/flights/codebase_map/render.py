"""The injected text: the header, one line per package folder with the session's folder first, the budget and its footer."""

from __future__ import annotations

HEADER = (
    "Codebase map (each package folder and the first line of its front door's doc; reuse what exists,"
    " and read a folder's front door before its other files):"
)
EMPTY = (
    "Codebase map: this repository has no package folder"
    " (no Go package, Python package, index.ts/index.js or lib.rs/mod.rs is tracked)."
)
UNAVAILABLE = "Codebase map unavailable: "
NO_DOC = "(no front door doc)"
# The whole injected text stays within this many characters.
MAP_BUDGET = 4000
# One folder's synopsis is cut to this many characters, so one long doc cannot crowd out the rest.
SYNOPSIS_CAP = 200


def first_line(text: str) -> str:
    """The first non-blank line of text, stripped; empty when there is none."""
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return ""


def unreadable(reason: str) -> str:
    """A folder's line when its front door could not be read."""
    return f"(front door unreadable: {first_line(reason) or reason})"


def footer(left: int) -> str:
    return f"({left} more package folder{'' if left == 1 else 's'} not listed)"


def _synopsis(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= SYNOPSIS_CAP else text[: SYNOPSIS_CAP - 1] + "…"


def _in_subtree(folder: str, cwd: str) -> bool:
    return cwd == "." or folder == cwd or folder.startswith(cwd + "/")


def render(entries: list[tuple[str, str]], cwd: str, budget: int) -> str:
    """The map: cwd's subtree first (both groups by folder name), cut to budget characters with a footer counting the rest.

    cwd is the session's folder relative to the repository's top level ("." for the top).
    """
    if not entries:
        return EMPTY
    ordered = sorted(entries, key=lambda entry: (not _in_subtree(entry[0], cwd), entry[0]))
    lines = [f"{'.' if folder == '.' else folder}/: {_synopsis(text)}" for folder, text in ordered]
    whole = "\n".join([HEADER, *lines])
    if len(whole) <= budget:
        return whole
    # Cut: the most leading lines that still leave room for the footer counting the rest.
    kept, size = 0, len(HEADER)
    while kept < len(lines) and size + 1 + len(lines[kept]) + 1 + len(footer(len(lines) - kept - 1)) <= budget:
        size += 1 + len(lines[kept])
        kept += 1
    return "\n".join([HEADER, *lines[:kept], footer(len(lines) - kept)])
