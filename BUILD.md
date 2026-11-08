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

Every release goes through [.github/workflows/release.yml](.github/workflows/release.yml), which runs when a GitHub release is published. It uses npm trusted publishing (OIDC, with a provenance attestation), so there is no npm token to manage, and it only _stages_ the release: nothing is live on npm until a maintainer approves it. Don't run `npm publish` locally.

The workflow checks that the release tag matches `package.json`, runs lint, the format check and the tests, then runs `npm stage publish`. Its `prepack` step rebuilds everything (`npm run build`), including the WASM notebooks and the wheel, using uv on the runner. marimo resolves to the newest release outside `uv.toml`'s `exclude-newer` window at that moment, which may be newer than the one you tested with locally.

1. Set the version in `package.json` and finish its section in [CHANGELOG.md](CHANGELOG.md):

   ```bash
   npm version <VERSION> --no-git-tag-version
   ```

2. Rebuild from scratch, then check what the package will contain, including `assets/logo.svg` and `assets/screenshots/` for the App Store. `npm run clean` removes everything the build generates (`dist/`, `public/`, `coverage/`):

   ```bash
   npm run clean
   npm run build
   npm pack --dry-run
   ```

3. Commit and push to `main`, then wait for the SignalK Plugin CI workflow to pass on GitHub. The pre-commit hooks lint and format the changed files, run the tests when plugin code changes, and run `marimo check` on changed notebooks. To run them all over every file, for example after upgrading marimo:

   ```bash
   prek run --all-files
   ```

4. Create the GitHub release, which creates the `v<VERSION>` tag and starts the release workflow. The notes are the version's CHANGELOG section:

   ```bash
   gh release create v<VERSION> --target main --title v<VERSION> \
     --notes-file <(sed -n '/^# v<VERSION> /,/^# v/p' CHANGELOG.md | sed '1d;$d')
   ```

   The dist-tag follows the tag name: `alpha`, `beta` or `rc` in the tag publishes under that dist-tag, any other release marked as a pre-release goes to `next`, and everything else to `latest`.

5. Watch the workflow, then approve the staged version on npmjs.com (the package's **Staged Packages** tab), or with `npm stage approve <stage-id>` and 2FA:

   ```bash
   gh run watch "$(gh run list --workflow release.yml --limit 1 --json databaseId --jq '.[0].databaseId')"
   ```

6. Move the `latest` git tag to the release. Version tags should never move, so only `latest` is forced:

   ```bash
   git fetch --tags
   git tag -f latest v<VERSION>
   git push -f origin latest
   ```

7. Install it from the SignalK App Store on a test server, and check that:
   - `/@rhizomatics/signalk-datalab-plugin/` opens the gallery (SignalK serves `public/` itself, as the package has the `signalk-webapp` keyword)
   - a notebook opens and loads data
   - the App Store shows the icon and screenshot

### One-off setup

- npmjs.com → package **Settings** → **Trusted Publisher** → GitHub Actions: org `rhizomatics`, repo `signalk-datalab-plugin`, workflow `release.yml`, environment `npm`, allowed action: stage publish.
- Then, under **Publishing access**, choose "Require two-factor authentication and disallow tokens", so only the workflow can publish.
- GitHub repo → **Settings** → **Environments** → create `npm`. Optionally add yourself as a required reviewer and restrict deployment to `v*` tags.
