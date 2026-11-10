"""The one door for running a command: bounded by a timeout, every failure an Unavailable that says why; and the one
door for starting this package as a detached background process."""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
# Background processes this process started and has not reaped: one still running when the hook answers outlives it.
STARTED: list[subprocess.Popen] = []


# The unavailable line a loop receives is this prefix and the reason.
UNAVAILABLE = "Codebase map unavailable: "


class Unavailable(Exception):
    """The map cannot be built; the message is the reason the injected line names."""


@dataclass
class Result:
    code: int
    stdout: str
    stderr: str

    def last_error_line(self) -> str:
        lines = [line.strip() for line in self.stderr.splitlines() if line.strip()]
        return lines[-1] if lines else "no error output"


def run(argv: list[str], cwd: str, env: dict[str, str], timeout: float) -> Result:
    """Run argv in cwd with env; a missing directory, a missing program or the timeout raise Unavailable."""
    if not os.path.isdir(cwd):
        raise Unavailable(f"the directory {cwd} does not exist")
    try:
        done = subprocess.run(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout)
    except FileNotFoundError:
        raise Unavailable(f"{argv[0]} is not on PATH") from None
    except subprocess.TimeoutExpired:
        raise Unavailable(f"`{' '.join(argv[:2])}` took longer than {timeout:g}s") from None
    except OSError as error:
        raise Unavailable(f"`{' '.join(argv[:2])}` could not start: {error}") from None
    return Result(done.returncode, done.stdout.decode("utf-8", "replace"), done.stderr.decode("utf-8", "replace"))


def start_background(args: list[str], env: dict[str, str], what: str) -> subprocess.Popen:
    """This package run detached with args (`build {top} {head}`), in its own session; tracked in STARTED.
    what names it in the Unavailable a failed start raises."""
    argv = [sys.executable, "-I", "-B", PACKAGE_DIR, *args]
    try:
        started = subprocess.Popen(
            argv, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True, close_fds=True,
        )
    except OSError as error:
        raise Unavailable(f"the {what} could not start: {error}") from None
    STARTED.append(started)
    return started
