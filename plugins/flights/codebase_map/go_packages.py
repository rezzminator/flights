"""Go package folders and their doc synopsis, read by the Go toolchain: `go list` in each tracked module."""

from __future__ import annotations

import json
import os
import shutil

from .command import Unavailable, run
from .render import NO_DOC, unreadable

# -find lists the packages without resolving their imports: no module download, no build.
GO_LIST = ["list", "-e", "-find", "-json=Dir,Doc,Error", "./..."]
# The login shell asked for go when the hook's PATH has none: a session started outside a login shell can lack the
# PATH the user's shell profile sets.
LOGIN_SHELL_LOOKUP = "command -v go"


def go_program(top: str, env: dict[str, str], timeout: float) -> str:
    """The go to run: from env's PATH, else the one `$SHELL -lc 'command -v go'` names (/bin/sh without SHELL), asked in top."""
    found = shutil.which("go", path=env.get("PATH", ""))
    if found:
        return found
    shell = env.get("SHELL") or "/bin/sh"
    try:
        result = run([shell, "-lc", LOGIN_SHELL_LOOKUP], top, env, timeout)
    except Unavailable as error:
        raise Unavailable(f"go is not on PATH, and the login shell {shell} could not be asked: {error}") from None
    # A profile may print before the answer: the answer is the last line.
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    named = lines[-1] if lines and result.code == 0 else ""
    if os.path.isabs(named) and os.path.isfile(named) and os.access(named, os.X_OK):
        return named
    raise Unavailable("go is not on PATH (nor in the login shell)")


def _go_env(env: dict[str, str]) -> dict[str, str]:
    # Each module is read alone, whatever workspace or module flags the session carries; -mod=readonly, because
    # -mod=mod lets go rewrite the user's go.mod (it adds a missing go line) and look up modules over the network.
    return {**env, "GOWORK": "off", "GOFLAGS": "-mod=readonly"}


def _packages(stream: str) -> list[dict]:
    decoder = json.JSONDecoder()
    found, at = [], 0
    while True:
        while at < len(stream) and stream[at].isspace():
            at += 1
        if at >= len(stream):
            return found
        package, at = decoder.raw_decode(stream, at)
        found.append(package)


def entries(top: str, files: list[str], env: dict[str, str], timeout: float) -> list[tuple[str, str]]:
    """(folder, synopsis) for every package of every tracked go.mod's module, folders relative to top."""
    modules = sorted(os.path.dirname(path) or "." for path in files if os.path.basename(path) == "go.mod")
    found = []
    go = go_program(top, env, timeout) if modules else ""
    for module in modules:
        result = run([go, *GO_LIST], os.path.join(top, module), _go_env(env), timeout)
        if result.code != 0:
            raise Unavailable(f"go list in {module}/ failed (exit {result.code}): {result.last_error_line()}")
        try:
            packages = _packages(result.stdout)
        except ValueError as error:
            raise Unavailable(f"go list in {module}/ printed unreadable JSON: {error}") from None
        for package in packages:
            folder = os.path.relpath(os.path.realpath(package["Dir"]), top)
            error = (package.get("Error") or {}).get("Err")
            if error:
                found.append((folder, unreadable(error)))
            else:
                found.append((folder, package.get("Doc") or NO_DOC))
    return found
