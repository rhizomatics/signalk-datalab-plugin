// Removes everything the build generates, so the next build starts from
// scratch: dist/ (TypeScript output), public/ (the WASM bundle, gallery and
// wheels) and coverage/. None of it is in git.
const fs = require("node:fs");
const path = require("node:path");

const root = path.join(__dirname, "..");

for (const dir of ["dist", "public", "coverage"]) {
  fs.rmSync(path.join(root, dir), { recursive: true, force: true });
}
