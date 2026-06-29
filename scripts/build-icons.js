const fs = require('node:fs');
const path = require('node:path');
const { Resvg } = require('@resvg/resvg-js');

const root = path.join(__dirname, '..');
const svg = fs.readFileSync(path.join(root, 'assets', 'logo.svg'));
const outDir = path.join(root, 'public');

const sizes = {
  'android-chrome-512x512.png': 512,
  'android-chrome-192x192.png': 192,
  'apple-touch-icon.png': 180,
  'favicon-32x32.png': 32,
  'favicon-16x16.png': 16,
};

for (const [filename, size] of Object.entries(sizes)) {
  const resvg = new Resvg(svg, { fitTo: { mode: 'width', value: size } });
  fs.writeFileSync(path.join(outDir, filename), resvg.render().asPng());
}

fs.copyFileSync(path.join(root, 'assets', 'logo.svg'), path.join(outDir, 'logo.svg'));
