"""The map text: ponytail's codebase map, ported from its hooks/ponytail-map.js (buildMap, namesIn) to stdlib Python.

Ported from ponytail @ 96608e078b2d5ea607c5c3b8b5a54d1c1fba6846, MIT License, Copyright (c) 2026 DietrichGebert; the
notice is in the plugin's THIRD_PARTY_NOTICES.md. The port keeps its behaviour: the top-level functions, classes and
exports of the tracked source files, one line per folder, inside a 2000-character budget, shared code first. Each JS
regex is rewritten so Python matches what V8 does: ASCII \\w, JS's \\s and trim set, and multiline ^ after \\r, \\u2028
and \\u2029 too.
"""

from __future__ import annotations

import os
import posixpath
import re
import stat

from . import repo

# A background build's own bound for the git command it runs.
BUILD_TIMEOUT = 120.0
BUDGET = 2000
MAX_FILES = 4000
# JS reads each file whole and keeps its first 65536 UTF-16 code units; this many bytes always hold them.
READ_BYTES = 65536 * 4
HEADER = "Codebase map (what already exists; reuse it, read a file only when you need its details):"

# JS's \s and String.prototype.trim set: its WhiteSpace and LineTerminator code points.
JS_SPACE = "\t\n\v\f\r                  　﻿"
_S = f"[{JS_SPACE}]"
# JS's multiline ^: the start, or after any LineTerminator (Python's re.M ^ follows \n only).
_BOL = "(?:^|(?<=[\r  ]))"


def _js(pattern: str, flags: int = 0) -> re.Pattern:
    """A JS regex literal's source compiled to match as V8 does: \\s as JS's set, ASCII \\w, a leading ^ as JS's."""
    if flags & re.M and pattern.startswith("^"):
        pattern = _BOL + pattern[1:]
    return re.compile(pattern.replace(r"\s", _S), flags | re.A)


SRC = _js(r"\.(py|js|jsx|mjs|cjs|ts|tsx|go|rs|rb|java|kt|php|swift|cs)\Z")
SKIP_DIR = _js(r"(^|/)(node_modules|\.git|dist|build|out|vendor|venv|\.venv|__pycache__|coverage|\.next|target|migrations|versions|fixtures|tests?|__tests__|spec)(/|\Z)")
SKIP_FILE = _js(r"(^|/)(test_[^/]*|[^/]*(_test|\.test|\.spec|\.gen|\.min|\.d)\.[a-z]+)\Z")
NAME = _js(r"^(?:type\s+)?(?:[\w$]+\s+as\s+)?([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)?)\Z")
SAFE_PATH = _js(r"^[\w.@+$()\[\]/-]+\Z")
SHARED = _js(r"(util|helper|lib|common|shared|service|component|hook|core|model|schema|api)", re.I)

_M = re.M
PATTERNS = {
    "py": [_js(r"^(?:async\s+)?def\s+([A-Za-z]\w*)", _M), _js(r"^class\s+([A-Za-z]\w*)", _M)],
    "js": [_js(r"^export\s+(?:default\s+)?(?:async\s+)?(?:function\*?|class|const|let|var|interface|type|enum)\s+([A-Za-z_$][\w$]*)", _M),
           _js(r"^export\s*\{([^}]*)\}", _M)],
    "go": [_js(r"^func\s+(?:\([^)]*\)\s*)?([A-Z]\w*)", _M), _js(r"^type\s+([A-Z]\w*)", _M)],
    "rs": [_js(r"^pub\s+(?:async\s+)?(?:fn|struct|enum|trait|type)\s+(\w+)", _M)],
    "rb": [_js(r"^\s*(?:def|class|module)\s+([A-Za-z][\w.]*)", _M)],
    "jvm": [_js(r"^\s*(?:public\s+)?(?:static\s+)?(?:final\s+)?(?:class|interface|enum|record)\s+(\w+)", _M)],
}
LANG = {"py": "py", "js": "js", "jsx": "js", "mjs": "js", "cjs": "js", "ts": "js", "tsx": "js", "go": "go", "rs": "rs",
        "rb": "rb", "java": "jvm", "kt": "jvm", "swift": "jvm", "cs": "jvm", "php": "jvm"}

