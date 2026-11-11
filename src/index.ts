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

// Everything public/ holds: top-level files (all have an extension, which
// keeps "config" out), and anything under assets/ or wheels/
const READONLY_STATIC_ROUTES = ["/:file([\\w.-]+\\.\\w+)", "/assets/*", "/wheels/*"];

module.exports = function (app: ServerAPI): Plugin {
  // SignalK serves public/ at /@rhizomatics/signalk-datalab-plugin itself, as
  // the package has the signalk-webapp keyword; this router adds /ui under
  // /plugins/<id>, which is for admins only
  const publicDir = path.join(__dirname, "..", "public");

  const plugin: Plugin = {
    id: PLUGIN_ID,
    name: "SignalK Data Lab",
    description: "Interactive data analysis notebooks for SignalK, using Marimo running in the browser — no Python required on the server.",

    registerWithRouter(router: PluginRouter) {
      // gzip the top-level HTML pages (not cached, so worth shrinking on
      // every visit). Skip assets/ and wheels/: they're content-hashed and
      // immutable-cached below, so each file is fetched at most once per
      // client — compressing multi-MB JS/WASM chunks on every request was
      // pure CPU cost, and saturated the threadpool badly enough on
      // resource-constrained servers to blow past the pyodide worker's RPC
      // startup timeout.
      router.use(compression({ filter: (req) => !IMMUTABLE_DIR_PATTERN.test(req.path) }));

      // With these headers, a page served over HTTPS (or from localhost) is
      // cross-origin isolated, which gives marimo the SharedArrayBuffer it
      // uses to interrupt a running cell. Without isolation, marimo only
      // logs "interrupts are not available" and otherwise works normally.
      // Browsers never isolate a plain-HTTP page on another host (such as
      // http://boat.local:3000), so there these headers have no effect.
      router.use((_req, res, next) => {
        res.setHeader("Cross-Origin-Opener-Policy", "same-origin");
        res.setHeader("Cross-Origin-Embedder-Policy", "require-corp");
        next();
      });

      // Serve all WASM bundle assets (JS chunks, fonts, icons, …). Hashed
      // filenames under assets/ and wheels/ get a far-future immutable
      // cache so repeat visits (e.g. from the same boat browser) skip the
      // network entirely instead of re-fetching hundreds of files.
      const serveStatic = express.static(publicDir, {
        setHeaders(res, filePath) {
          if (IMMUTABLE_DIR_PATTERN.test(filePath)) {
            res.setHeader("Cache-Control", "public, max-age=31536000, immutable");
          }
        },
      });

      // /ui is the canonical entry point, linked from the SignalK admin panel
      // and redirected to from the webapp copy of the gallery
      const sendGallery: express.RequestHandler = (_req, res) => {
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
      };

      // Plugin routes are admin-only, unless (on servers 2.31 and later) they
      // are registered through router.access(). The server matches each
      // route's path (path-to-regexp 0.1) against the request, so a blanket
      // "/*" would also open up the server's own GET /plugins/<id>/config;
      // instead, only files with an extension, and the two asset folders.
      if (typeof router.access === "function") {
        const readonly = router.access("readonly");
        readonly.get("/ui", sendGallery);
        for (const route of READONLY_STATIC_ROUTES) {
          readonly.get(route, serveStatic);
        }
      } else {
        router.use("/", serveStatic);
        router.get("/ui", sendGallery);
      }
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
