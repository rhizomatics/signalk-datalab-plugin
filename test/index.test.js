// Tests for the plugin entry point, run against the compiled dist/index.js
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const createPlugin = require("../dist/index.js");

function fakeApp() {
  const statuses = [];
  return { statuses, setPluginStatus: (message) => statuses.push(message) };
}

function fakeRouter() {
  const uses = [];
  const gets = {};
  return {
    uses,
    gets,
    use: (...args) => uses.push(args),
    get: (route, handler) => {
      gets[route] = handler;
    },
  };
}

function fakeResponse() {
  const res = { sentFile: null, statusCode: 200, body: null };
  res.sendFile = (file) => {
    res.sentFile = file;
  };
  res.status = (code) => {
    res.statusCode = code;
    return res;
  };
  res.send = (body) => {
    res.body = body;
  };
  return res;
}

void test("exports a plugin constructor", () => {
  assert.equal(typeof createPlugin, "function");
  const plugin = createPlugin(fakeApp());
  assert.equal(plugin.id, "signalk-datalab-plugin");
  assert.equal(plugin.name, "SignalK Data Lab");
  assert.equal(typeof plugin.description, "string");
  assert.deepEqual(plugin.schema, { type: "object", properties: {} });
});

void test("start and stop report plugin status", () => {
  const app = fakeApp();
  const plugin = createPlugin(app);
  plugin.start({}, () => {});
  plugin.stop();
  assert.equal(app.statuses.length, 2);
  assert.match(app.statuses[0], /\/plugins\/signalk-datalab-plugin\/ui/);
  assert.equal(app.statuses[1], "Stopped");
});

void test("registerWithRouter serves the bundle and a /ui entry point", () => {
  const router = fakeRouter();
  createPlugin(fakeApp()).registerWithRouter(router);
  assert.equal(router.uses.length, 2);
  assert.equal(typeof router.uses[0][0], "function");
  assert.equal(router.uses[1][0], "/");
  assert.equal(typeof router.uses[1][1], "function");
  assert.equal(typeof router.gets["/ui"], "function");
});

void test("/ui sends index.html when the notebook is built", (t) => {
  t.mock.method(fs, "existsSync", () => true);
  const router = fakeRouter();
  createPlugin(fakeApp()).registerWithRouter(router);
  const res = fakeResponse();
  router.gets["/ui"]({}, res);
  assert.equal(res.sentFile, path.join(__dirname, "..", "public", "index.html"));
});

void test("/ui explains how to build the notebook when it's missing", (t) => {
  t.mock.method(fs, "existsSync", () => false);
  const router = fakeRouter();
  createPlugin(fakeApp()).registerWithRouter(router);
  const res = fakeResponse();
  router.gets["/ui"]({}, res);
  assert.equal(res.statusCode, 503);
  assert.match(res.body, /npm run build:wasm/);
  assert.equal(res.sentFile, null);
});
