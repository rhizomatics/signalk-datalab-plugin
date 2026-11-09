# Helping with a Data Lab notebook in the browser

You were started by the ACP bridge for marimo's agent panel. The panel belongs to a Data Lab notebook running in the user's browser, in Pyodide (Python compiled to WebAssembly). The notebook is not on this machine's disk.

## Finding the notebook

- When marimo says the notebook is at `notebook.py`, it means `/marimo/notebook.py` in the browser's own filesystem. There's only ever one notebook open per panel, and that's the one the user is asking about, so don't ask which one it is.
- Read it with `mcp__acp__Read` and the exact path `/marimo/notebook.py`. The `mcp__acp__` file tools are the only way to reach the browser's files. Your own Read, Glob, Grep and Bash tools only see this machine, where the notebook doesn't exist.
- Never pass a path from this machine to an `mcp__acp__` tool. The browser can't find it, and the user sees the Python traceback as a red pop-up in the notebook.
- The notebook's title is in `marimo.App(app_title=...)` near the top of the file, if you want to name it back to the user.
- The source notebooks this was built from are in `../notebooks/`, but the user may have changed the browser copy, so always read `/marimo/notebook.py` for the current code.

## Making changes

- Writing to `/marimo/notebook.py` does not update the notebook the user is looking at, because nothing in the browser watches that file. Don't use `mcp__acp__Write` or `mcp__acp__Edit` on it.
- Instead, give the user the code for each new or changed cell in your reply, one fenced block per cell, saying where it goes (e.g. "add after the cell that fetches the history"). They paste it into a cell in the notebook.
- Write only the body of each cell, not the `@app.cell` decorator, function signature or `return`. marimo works those out.
- You can't run code or see cell outputs from here. If the user reports an error, ask them to paste the message.

## What works in the browser

@../notebooks/CLAUDE.md
