# Changelog

All notable changes to pyintent are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
pyintent uses [Semantic Versioning](https://semver.org/).

---

## [0.1.0] — 2024-07-02

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
