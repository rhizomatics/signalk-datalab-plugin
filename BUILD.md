# signalk-datalab-plugin Development

## Updating the Python side

[requirements.txt](requirements.txt) sets a minimum marimo version (`marimo>=…`), not a fixed one. The WASM build (`npm run build:wasm`), `npm run agent`, `npm run lab`, the pre-commit `marimo check` hook and the Claude `marimo check` hook all use it, so each picks up the newest marimo release `uv` can resolve, subject to the release cooldowns below. A release build can therefore ship a newer marimo than the last one. Before a release build:

1. Check the [marimo releases](https://github.com/marimo-team/marimo/releases) since the version in the last build for any breaking changes.
2. If the notebooks need a newer marimo feature, raise the minimum in `requirements.txt`, e.g. `marimo>=0.25.0`.
3. Check the notebooks still pass with the version uv now resolves:

   ```bash
   uv run --with-requirements requirements.txt marimo check notebooks/*.py
   ```

4. Rebuild and confirm the version that went into the bundle:

   ```bash
   npm run build:wasm
   grep -o '"version": *"[0-9.]*"' public/datalab.html | head -1
   ```

5. Try it against a real server with `SIGNALK_URL=http://my-boat.local:3000 npm run preview`.
6. Note the new version in [CHANGELOG.md](CHANGELOG.md).

If `uv` reports _No solution found_ for a version that is on PyPI, check the `exclude-newer` release cooldowns: 4 days in this repo's `uv.toml`, 5 days in `packages/ibis-signalk/pyproject.toml` (which `npm run lab` runs under), and possibly one in `~/.config/uv/uv.toml`. They hold back recently published packages, so a new marimo release can't be used until it is older than the cutoff. `signalk-cli` is exempt in both repo files.

The `packages/ibis-signalk` package has its own marimo requirement in its `pyproject.toml` and `uv.lock`. It isn't part of the plugin build, but can be updated with `uv lock --upgrade-package marimo` in that directory.

The notebooks install `signalk-cli>=3.0.0` from PyPI when they open in the browser, so users get whatever version is current then, not necessarily the one a release was tested with.

## Release

`npm publish` rebuilds everything first (`prepack` runs `npm run build`), so the publishing machine needs Node.js and [uv](https://docs.astral.sh/uv/).

1. Set the version in `package.json` and finish its section in [CHANGELOG.md](CHANGELOG.md):

   ```bash
   npm version <VERSION> --no-git-tag-version
   ```

2. Commit and push, then wait for the SignalK Plugin CI workflow to pass on GitHub. The pre-commit hooks lint and format the changed files, run the tests when plugin code changes, and run `marimo check` on changed notebooks. To run them all over every file, for example after upgrading marimo:

   ```bash
   pre-commit run --all-files
   ```

3. Rebuild from scratch, then check what the package will contain, including `assets/logo.svg` and `assets/screenshots/` for the App Store. `npm run clean` removes everything the build generates (`dist/`, `public/`, `coverage/`):

   ```bash
   npm run clean
   npm run build
   npm pack --dry-run
   ```

4. Tag the release. Version tags should never move, so only `latest` is forced:

   ```bash
   git tag v<VERSION>
   git tag -f latest
   git push origin v<VERSION>
   git push -f origin latest
   ```

5. Publish to npm:

   ```bash
   npm login
   npm publish --tag latest --access public
   ```

6. Create the GitHub release, with the version's CHANGELOG section as its notes:

   ```bash
   gh release create v<VERSION> --title v<VERSION> --notes-file <notes.md>
   ```

7. Install it from the SignalK App Store on a test server, and check that:
   - `/@rhizomatics/signalk-datalab-plugin/` opens the gallery (SignalK serves `public/` itself, as the package has the `signalk-webapp` keyword)
   - a notebook opens and loads data
   - the App Store shows the icon and screenshot
