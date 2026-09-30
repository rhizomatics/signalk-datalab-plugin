// Local preview of the WASM build in public/.
// The notebook calls the SignalK API on its own origin, so /signalk/* is
// proxied to a real server (SIGNALK_URL, default http://localhost:3000).
const http = require("node:http");
const https = require("node:https");
const path = require("node:path");
const express = require("express");

const root = path.join(__dirname, "..");
const port = Number(process.env.PORT || 8080);
const target = new URL(process.env.SIGNALK_URL || "http://localhost:3000");
const client = target.protocol === "https:" ? https : http;

const app = express();

app.use("/signalk", (req, res) => {
  const upstream = client.request(
    {
      protocol: target.protocol,
      hostname: target.hostname,
      port: target.port,
      method: req.method,
      path: req.originalUrl,
      headers: { ...req.headers, host: target.host },
    },
    (upRes) => {
      res.writeHead(upRes.statusCode, upRes.headers);
      upRes.pipe(res);
    },
  );
  upstream.on("error", (err) => {
    res.status(502).send(`SignalK proxy error (${target.origin}): ${err.code || err.message}`);
  });
  req.pipe(upstream);
});

app.use(express.static(path.join(root, "public")));

const server = app.listen(port, () => {
  console.log(`Data Lab preview on http://localhost:${port}/ (SignalK API -> ${target.origin})`);
});

// WebSocket connections (the Live Stream notebook's /signalk/v1/stream) arrive
// as upgrade requests, which express doesn't see, so forward them separately
server.on("upgrade", (req, socket, head) => {
  if (!req.url.startsWith("/signalk")) {
    socket.destroy();
    return;
  }
  const upstream = client.request({
    protocol: target.protocol,
    hostname: target.hostname,
    port: target.port,
    method: req.method,
    path: req.url,
    headers: { ...req.headers, host: target.host },
  });
  upstream.on("upgrade", (upRes, upSocket, upHead) => {
    const headers = [];
    for (let i = 0; i < upRes.rawHeaders.length; i += 2) {
      headers.push(`${upRes.rawHeaders[i]}: ${upRes.rawHeaders[i + 1]}`);
    }
    socket.write(`HTTP/1.1 101 Switching Protocols\r\n${headers.join("\r\n")}\r\n\r\n`);
    if (upHead.length) socket.write(upHead);
    if (head.length) upSocket.write(head);
    upSocket.pipe(socket).pipe(upSocket);
    upSocket.on("error", () => socket.destroy());
    socket.on("error", () => upSocket.destroy());
  });
  // The server answered without upgrading, e.g. 401 when security is on
  upstream.on("response", (upRes) => {
    socket.end(`HTTP/1.1 ${upRes.statusCode} ${upRes.statusMessage}\r\n\r\n`);
  });
  upstream.on("error", () => socket.destroy());
  upstream.end();
});
