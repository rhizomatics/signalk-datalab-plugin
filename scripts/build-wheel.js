// Builds the ibis-signalk wheel into public/wheels/ so the WASM notebook can
// micropip-install it from the plugin itself, and writes index.json naming it.
const fs = require("node:fs");
const path = require("node:path");
const { execFileSync } = require("node:child_process");

const root = path.join(__dirname, "..");
const outDir = path.join(root, "public", "wheels");

fs.rmSync(outDir, { recursive: true, force: true });
execFileSync("uv", ["build", "--wheel", "--out-dir", outDir, path.join(root, "packages", "ibis-signalk")], { stdio: "inherit" });

const wheels = fs.readdirSync(outDir).filter((f) => f.endsWith(".whl"));
fs.writeFileSync(path.join(outDir, "index.json"), JSON.stringify({ "ibis-signalk": wheels[0] }));
