# SignalK Data Lab

## ALPHA - Use with care

Data notebooks, using [Marimo](https://marimo.io) and Python for DAG aware notebooks. Notebooks run entirely in the browser, using WebAssembly (WASM) to keep the server load minimal and best suited to Raspberry Pi, NanoPi etc servers.

Intention is to have these wired up by default to SignalK History API.

Packaged with an example working notebook that will pull selected paths out of
the SignalK History API

## Development

### Linux Packages
* node
* librsvg2-bin

### Local Execution

To run the notebook outside of SignalK / webbrowser context, use

```bash
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt
marimo run notebooks/signalk.py
```

### Release

```bash
npm publish --tag latest --access public
```

## Also Check

* [signalk-cli](https://pypi.org/project/signalk-cli/) - A Python based CLI for extracting data and exploring paths on the SignalK APIs, with output to CSV or Apache Arrow dataframe (Feather)