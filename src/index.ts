import * as path from "path";
import * as fs from "fs";
import compression from "compression";
import express from "express";
import type { Plugin, PluginRouter, ServerAPI } from "@signalk/server-api";

const PLUGIN_ID = "signalk-datalab-plugin";

// marimo's exported JS/CSS chunks and the vendored wheel are content-hashed
// (e.g. index-CgQsZfww.js), so they're safe to cache indefinitely; the HTML
// pages and other top-level files are not hashed and must revalidate instead.
const IMMUTABLE_DIR_PATTERN = /[/\\](assets|wheels)[/\\]/;

module.exports = function (app: ServerAPI): Plugin {
  // SignalK serves public/ at /@rhizomatics/signalk-datalab-plugin itself, as
  // the package has the signalk-webapp keyword; this router adds /ui under
  // /plugins/<id>, which is for admins only
  const publicDir = path.join(__dirname, "..", "public");

  const plugin: Plugin = {
    id: PLUGIN_ID,
    name: "SignalK Data Lab",
    description:
      "Interactive data analysis notebooks for SignalK, using Marimo running as WebAssembly in the browser — no Python required on the server.",

    registerWithRouter(router: PluginRouter) {
      // gzip/brotli the JS/CSS/HTML chunks marimo's WASM export ships —
      // there are hundreds of them, so shrinking each one adds up
      router.use(compression());

      // Serve all WASM bundle assets (JS chunks, fonts, icons, …). Hashed
      // filenames under assets/ and wheels/ get a far-future immutable
      // cache so repeat visits (e.g. from the same boat browser) skip the
      // network entirely instead of re-fetching hundreds of files.
      router.use(
        "/",
        express.static(publicDir, {
          setHeaders(res, filePath) {
            if (IMMUTABLE_DIR_PATTERN.test(filePath)) {
              res.setHeader("Cache-Control", "public, max-age=31536000, immutable");
            }
          },
        }),
      );

      // /ui is the canonical entry point linked from the SignalK admin panel
      router.get("/ui", (_req, res) => {
        const htmlPath = path.join(publicDir, "index.html");
        if (fs.existsSync(htmlPath)) {
          res.sendFile(htmlPath);
        } else {
          res
            .status(503)
            .send(
              "<!doctype html><html><body>" +
                "<h2>Notebook not built</h2>" +
                "<p>Run <code>npm run build:wasm</code> in the plugin directory.</p>" +
                "</body></html>",
            );
        }
      });
    },

    schema: { type: "object", properties: {} },

    start(): void {
      app.setPluginStatus(`Data Lab Notebooks ready — open /plugins/${PLUGIN_ID}/ui`);
    },

    stop(): void {
      app.setPluginStatus("Stopped");
    },
  };

  return plugin;
};
