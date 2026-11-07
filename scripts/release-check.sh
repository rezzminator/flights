#!/usr/bin/env bash
# Release integrity: the version agrees in every place that carries it, and
# CHANGELOG.md has a dated section for it. With a base version argument (the
# version on main), the version must also have moved past it.
# Prints one line per failure and exits 1; exits 2 when a file or a version cannot be read.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 2
v=$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["version"])' plugins/flights/.claude-plugin/plugin.json) || { echo "ERROR cannot read plugins/flights/.claude-plugin/plugin.json"; exit 2; }
[ -n "$v" ] || { echo "ERROR plugin.json has no version"; exit 2; }
v_re=$(printf '%s' "$v" | sed 's/\./\\./g')
fail=0
b=$(grep -oE 'badge/version-[0-9]+\.[0-9]+\.[0-9]+(--[0-9A-Za-z.]+)?-' README.md | sed -E 's/^badge\/version-//; s/-$//; s/--/-/')
[ "$b" = "$v" ] || { echo "FAIL README badge says ${b:-nothing}, plugin.json $v"; fail=1; }
grep -qE "^## \[$v_re\] — [0-9]{4}-[0-9]{2}-[0-9]{2}$" CHANGELOG.md || { echo "FAIL CHANGELOG.md has no dated section for $v"; fail=1; }
if [ -n "${1:-}" ]; then
  # Semantic-version precedence (semver.org item 11), hand-written: the standard library has none. A release sorts
  # after its own pre-releases; pre-release fields compare numerically when numeric, a number before a word.
  newest=$(python3 -c '
import sys
def key(v):
    core, _, pre = v.partition("-")
    fields = [(0, int(f), "") if f.isdigit() else (1, 0, f) for f in pre.split(".")] if pre else []
    return ([int(n) for n in core.split(".")], pre == "", fields)
a, b = sys.argv[1:]
print(a if key(a) >= key(b) else b)' "$1" "$v") || { echo "ERROR cannot compare version $v with main's $1"; exit 2; }
  { [ "$v" != "$1" ] && [ "$newest" = "$v" ]; } || { echo "FAIL version $v has not moved past main's $1"; fail=1; }
fi
[ $fail -eq 0 ] && echo "PASS release $v: versions agree, CHANGELOG dated${1:+, past $1}"
exit $fail
