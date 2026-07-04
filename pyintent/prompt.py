"""The canonical pyintent authoring guide + writers for AI-tool prompt files.

``init`` writes this reference into the well-known prompt files that coding
agents read (AGENTS.md, CLAUDE.md, Copilot, Cursor). ``prompt`` prints it.
"""

from __future__ import annotations

from pathlib import Path

REFERENCE = '''\
# pyintent — writing specifications

`pyintent` is a **pure verifier**. You (the AI implementer) write the
implementation; the human (or you) writes `@spec` decorators describing
*intent*. pyintent then checks that your implementation satisfies the spec.
pyintent NEVER generates or edits implementation code, and NEVER calls an LLM.

Your job: **make the implementation satisfy every `@spec`.** Run
`pyintent verify <path>` (or `pytest --pyintent`) and fix real code until checks
pass. Do not weaken a spec to make it pass unless explicitly told to.

## The decorator

```python
from pyintent import spec, pure, reads, writes, network, io, async_, throws, Perf

@spec(
    intent="One-line description of what this does and why.",
    where=["n >= 0"],                 # preconditions (Python expressions)
    ensures=["result >= 0",           # postconditions; `result` = return value
             "result == n * 2"],
    effects=[pure],                   # see effects below
    ex=["(0,) -> 0",                  # runnable examples; see format below
        "(3,) -> 6",
        "(-1,) -> raises ValueError"],
    perf=Perf(time="O(n)"),           # optional, advisory
)
def double_nonneg(n: int) -> int:
    if n < 0:
        raise ValueError("n must be >= 0")
    return n * 2
```

`@spec` must be the **outermost** decorator and returns the target unchanged —
it only attaches metadata, so it never changes runtime behaviour.

## Example format: `"(args) -> expected"`

- Left side is a tuple of call arguments: `"(1, 2)"`, `"('hi',)"` (one-element
  tuples need the trailing comma), `"()"` for no args.
- `->` separates input from expected output.
- Right side is one of:
  - a Python literal/expression evaluated in the target's module: `42`, `[1,2]`,
    `"ok"`, `MyEnum.A`
  - `raises ExceptionType` — the call must raise that type (or a subclass)
  - `_` — wildcard: any return value is accepted (only that it does not raise)
- Arguments and expected values are evaluated at verify time in the module's
  namespace, so you may reference names defined in the module.

## Effects (checked where possible)

- `pure` — no I/O, no global state, no randomness. **Verified** by AST: calls
  into `os/sys/random/requests/httpx/socket/subprocess/urllib/time/...` and
  builtins `print/open/input/exec/eval` are violations, as are `global`/
  `nonlocal` writes. (Shallow: it does not follow calls into helpers.)
- `async_` — **verified**: the function must be `async def`.
- `throws(ExcA, ExcB)` — **verified** by AST: every exception type you `raise`
  explicitly must be declared here. (Raises that don't statically name a type,
  like `raise err` through a variable, are skipped and counted in the summary.)
- `reads(...)`, `writes(...)`, `network(...)`, `io` — recorded as documentation
  in v0.1 (declaration-only, not yet enforced).

A function may declare multiple effects, e.g. `effects=[reads("db"), throws(KeyError)]`.

## Properties (`where` + `ensures`)

For **pure** functions, pyintent uses Hypothesis to generate inputs from your
type hints, filters them through `where`, and asserts every `ensures`
expression. `ensures` may reference parameters and `result`. Effectful or
un-annotatable functions are skipped (not failed).

## Methods, classes, modules

- On methods, examples exclude `self`/`cls` from the argument tuple. Instance
  methods and properties are **skipped** for example/property execution in v0.1
  (planned for v0.2); their specs are still validated structurally.
- Properties: use `()` as the example input and do not use `where`.
- `@spec` on a **class** records invariants (documentation in v0.1).
- `module_spec(...)` / `package_spec(...)` record module/package intent.
- Abstract methods may carry a `@spec` to define the contract subclasses must meet.

## Workflow

1. Read the specs. 2. Implement. 3. Run `pyintent verify <path>` (or
`pytest --pyintent`). 4. Read failures (they show expected vs actual). 5. Fix the implementation.
6. Repeat until green. Treat the spec as the source of truth.
'''


def get_reference() -> str:
    return REFERENCE


_HEADER = "<!-- pyintent:begin -->"
_FOOTER = "<!-- pyintent:end -->"
_BLOCK = f"{_HEADER}\n{REFERENCE}\n{_FOOTER}\n"

#: Files coding agents commonly read, relative to project root.
PROMPT_FILES = (
    "AGENTS.md",
    "CLAUDE.md",
    ".github/copilot-instructions.md",
    ".cursor/rules/pyintent.md",
)


def _upsert(path: Path, block: str) -> str:
    """Insert or replace the pyintent block in ``path``. Returns action taken."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(block, encoding="utf-8")
        return "created"

    text = path.read_text(encoding="utf-8")
    if _HEADER in text and _FOOTER in text:
        pre = text[: text.index(_HEADER)]
        post = text[text.index(_FOOTER) + len(_FOOTER):]
        path.write_text(pre + block.rstrip("\n") + post, encoding="utf-8")
        return "updated"

    sep = "" if text.endswith("\n\n") else ("\n" if text.endswith("\n") else "\n\n")
    path.write_text(text + sep + block, encoding="utf-8")
    return "appended"


def write_prompt_files(root: str | Path = ".") -> dict[str, str]:
    """Write/refresh the pyintent guide into all known prompt files."""
    root = Path(root)
    actions: dict[str, str] = {}
    for rel in PROMPT_FILES:
        actions[rel] = _upsert(root / rel, _BLOCK)
    return actions
