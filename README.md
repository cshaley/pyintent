# pyintent

Write down what a function is supposed to do. Let an AI coding tool write the implementation. pyintent checks that the implementation actually does what you said.

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

```bash
pyintent verify myapp/orders.py     # run all verifiers, human-readable report
pytest --pyintent                   # or run specs as pytest items
```

pyintent is a pure verifier. It never calls an LLM. Like mypy checks types without generating code, pyintent checks that an implementation matches its declared intent: examples, pre/post-conditions, effects, and types. Every check is deterministic: it passes, or it tells you exactly what's wrong and where.

## Why I built this

I started with a different question: would LLMs write better code if we gave them a language designed for them? I prototyped one with Replit agents. The answer was no. A model that has never seen a language in its training data writes it badly, no matter how friendly the syntax is, and no amount of prompt-side documentation made up the gap. The training data wins.

But the research I read while designing that language kept pointing at a handful of things that reliably do help LLMs produce correct code: stating intent explicitly, giving concrete input/output examples, declaring side effects, and giving the model fast deterministic feedback it can iterate against. (The specific papers are in [The research behind the design](#the-research-behind-the-design).)

So pyintent is that language idea inverted. Instead of new syntax the model has never seen, it's a contract you attach to ordinary Python, the language LLMs know best, plus a verifier that checks the contract mechanically. The spec states what the code should do; the AI writes the code; `pyintent verify` closes the loop.

## The research behind the design

Nothing in `@spec` is invented here. Each piece comes from somewhere, either from the contracts-and-testing literature or from what the LLM code-generation papers found actually helps. These are the papers that shaped the design.

**The contract idea is old.** Preconditions and postconditions as the definition of program correctness go back to [Dijkstra's guarded commands](https://doi.org/10.1145/360933.360975) (1975), and attaching them to code as first-class, checkable clauses is [Meyer's Design by Contract](https://doi.org/10.1109/2.161279) (1992). `where`, `ensures`, and `invariants` are that vocabulary almost verbatim. At the heavyweight end, [Dafny](https://doi.org/10.1007/978-3-642-17511-4_20) (Leino, 2010) proves contracts statically. pyintent sits deliberately at the lightweight end: same contract shape, checked by execution and property testing rather than proof, on unmodified Python.

**Checking contracts by generated inputs.** The technique behind the `properties` verifier is [QuickCheck](https://doi.org/10.1145/351240.351266) (Claessen & Hughes, 2000): generate random inputs, assert declared properties. pyintent uses its Python descendant [Hypothesis](https://doi.org/10.21105/joss.01891) (MacIver et al.) directly. [Vikram et al.](https://arxiv.org/abs/2307.04346) found the painful parts of property-based testing are writing input generators and inventing properties; pyintent builds generators from your type hints, so the spec author only writes the properties.

**Why not a new language.** Code LLM quality tracks how often a language appears in training data. [MultiPL-E](https://arxiv.org/abs/2208.08227) (Cassano et al.) benchmarked code generation across 19 languages and found performance drops off sharply for low-resource ones, and [MultiPL-T](https://arxiv.org/abs/2308.09895) showed that closing the gap takes large-scale training data, not something you can fix from the prompt side. A brand-new language is the lowest-resource language possible, which is why pyintent attaches contracts to Python instead.

**Why examples are the core of the spec.** [AlphaCode](https://arxiv.org/abs/2203.07814) (Li et al.) credited much of its competition performance to filtering a huge pool of sampled programs by executing them against the problem's example tests; [CodeT](https://arxiv.org/abs/2207.10397) (Chen et al.) got large gains from the same move with generated tests. [TiCoder](https://arxiv.org/abs/2208.05950) (Lahiri et al.) showed that a handful of concrete test cases also works as a *formalization of user intent*: it pins down what you meant, not just what passes. pyintent's `ex` field is that idea as a one-line syntax.

**Why postconditions.** [Endres et al.](https://arxiv.org/abs/2310.01831) found that natural-language intent can be translated into formal postconditions that are usually correct and genuinely discriminating: their generated postconditions caught 64 real historical bugs in Defects4J. `ensures` is the hand-written version of the same contract.

**Why a deterministic verifier in the loop.** Iterating against feedback demonstrably helps: [Self-Debugging](https://arxiv.org/abs/2304.05128) (Chen et al.) with execution results, [Reflexion](https://arxiv.org/abs/2303.11366) (Shinn et al.) with environment signals like failing tests, [Self-Refine](https://arxiv.org/abs/2303.17651) (Madaan et al.) with the model's own critique. But [Olausson et al.](https://arxiv.org/abs/2306.09896) found self-repair is bottlenecked exactly there: models are bad at judging their *own* code. That's the argument for pyintent being a pure verifier: the feedback the model iterates against comes from running the contract, never from asking a model whether it thinks the code is right.

## What I can and can't claim

I tried to show that pyintent improves LLM coding-benchmark scores and never found an experiment design that made a convincing case. Benchmark tasks like [HumanEval](https://arxiv.org/abs/2107.03374) and [MBPP](https://arxiv.org/abs/2108.07732) are small, self-contained, and already specified by their test suites, which is precisely the situation where a spec layer adds the least. If anything, the benchmark literature argues for richer checks than benchmarks themselves use: [EvalPlus](https://arxiv.org/abs/2305.01210) added 80× more tests to HumanEval and found a meaningful share of "passing" solutions were wrong.

The bet I'm actually making is on maintainability. A test suite tells you what code does today; a spec records what it was *for*. Six months from now, when an AI tool (or a person) rewrites `find_order`, the contract is still attached to the function: the intent, the examples, the declared effects, the exceptions it's allowed to raise. Any regeneration of the code gets re-verified against the original intent instead of against whatever the last version happened to do.

That's a hypothesis, not a measured result. If you have an idea for a fair experiment, I'd genuinely like to hear it. Open an issue.

## Install

```bash
pip install pyintent           # core (examples, properties, effects)
pip install pyintent[types]    # + mypy integration
pip install pyintent[dev]      # + mypy + pytest-asyncio
```

Or with conda:

```bash
conda install -c conda-forge pyintent
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
[PASS] examples   my_abs  (3,) -> 3
[PASS] examples   my_abs  (-4,) -> 4
[PASS] examples   my_abs  (0,) -> 0
[PASS] properties my_abs  2 ensures held over 50 examples
[PASS] effects    my_abs  pure  no impure calls found
[PASS] types      mymodule.py  mypy clean

6 passed  0 failed  0 errored  0 skipped
```

## The `@spec` decorator

`@spec` accepts these fields:

| Field        | Type                | Description |
|--------------|---------------------|-------------|
| `intent`     | `str` (required)    | One-line description of what the function does and why. |
| `where`      | `list[str]`         | Preconditions: Python expressions that must hold over the inputs. |
| `ensures`    | `list[str]`         | Postconditions: Python expressions over inputs and `result`. |
| `effects`    | `list[Effect]`      | Declared side-effects (see below). |
| `ex`         | `list[str]`         | Runnable examples in `"(args) -> expected"` format. |
| `perf`       | `Perf`              | Advisory complexity, e.g. `Perf(time="O(n)")`. |
| `invariants` | `list[str]`         | Class/module-level invariants (plain strings or expressions). |

`@spec` must be the outermost decorator and returns the target unchanged. It only attaches metadata, so there is no runtime overhead.

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

Runs `mypy` over the target file. Skipped (not failed) if mypy is not installed. Install it with `pip install pyintent[types]`.

### `effects` — AST-based effect checking

Three effects are actively verified in v0.1:

| Effect | What is checked |
|--------|----------------|
| `pure` | No calls to impure builtins (`print`, `open`, …) or modules (`os`, `sys`, `random`, `requests`, …), no `global`/`nonlocal` writes. |
| `async_` | The function must be defined with `async def`. |
| `throws(ExcA, ExcB)` | Every explicitly raised exception type is declared. Raises that don't statically name a type (`raise err` through a variable, `raise make_err()` through a factory) are skipped and counted in the summary. |

These effects are declaration-only (recorded but not verified):
`reads("db")`, `writes("cache")`, `network("stripe")`, `io`

A function may combine multiple effects:
```python
effects = [reads("db"), throws(NotFoundError, ValueError)]
```

The purity check is deliberately shallow — it doesn't follow calls into helper functions. It catches the common cases and reports the offending file line for each violation.

## CLI usage

```bash
# Write the spec-authoring guide into your AI tool's prompt files
# (AGENTS.md, CLAUDE.md, .github/copilot-instructions.md, etc.)
pyintent init

# Print the spec-authoring guide to stdout
pyintent prompt

# Validate spec structure by importing files (functions are not called)
pyintent check myapp/

# Require every public function to have a @spec (names starting
# with "_" are exempt)
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

The pytest plugin is opt-in; installing pyintent does not change how existing `pytest` runs behave.

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

`exclude` entries are glob patterns matched against path segments (`"migrations"`), relative-path prefixes (`"src/migrations"`), or filenames (`"*_pb2.py"`), anchored at the directory containing the pyproject.toml. Both the CLI and `pytest --pyintent` skip excluded files without importing them. A file you name explicitly on the command line is always checked, even if a pattern matches it.

## Safety

pyintent imports the files it checks, and the `examples` and `properties` verifiers execute the code under test in the current Python process. That's fine for your own code. But pyintent's whole premise is checking code written by an AI tool, so treat that code as untrusted: review it, or run `pyintent verify` in a sandbox (container, VM, or restricted user) first.

## Status

v0.1. Planned for v0.2: generator/async-generator specs, `@overload`, instance-method example execution, Liskov enforcement of abstract-method contracts, performance measurement.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
