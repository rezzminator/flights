"""The rule links: each `{plugin root}/rules/{stem}.md` linked as `{rules folder}/flights-{stem}.md`, and the one line
a chat hears about what changed."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

# Flights owns every symlink named PREFIX + {stem} + ".md" directly in the rules folder, and nothing else there.
PREFIX = "flights-"
# The line a chat hears when a rule could not be installed is this prefix and the reason.
NOT_INSTALLED = "Flights rules not installed: "


class NotInstalled(Exception):
    """The links could not be made; the message is the reason the line names."""


@dataclass
class Outcome:
    rules: str
    linked: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    kept: list[str] = field(default_factory=list)

    def line(self) -> str | None:
        """The one context line, or None when every link was already right."""
        parts = []
        if self.kept:
            verb = "is" if len(self.kept) == 1 else "are"
            parts.append(f"{NOT_INSTALLED}{', '.join(self.kept)} {verb} not a symlink, left untouched; move it aside to"
                         " let flights link it.")
        if self.linked:
            parts.append(f"Flights rules linked into {self.rules}: {', '.join(self.linked)}; they load from the next chat.")
        if self.removed:
            parts.append(f"Flights rules removed from {self.rules}: {', '.join(self.removed)}; the change loads from"
                         " the next chat.")
        return " ".join(parts) or None


def config_dir(env: dict[str, str]) -> str:
    """$CLAUDE_CONFIG_DIR, else $HOME/.claude."""
    if env.get("CLAUDE_CONFIG_DIR"):
        return env["CLAUDE_CONFIG_DIR"]
    if env.get("HOME"):
        return os.path.join(env["HOME"], ".claude")
    raise NotInstalled("neither CLAUDE_CONFIG_DIR nor HOME is set")


def shipped_stems(plugin_root: str) -> list[str]:
    """The stems of the regular *.md files in the plugin's rules folder, sorted; an unreadable folder or none raises."""
    source = os.path.join(plugin_root, "rules")
    try:
        names = os.listdir(source)
    except OSError as error:
        raise NotInstalled(f"the plugin's rules folder {source} cannot be read: {error.strerror}") from None
    stems = sorted(name[:-3] for name in names if name.endswith(".md") and os.path.isfile(os.path.join(source, name)))
    if not stems:
        raise NotInstalled(f"the plugin's rules folder {source} holds no .md rule")
    return stems


def link(target: str, path: str) -> None:
    """path made a symlink to target by a temporary link renamed over it, so a concurrent reader never sees a gap."""
    temporary = os.path.join(os.path.dirname(path), f".{os.path.basename(path)}.{os.getpid()}.tmp")
    try:
        os.symlink(target, temporary)
        os.replace(temporary, path)
    except OSError as error:
        try:
            os.unlink(temporary)
        except OSError:
            pass  # never made, or already renamed: nothing to clean
        raise NotInstalled(f"could not link {path}: {error.strerror}") from None


def sync(plugin_root: str, rules: str) -> Outcome:
    """Every shipped rule linked into rules, every flights-*.md symlink of a stem no longer shipped removed; a regular
    file or folder on a flights name is kept. NotInstalled names the first step that failed."""
    stems = shipped_stems(plugin_root)
    outcome = Outcome(rules)
    try:
        os.makedirs(rules, exist_ok=True)
    except OSError as error:
        raise NotInstalled(f"could not create the rules folder {rules}: {error.strerror}") from None
    for stem in stems:
        name = f"{PREFIX}{stem}.md"
        path, target = os.path.join(rules, name), os.path.join(plugin_root, "rules", stem + ".md")
        if os.path.islink(path):
            if os.readlink(path) == target:
                continue
        elif os.path.lexists(path):
            outcome.kept.append(path)
            continue
        link(target, path)
        outcome.linked.append(name)
    try:
        names = sorted(os.listdir(rules))
    except OSError as error:
        raise NotInstalled(f"could not read the rules folder {rules}: {error.strerror}") from None
    for name in names:
        stem = name[len(PREFIX):-3]
        path = os.path.join(rules, name)
        if not (name.startswith(PREFIX) and name.endswith(".md")) or stem in stems or not os.path.islink(path):
            continue
        try:
            os.unlink(path)
        except FileNotFoundError:
            continue  # a chat starting at the same moment removed it first and says so
        except OSError as error:
            raise NotInstalled(f"could not remove the stale link {path}: {error.strerror}") from None
        outcome.removed.append(name)
    return outcome
