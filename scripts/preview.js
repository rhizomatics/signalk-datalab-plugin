// Local preview of the WASM build in public/.
// The notebook calls the SignalK API on its own origin, so /signalk/* is
// proxied to a real server (SIGNALK_URL, default http://localhost:3000).
const http = require('node:http');
const https = require('node:https');
const path = require('node:path');
const express = require('express');

const root = path.join(__dirname, '..');
const port = Number(process.env.PORT || 8080);
const target = new URL(process.env.SIGNALK_URL || 'http://localhost:3000');
const client = target.protocol === 'https:' ? https : http;

const app = express();

app.use('/signalk', (req, res) => {
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
  upstream.on('error', (err) => {
    res.status(502).send(`SignalK proxy error (${target.origin}): ${err.code || err.message}`);
  });
  req.pipe(upstream);
});

app.use(express.static(path.join(root, 'public')));

app.listen(port, () => {
  console.log(`Data Lab preview on http://localhost:${port}/ (SignalK API -> ${target.origin})`);
});
