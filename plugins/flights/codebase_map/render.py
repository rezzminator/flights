"""The injected text: the header naming the order, one line per package folder hottest first (the session's folder
first when no package folder was read yet), the budget and its footer."""

from __future__ import annotations

_HEADER_REST = (
    "each package folder and the first line of its front door's doc; reuse what exists,"
    " and read a folder's front door before its other files):"
)
# The header when some package folder has been read: the hottest first.
HOT_HEADER = "Codebase map (hottest first, by how often this repository's files are read, recent reads weighing more; " + _HEADER_REST
# The header when none has: the session's folder first, then by name.
COLD_HEADER = "Codebase map (no read history yet: the session's folder first, then by name; " + _HEADER_REST
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


def render(entries: list[tuple[str, str]], cwd: str, budget: int, heat: dict[str, float] | None = None) -> str:
    """The map: the hottest folder first, then cwd's subtree, then by folder name; cut to budget characters, the coldest
    lines first, with a footer counting them.

    cwd is the session's folder relative to the repository's top level ("." for the top); heat is each folder's read
    heat, a folder it leaves out reads as 0.
    """
    if not entries:
        return EMPTY
    heat = heat or {}
    header = HOT_HEADER if any(heat.get(folder, 0.0) > 0 for folder, _ in entries) else COLD_HEADER
    ordered = sorted(entries, key=lambda entry: (-heat.get(entry[0], 0.0), not _in_subtree(entry[0], cwd), entry[0]))
    lines = [f"{'.' if folder == '.' else folder}/: {_synopsis(text)}" for folder, text in ordered]
    whole = "\n".join([header, *lines])
    if len(whole) <= budget:
        return whole
    # Cut: the most leading lines that still leave room for the footer counting the rest.
    kept, size = 0, len(header)
    while kept < len(lines) and size + 1 + len(lines[kept]) + 1 + len(footer(len(lines) - kept - 1)) <= budget:
        size += 1 + len(lines[kept])
        kept += 1
    return "\n".join([header, *lines[:kept], footer(len(lines) - kept)])
