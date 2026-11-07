# Every check ci.yml runs on a develop -> main pull request, run the same way
# here first. The tests need python3 (3.9 or later), git and go on PATH; a
# missing one fails the run, never skips it. validate needs the claude CLI.
MANIFEST := plugins/flights/.claude-plugin/plugin.json

.PHONY: release-check check test validate release

release-check: check release

check: test validate

test:
	python3 -B -m unittest discover -s tests -t . -v

validate:
	claude plugin validate --strict plugins/flights

# Run `git fetch origin main` first: the version must move past main's.
release:
	@git rev-parse --verify -q origin/main >/dev/null || { echo "origin/main is missing from the checkout"; exit 1; }
	base=$$(if git cat-file -e "origin/main:$(MANIFEST)" 2>/dev/null; then git show "origin/main:$(MANIFEST)" | python3 -c 'import json, sys; print(json.load(sys.stdin)["version"])'; else echo "main has no $(MANIFEST): treating this as the first release" >&2; echo 0.0.0; fi) && \
	scripts/release-check.sh "$$base"
	v=$$(python3 -c 'import json; print(json.load(open("$(MANIFEST)"))["version"])'); \
	v_re=$$(printf '%s' "$$v" | sed 's/[.]/[.]/g'); \
	awk -v v="$$v_re" '$$0 ~ "^## \\[" v "\\]" {f=1; next} /^## \[/ || /^\[/ {f=0} f' CHANGELOG.md | grep -q '' || { echo "FAIL CHANGELOG.md section for $$v yields no release notes"; exit 1; }
