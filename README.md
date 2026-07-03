# pyintent

Write your intent as a specification. Let any AI coding tool write the implementation. **pyintent verifies the implementation actually satisfies the intent.**

pyintent is a *pure verifier*. It never calls an LLM. Like `mypy` checks types without generating code, pyintent checks that an implementation matches its declared intent — examples, pre/post-conditions, effects, and types.

```python
from pyintent import spec, reads, throws

@spec(
    intent  = "Return the order with the given id from the database.",
    where   = ["order_id > 0"],
    ensures = ["result.id == order_id"],
    effects = [reads("db"), throws(NotFoundError)],
    ex      = [
        "(42,)  -> _",
        "(999,) -> raises NotFoundError",
        "(0,)   -> raises ValueError",
    ],
)
def find_order(order_id: int) -> Order:
    ...   # implemented by Claude Code / Copilot / Devin / you
```

Then:

```bash
pyintent verify myapp/orders.py     # run all verifiers, human-readable report
pytest --pyintent                   # specs become pytest items automatically
```

## Install

```bash
pip install pyintent           # core (examples, properties, effects)
pip install pyintent[types]    # + mypy integration
pip install pyintent[dev]      # + mypy + pytest-asyncio
```

## Quick start

```python
from pyintent import spec, pure

@spec(
    intent  = "Return the absolute value of x.",
    effects = [pure],
    ensures = ["result >= 0", "result == x or result == -x"],
    ex      = ["(3,) -> 3", "(-4,) -> 4", "(0,) -> 0"],
)
def my_abs(x: int) -> int:
    return x if x >= 0 else -x
```

```bash
$ pyintent verify mymodule.py
[PASS] examples    my_abs  (3,) -> 3
[PASS] examples    my_abs  (-4,) -> 4
[PASS] examples    my_abs  (0,) -> 0
[PASS] properties  my_abs
[PASS] effects     my_abs  pure
[PASS] types       mymodule.py

3 passed  0 failed  0 errored  0 skipped
```

## The `@spec` decorator

`@spec` accepts these fields:

| Field        | Type                | Description |
|--------------|---------------------|-------------|
| `intent`     | `str` (required)    | One-line description of what the function does and why. |
| `where`      | `list[str]`         | Preconditions — Python expressions that must hold over the inputs. |
| `ensures`    | `list[str]`         | Postconditions — Python expressions over inputs and `result`. |
| `effects`    | `list[Effect]`      | Declared side-effects (see below). |
| `ex`         | `list[str]`         | Runnable examples in `"(args) -> expected"` format. |
| `perf`       | `Perf`              | Advisory complexity, e.g. `Perf(time="O(n)")`. |
| `invariants` | `list[str]`         | Class/module-level invariants (plain strings or expressions). |

`@spec` must be the **outermost** decorator and returns the target **unchanged** — it only attaches metadata, so there is zero runtime overhead.

## Verifiers

### `examples` — run concrete cases

Each `ex` string has the format `"(args) -> expected"`:

```python
ex = [
    "(1, 2)  -> 3",              # must return 3
    "(0,)    -> raises ValueError",  # must raise ValueError
    "('hi',) -> _",              # wildcard: any return without raising
]
```

- The left side is a tuple literal (single-arg tuples need a trailing comma: `(42,)`).
- `raises ExcType` matches if the call raises that type or a subclass.
- `_` matches any non-raising return.
- Values are evaluated in the module's global namespace, so domain objects and enums resolve correctly.

### `properties` — hypothesis-based postcondition testing

For functions with `ensures` and no impure effects, pyintent generates inputs from type hints using [Hypothesis](https://hypothesis.readthedocs.io/), filters them through `where`, and asserts every `ensures` expression:

```python
@spec(
    intent  = "Sort a list of integers in ascending order.",
    effects = [pure],
    where   = ["len(xs) < 1000"],
    ensures = [
        "len(result) == len(xs)",
        "all(result[i] <= result[i+1] for i in range(len(result)-1))",
    ],
)
def sort_ints(xs: list[int]) -> list[int]:
    return sorted(xs)
```

`ensures` expressions may reference input parameters and `result` (the return value).

### `types` — mypy integration

Runs `mypy` over the target file. Skipped gracefully if mypy is not installed. Install it with `pip install pyintent[types]`.

### `effects` — AST-based effect checking

Three effects are actively verified in v0.1:

| Effect | What is checked |
|--------|----------------|
| `pure` | No calls to impure builtins (`print`, `open`, …) or modules (`os`, `sys`, `random`, `requests`, …), no `global`/`nonlocal` writes. |
| `async_` | The function must be defined with `async def`. |
| `throws(ExcA, ExcB)` | Every explicitly raised exception type is declared. |

These effects are **declaration-only** (recorded but not verified):
`reads("db")`, `writes("cache")`, `network("stripe")`, `io`

A function may combine multiple effects:
```python
effects = [reads("db"), throws(NotFoundError, ValueError)]
```

## CLI usage

```bash
# Write the spec-authoring guide into your AI tool's prompt files
# (AGENTS.md, CLAUDE.md, .github/copilot-instructions.md, etc.)
pyintent init

# Print the spec-authoring guide to stdout
pyintent prompt

# Validate spec structure by importing files (no execution)
pyintent check myapp/

# Require every public function to have a @spec
pyintent check --require-specs myapp/

# Run all verifiers and report results
pyintent verify myapp/orders.py
pyintent verify myapp/

# Machine-readable JSON output
pyintent verify --json myapp/ > results.json

# Run only specific verifiers
pyintent verify --only examples --only properties myapp/
```

Exit codes: `0` all good, `1` verification failures, `2` usage or load error.

## pytest plugin

The pytest plugin is opt-in — installing pyintent does not change how existing `pytest` runs behave.

Enable it on the command line:

```bash
pytest --pyintent
```

Or permanently in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
pyintent = true
```

Each spec becomes one or more pytest items:

- One item per `ex` case
- One item for property testing (if `ensures` is set)
- One item for the type check per file

## pyproject.toml configuration

```toml
[tool.pyintent]
require_specs = true   # or "all" to also require class/module specs
exclude = ["migrations", "tests"]
```

## Safety

pyintent's `examples` and `properties` verifiers **execute the code under test** in the current Python process. That is fine for your own code — but pyintent's whole premise is checking code written by an AI tool, so treat that code as untrusted: review it, or run `pyintent verify` in a sandbox (container, VM, or restricted user), before running it on your machine.

## Status

v0.1. The following are planned for v0.2: generator/async-generator specs, `@overload`, instance-method example execution, Liskov enforcement of abstract-method contracts, performance measurement.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
