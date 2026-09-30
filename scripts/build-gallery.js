// Writes public/index.html: a static gallery with a card per notebook. Each
// card's title and description come from the notebook's opening markdown cell
// (its "# heading" and first paragraph), so the gallery stays in step with the
// notebooks. Plain HTML, so it loads instantly; a notebook's Python runtime
// only downloads when someone opens it.
const fs = require("node:fs");
const path = require("node:path");

const root = path.join(__dirname, "..");
const notebooksDir = path.join(root, "notebooks");
const publicDir = path.join(root, "public");

// Data Lab is the main interface, so it comes first and is marked as such
const MAIN = "signalk.py";
const MAIN_PAGE = "datalab.html";

function pageFor(notebook) {
  return notebook === MAIN ? MAIN_PAGE : `${path.parse(notebook).name}.html`;
}

function escapeHtml(text) {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

// Enough markdown for a description: links become their text, plus `code`
// and **bold**
function inlineMarkdown(text) {
  return escapeHtml(text)
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
}

function describe(notebook) {
  const source = fs.readFileSync(path.join(notebooksDir, notebook), "utf8");
  const intro = source.match(/mo\.md\(r?"""([\s\S]*?)"""\)/);
  const lines = intro ? intro[1].split("\n").map((line) => line.trim()) : [];
  const heading = lines.find((line) => line.startsWith("# "));
  const start = lines.indexOf(heading) + 1;
  const paragraph = [];
  for (const line of lines.slice(start)) {
    if (line === "" && paragraph.length) break;
    if (line !== "") paragraph.push(line);
  }
  return {
    title: heading ? heading.slice(2) : path.parse(notebook).name,
    description: paragraph.join(" "),
    page: pageFor(notebook),
    main: notebook === MAIN,
  };
}

function card({ title, description, page, main }) {
  return `
      <a class="card${main ? " main" : ""}" href="${page}">
        ${main ? '<span class="badge">Start here</span>' : ""}
        <h2>${escapeHtml(title)}</h2>
        <p>${inlineMarkdown(description)}</p>
        <span class="open">Open notebook →</span>
      </a>`;
}

function buildGallery(notebooks) {
  const ordered = [MAIN, ...notebooks.filter((f) => f !== MAIN).sort()].filter((f) => notebooks.includes(f));
  const cards = ordered.map(describe).map(card).join("\n");
  const html = `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>SignalK Data Lab</title>
    <link rel="icon" href="favicon.ico" />
    <link rel="icon" type="image/png" sizes="32x32" href="favicon-32x32.png" />
    <link rel="apple-touch-icon" href="apple-touch-icon.png" />
    <style>
      :root {
        --bg: #f6f7f9;
        --card: #ffffff;
        --text: #1b1f24;
        --muted: #5b6470;
        --border: #dde1e6;
        --accent: #0b6e99;
        --accent-soft: #e3f1f8;
      }
      @media (prefers-color-scheme: dark) {
        :root {
          --bg: #111418;
          --card: #1a1f25;
          --text: #e6e9ed;
          --muted: #9aa4af;
          --border: #2c333b;
          --accent: #5cb8e0;
          --accent-soft: #16303d;
        }
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        background: var(--bg);
        color: var(--text);
        font: 16px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
      }
      main { max-width: 1040px; margin: 0 auto; padding: 32px 16px 48px; }
      header { display: flex; align-items: center; gap: 16px; margin-bottom: 8px; }
      header img { width: 56px; height: 56px; }
      h1 { font-size: 1.8rem; margin: 0; }
      .intro { color: var(--muted); margin: 0 0 28px; max-width: 70ch; }
      .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(290px, 1fr)); gap: 16px; }
      .card {
        position: relative;
        display: flex;
        flex-direction: column;
        padding: 20px;
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 10px;
        color: inherit;
        text-decoration: none;
      }
      .card:hover, .card:focus-visible { border-color: var(--accent); }
      .card.main { grid-column: 1 / -1; background: var(--accent-soft); border-color: var(--accent); }
      .card h2 { font-size: 1.15rem; margin: 0 0 8px; }
      .card p { margin: 0 0 16px; color: var(--muted); flex: 1; }
      .card code { font-size: 0.9em; }
      .open { color: var(--accent); font-weight: 600; }
      .badge {
        align-self: flex-start;
        margin-bottom: 8px;
        padding: 2px 8px;
        border-radius: 999px;
        background: var(--accent);
        color: var(--card);
        font-size: 0.75rem;
        font-weight: 600;
      }
      footer { margin-top: 32px; color: var(--muted); font-size: 0.9rem; max-width: 70ch; }
      footer a { color: var(--accent); }
    </style>
  </head>
  <body>
    <main>
      <header>
        <img src="logo.svg" alt="" />
        <h1>SignalK Data Lab</h1>
      </header>
      <p class="intro">
        Notebooks for exploring your boat's SignalK data, running entirely in your browser. Start with Data Lab, or try one of
        the experiments; each one explains its approach and its limitations when it opens.
      </p>
      <div class="grid">
${cards}
      </div>
      <footer>
        <p>
          Opening a notebook needs an internet connection, to load Python and some of its packages; the first time takes a
          while, and your browser keeps them for next time. Built with <a href="https://marimo.io">marimo</a>.
        </p>
      </footer>
    </main>
  </body>
</html>
`;
  fs.writeFileSync(path.join(publicDir, "index.html"), html);
}

module.exports = { buildGallery, MAIN, MAIN_PAGE, pageFor };

if (require.main === module) {
  const notebooks = fs
    .readdirSync(notebooksDir)
    .filter((f) => f.endsWith(".py"))
    .filter((f) => /^app = marimo\.App/m.test(fs.readFileSync(path.join(notebooksDir, f), "utf8")));
  buildGallery(notebooks);
}
