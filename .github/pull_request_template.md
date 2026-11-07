<!-- Pull requests go to `develop`; `main` holds only releases. -->

## What this changes

## Why

## How it was checked

- [ ] A behaviour change has a test in `tests/` I watched fail first
- [ ] `make test` passes
- [ ] `make validate` passes
- [ ] `scripts/release-check.sh` passes
- [ ] Tried in a real session with `claude --plugin-dir plugins/flights`, where the change touches a hook
- [ ] README and CHANGELOG (`## [Unreleased]`) updated where behaviour changed
