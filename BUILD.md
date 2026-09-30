# signalk-datalab-plugin Development

## Updating the Python side

The marimo version is pinned in [requirements.txt](requirements.txt). The WASM build (`npm run build:wasm`), `npm run agent` and the Claude `marimo check` hook all use it, so the version shipped doesn't depend on what `uv` has cached. Update it before a release build:

1. Check the [marimo releases](https://github.com/marimo-team/marimo/releases) for the version you want and any breaking changes.
2. Set it in `requirements.txt`, e.g. `marimo==0.25.0`.
3. Check the notebook still passes with the new version:

   ```bash
   uv run --with-requirements requirements.txt marimo check notebooks/signalk.py
   ```

4. Rebuild and confirm the version that went into the bundle:

   ```bash
   npm run build:wasm
   grep -o '"version": *"[0-9.]*"' public/index.html | head -1
   ```

5. Try it against a real server with `SIGNALK_URL=http://my-boat.local:3000 npm run preview`.
6. Note the new version in [CHANGELOG.md](CHANGELOG.md).

If `uv` reports *No solution found* for a version that is on PyPI, check for an `exclude-newer` setting in `~/.config/uv/uv.toml`. That setting holds back recently published packages, so a new marimo release can't be used until it is older than the cutoff.

The `packages/ibis-signalk` package has its own marimo requirement in its `pyproject.toml` and `uv.lock`. It isn't part of the plugin build, but can be updated with `uv lock --upgrade-package marimo` in that directory.

## Release

```bash
npm login
git tag -f latest
git tag -f v<VERSION>
git push --tags --force
npm publish --tag latest --access public
```

GitHub release