# Approximates JS localeCompare (ICU, en-US) on the ASCII SAFE_PATH allows: primary weights in this order, a letter's
# cases sharing one, then lowercase before uppercase; other locales' tailorings are not emulated.
_COLLATION = "_-.()[]@/+$0123456789abcdefghijklmnopqrstuvwxyz"


def _collation_key(path: str) -> tuple[tuple[int, ...], tuple[int, ...]]:
    return tuple(_COLLATION.index(c.lower()) for c in path), tuple(int(c.isupper()) for c in path)


def _extname(path: str) -> str:
    """Node's path.extname without its dot: '' when the basename's only dot leads it."""
    base = posixpath.basename(path)
    dot = base.rfind(".")
    return base[dot + 1:] if dot > 0 else ""


def names_in(path: str, text: str) -> list[str]:
    """namesIn: the names the path's language patterns find, in pattern order, no `_` name, no duplicate."""
    names: list[str] = []
    for pattern in PATTERNS.get(LANG.get(_extname(path), ""), []):
        for match in pattern.finditer(text):
            for part in match.group(1).split(","):
                found = NAME.match(part.strip(JS_SPACE))
                name = found.group(1) if found else ""
                if name and not name.startswith("_") and name not in names:
                    names.append(name)
    return names


def _read(full: str) -> str | None:
    """The file's first 65536 UTF-16 code units, as JS slices them; None for anything but a regular file."""
    try:
        if not stat.S_ISREG(os.lstat(full).st_mode):
            return None
        with open(full, "rb") as handle:
            data = handle.read(READ_BYTES)
    except OSError:
        return None
    text = data.decode("utf-8", "replace")
    if len(text) <= 65536 // 2:
        return text
    return text.encode("utf-16-le", "surrogatepass")[:65536 * 2].decode("utf-16-le", "surrogatepass")


def source_files(paths: list[str]) -> list[str]:
    """buildMap's file list: safe source paths, no test, generated or vendored one, cut at MAX_FILES, shared first."""
    kept = [p for p in paths if SAFE_PATH.match(p) and SRC.search(p) and not SKIP_DIR.search(p) and not SKIP_FILE.search(p)]
    return sorted(kept[:MAX_FILES], key=lambda p: (not SHARED.search(p), _collation_key(p)))


def build_map(top: str, paths: list[str]) -> str:
    """buildMap over paths relative to top: the header and one line per folder, '' when no file names anything."""
    folders: dict[str, list[list[str]]] = {}
    for path in source_files(paths):
        text = _read(os.path.join(top, path))
        if text is None:
            continue
        names = names_in(path, text)
        if names:
            folders.setdefault(posixpath.dirname(path) or ".", []).append(names)
    lines: list[str] = []
    used = skipped = 0
    for folder, per_file in folders.items():
        # The first exports say what a file is; in a folder of many files one name each.
        names = list(dict.fromkeys(n for file_names in per_file for n in file_names[:1 if len(per_file) > 8 else 3]))
        line = f"{folder}/: {', '.join(names[:30])}{', ...' if len(names) > 30 else ''}"
        if used + len(line) > BUDGET:
            skipped += 1
            continue
        lines.append(line)
        used += len(line) + 1
    if not lines:
        return ""
    return "\n".join([HEADER, *lines]) + (f"\n({skipped} more folders not listed)" if skipped else "")


def map_text(top: str, env: dict[str, str]) -> str:
    """The map of the repository at top, from the paths git tracks, cut at MAX_FILES * 5 as ponytail cuts them."""
    return build_map(top, repo.tracked_paths(top, env, BUILD_TIMEOUT)[:MAX_FILES * 5])
