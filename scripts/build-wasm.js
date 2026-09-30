// Exports every marimo notebook in notebooks/ to the WASM bundle in public/.
// signalk.py becomes datalab.html (the main Data Lab interface); each other
// notebook becomes <name>.html next to it, and index.html is a gallery of them
// all (see build-gallery.js). All exports of the same marimo version share
// identical, content-hashed assets, so only one copy of assets/ is kept.
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { execFileSync } = require("node:child_process");
const { buildGallery, MAIN, MAIN_PAGE } = require("./build-gallery");

const root = path.join(__dirname, "..");
const publicDir = path.join(root, "public");
const notebooksDir = path.join(root, "notebooks");

function exportNotebook(notebook, outDir) {
  execFileSync(
    "uv",
    [
      "run",
      "--with-requirements",
      "requirements.txt",
      "marimo",
      "export",
      "html-wasm",
      path.join("notebooks", notebook),
      "-o",
      outDir,
      "--mode",
      "edit",
      "-f",
    ],
    { cwd: root, stdio: "inherit" },
  );
}

const notebooks = fs
  .readdirSync(notebooksDir)
  .filter((f) => f.endsWith(".py"))
  .filter((f) => /^app = marimo\.App/m.test(fs.readFileSync(path.join(notebooksDir, f), "utf8")));

// Clear the previous build's assets and notebook pages, so a renamed or
// removed notebook doesn't leave a stale page behind
fs.rmSync(path.join(publicDir, "assets"), { recursive: true, force: true });
if (fs.existsSync(publicDir)) {
  for (const file of fs.readdirSync(publicDir).filter((f) => f.endsWith(".html"))) {
    fs.rmSync(path.join(publicDir, file));
  }
}
exportNotebook(MAIN, publicDir);
fs.renameSync(path.join(publicDir, "index.html"), path.join(publicDir, MAIN_PAGE));

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "datalab-wasm-"));
try {
  for (const notebook of notebooks.filter((f) => f !== MAIN)) {
    const out = path.join(tmp, path.parse(notebook).name);
    exportNotebook(notebook, out);
    fs.copyFileSync(path.join(out, "index.html"), path.join(publicDir, `${path.parse(notebook).name}.html`));
    // Assets should match the main export; copy any that don't, just in case
    fs.cpSync(path.join(out, "assets"), path.join(publicDir, "assets"), {
      recursive: true,
      force: false,
    });
  }
} finally {
  fs.rmSync(tmp, { recursive: true, force: true });
}

buildGallery(notebooks);
