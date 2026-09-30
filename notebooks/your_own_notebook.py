import marimo

__generated_with = "0.25.0"
app = marimo.App(width="medium", app_title="Add Your Own Notebook")

with app.setup(hide_code=True):
    import marimo as mo


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    # Add Your Own Notebook

    How to write a notebook of your own and add it to this gallery: where the file
    goes, what the gallery reads from it, and the browser quirks worth knowing
    before you start.

    This notebook is just text; there's nothing to run.

    **Limitations**

    - Adding a notebook to the gallery means rebuilding the plugin from its source
    code, on a computer with Node.js and [uv](https://docs.astral.sh/uv/). You can't
    add one from the browser or the SignalK admin screens.
    - Changes you make to a notebook in the browser aren't kept when you open a
    different notebook, because every notebook here saves to the same
    `notebook.py` in the browser's storage. Download your work first (see below).

    Find the other notebooks in the [gallery](index.html).
    """)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## 1. Write the notebook

    Notebooks are [marimo](https://marimo.io) notebooks: plain Python files, with
    each cell a function. Start from whichever of the other notebooks is closest
    to what you want.

    - **In the browser:** open a notebook here, change it, then save it with
    marimo's menu (top right), **Download → Download notebook source**, which
    gives you the `.py` file.
    - **On a computer:** get the plugin's source code from
    [GitHub](https://github.com/rhizomatics/signalk-datalab-plugin) and run
    `npm run lab`, which opens marimo on all the notebooks, pointed at the SignalK
    server in the `SIGNALK_URL` environment variable.

    Save the file into the `notebooks/` folder, with a lowercase name such as
    `tide_heights.py`. The gallery lists notebooks by file name, after
    Analyze with Polars Dataframes, which always comes first.
    """)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## 2. Start with an intro cell

    The gallery card comes from the notebook's first markdown cell: its `# heading`
    becomes the card's title, and the first paragraph after it becomes the
    description. The other notebooks all follow the same pattern, so yours will
    fit in if it does too:

    ```python
    @app.cell(hide_code=True)
    def _():
        mo.md(r'''
        # Tide Heights Against Time

        Chart tide height over the chosen period, from a tide plugin's history.

        Cells run automatically as you change the inputs. If any look stale or
        empty, press **Run** (▶) at the bottom right of the page.

        **Limitations**

        - Needs a tide plugin recording `environment.tide.heightNow`.

        Find the other notebooks in the [gallery](index.html).
        ''')
        return
    ```
    """)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## 3. Build it into the gallery

    From the plugin's folder:

    ```bash
    uv run --with marimo marimo check notebooks/tide_heights.py
    npm run build:wasm
    ```

    The build turns every notebook in `notebooks/` into a page of its own
    (`public/tide_heights.html`) and rebuilds the gallery (`public/index.html`)
    with a card for each. Nothing else needs registering.

    To try it before installing, run `npm run preview` with `SIGNALK_URL` set to
    your server, then open the address it prints. To put it on your boat, install
    the rebuilt plugin on your SignalK server.
    """)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## 4. Things that work differently in the browser

    Notebooks here run in the browser with [Pyodide](https://pyodide.org), not on a
    computer, and a few things catch people out. Check yours with `npm run preview`
    as well as `npm run lab`, because these only show up in the browser.

    - **Packages:** pure Python packages install from PyPI with
    `await micropip.install('name')` in an `async` cell. Packages with compiled
    code only work if [Pyodide provides them](https://pyodide.org/en/stable/usage/packages-in-pyodide.html),
    and those versions often trail the desktop ones; polars, for example, is
    well behind.
    - **Reaching SignalK:** the server's address is the page's own
    (`js.location.origin`). The [signalk-cli](https://signalk-cli.rhizomatics.org.uk)
    `HistoryClient` works in the browser, as in
    [Analyze and Export with signalk-cli](history_export.html).
    - **Timestamps:** to show times with a time zone, include
    `import tzdata` in the setup cell, or tables fail to display.
    - **Strings from Arrow:** the browser's polars can crash passing on string
    columns it received as Arrow data, for example into DuckDB. Rebuild them first
    with `df.with_columns(pl.col(pl.String) + '')`.
    - **SQL:** any SQL cell makes the notebook download DuckDB and its companions
    (about 28 MB) as soon as it opens, so keep SQL out of notebooks that don't need it.
    - **Live data:** the browser can't wait on a connection without freezing the
    notebook; see [Live Stream With signalk-cli](live_stream.html) for how it
    uses the browser's own WebSocket instead.
    - **Private names:** marimo deletes a cell's `_`-prefixed variables when the
    cell runs again, so anything that outlives the run, like a callback, must not
    rely on them.

    The notes marimo's AI assistant uses for these notebooks, in
    `notebooks/CLAUDE.md`, cover the same ground in more detail.
    """)
    return


if __name__ == "__main__":
    app.run()
