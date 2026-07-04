# Contributing to pyintent

Thanks for helping out. Here's what you need to get started.

## Filing issues

- **Bug reports** — use the [bug report template](.github/ISSUE_TEMPLATE/bug_report.md).
  Include the Python version, pyintent version, a minimal reproducing example, and the full output.
- **Feature requests** — use the [feature request template](.github/ISSUE_TEMPLATE/feature_request.md).
  Explain the use case before proposing a solution.
- **Questions** — open a plain issue with the `question` label.

## Development setup

```bash
git clone https://github.com/cshaley/pyintent
cd pyintent
pip install -e ".[dev]"
```

This installs pyintent in editable mode with `mypy` and `pytest-asyncio`.

## Running the tests

```bash
pytest                          # run the test suite
pytest --pyintent               # also run pyintent's own specs as pytest items
```

All tests must pass before a PR is merged.

## Code style

- Python 3.10+.
- Standard library imports first, then third-party, then local (`from __future__` always first).
- Private helpers are prefixed with `_`.
- Every public symbol exported from `__init__.py` must have a docstring.
- Keep the library lean: new dependencies in the default install require a strong justification.

## Submitting a pull request

1. Fork the repository and create a branch from `main`.
2. Make your changes.
3. Add or update tests so coverage does not regress.
4. Run the full test suite (`pytest`).
5. Open a PR against `main` with a clear description of what changed and why.

## Architecture overview

```
pyintent/
  __init__.py        public API surface
  _spec.py           @spec decorator and PyIntentSpec data model
  _effects.py        Effect / EffectKind value objects
  _parser.py         ex string parser
  _discovery.py      discover SpecTarget objects in a module
  _loader.py         import Python files by path
  _module_spec.py    module_spec() / package_spec() helpers
  _perf.py           Perf declaration
  _errors.py         PyIntentError / PyIntentSpecError
  cli.py             click CLI (init, prompt, check, verify)
  plugin.py          pytest plugin (opt-in via --pyintent)
  prompt.py          spec-authoring guide written by pyintent init
  verifier/
    __init__.py      run_all() orchestrator
    examples.py      ex case runner
    properties.py    hypothesis-based postcondition testing
    effects.py       AST-based effect checking
    types.py         mypy integration
    _result.py       CheckResult / Status
```

The library is a *pure verifier* — it checks, it never generates. No part of the library calls an LLM.
