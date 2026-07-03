---
name: Bug report
about: Something is broken or behaves unexpectedly
title: "[bug] "
labels: bug
assignees: ''
---

## Describe the bug

A clear, concise description of what is wrong.

## To reproduce

Minimal Python code that demonstrates the problem:

```python
from pyintent import spec, pure

@spec(...)
def my_function(...):
    ...
```

Command run:

```bash
pyintent verify mymodule.py
# or: pytest --pyintent
```

Full output (including traceback if any):

```
paste output here
```

## Expected behaviour

What you expected to happen.

## Environment

- Python version: (e.g. 3.11.4)
- pyintent version: (run `pyintent --version`)
- OS: (e.g. macOS 14, Ubuntu 22.04)
- Installed extras: (e.g. `[dev]`, `[types]`)
