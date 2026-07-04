# Changelog

All notable changes to pyintent are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
pyintent uses [Semantic Versioning](https://semver.org/).

---

## [0.1.1] — 2026-07-03

### Fixed

- `[tool.pyintent] exclude` was documented but never applied. `check`,
  `verify`, and `pytest --pyintent` now all skip excluded files without
  importing them. Patterns are globs matched against path segments,
  relative-path prefixes, or filenames, anchored at the pyproject.toml
  directory. A file named explicitly on the command line is always checked.
- `check --require-specs` no longer flags `_`-prefixed (private) functions and
  methods, matching the documented "every public function" behaviour.
- Effects-verifier failure details now report line numbers relative to the
  file instead of the function's source snippet.
- `throws(...)` no longer reports a false positive for `raise err` where
  `err` is a variable, or `raise make_err()` through a factory. Constructor
  calls (`raise NotFound(...)`) are still checked even when the class is
  imported inside the function, and skipped raises are counted in the
  check's summary.
- Config loading works on Python 3.10 (falls back to `tomli`, now a
  dependency on 3.10 only).
- Effects PASS lines no longer print the label twice (`pure  pure`), and the
  CLI shortens absolute paths for display while `--json` keeps them intact.

## [0.1.0] — 2026-07-03

Initial open-source release.

### Added

- `@spec` decorator — attach intent, pre/postconditions, effects, examples, and
  performance declarations to functions, methods, and classes with zero runtime
  overhead.
- `module_spec()` / `package_spec()` — module- and package-level intent specs.
- **Examples verifier** — run `ex` cases against the real implementation;
  supports `raises`, `_` wildcard, and value equality.
- **Properties verifier** — hypothesis-based postcondition testing for pure
  functions with type-annotated parameters.
- **Effects verifier** — AST-based checking of `pure`, `async_`, and
  `throws(...)` declarations.
- **Types verifier** — optional `mypy` integration (skipped gracefully if mypy
  is not installed).
- `pyintent verify PATH` CLI — run all verifiers with human-readable or JSON
  output.
- `pyintent check PATH` CLI — validate spec structure without execution;
  `--require-specs` enforces coverage.
- `pyintent init` / `pyintent prompt` CLI — write or print the spec-authoring
  guide for AI coding tools (AGENTS.md, CLAUDE.md, Copilot, Cursor).
- Opt-in pytest plugin (`--pyintent` / `pyintent = true` ini option) — specs
  become ordinary pytest items.
- `pyproject.toml` `[tool.pyintent]` configuration for `require_specs` and
  `exclude`.

### Deferred to v0.2

- Generator and async-generator spec execution.
- `@overload` support.
- Instance-method example execution (currently skipped with a reason).
- Liskov enforcement of abstract-method contracts.
- Performance measurement (`Perf` is stored, not yet verified).
