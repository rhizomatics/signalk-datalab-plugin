import { defineConfig } from "astro/config";
import starlight from "@astrojs/starlight";
import starlightLlmsTxt from "starlight-llms-txt";
import fs from "node:fs";
import GithubSlugger from "github-slugger";

function readmeSidebar() {
  const md = fs.readFileSync("../README.md", "utf8");
  const slugger = new GithubSlugger();
  const headings = [];

  for (const m of md.matchAll(/^(#{2,4})\s+(.+)$/gm)) {
    const text = m[2]
      .replace(/\[([^\]]*)\]\([^)]*\)/g, "$1")
      .replace(/[*`_~]/g, "")
      .trim();
    headings.push({ level: m[1].length, text, slug: slugger.slug(text) });
  }

  const build = (start, level, end = headings.length) => {
    const items = [];
    let i = start;
    while (i < end) {
      const h = headings[i];
      if (h.level !== level) {
        i++;
        continue;
      }
      // find children before the next heading of same-or-higher level
      let j = i + 1;
      while (j < end && headings[j].level > level) j++;
      const children = build(i + 1, level + 1, j);
      if (children.length) {
        items.push({
          label: h.text,
          collapsed: true,
          items: [{ label: "Overview", link: `/#${h.slug}` }, ...children],
        });
      } else {
        items.push({ label: h.text, link: `/#${h.slug}` });
      }
      i = j;
    }
    return items;
  };

  return build(0, 2);
}

export default defineConfig({
  site: "https://signalk-datalab.rhizomatics.org.uk",
  integrations: [
    starlight({
      title: "SignalK Data Lab Plugin",
      logo: {
        src: "../assets/logo.svg",
        replacesTitle: false,
      },
      social: [{ icon: "github", label: "GitHub", href: "https://github.com/rhizomatics/signalk-datalab-plugin" }],
      sidebar: [{ label: "Readme", link: "/" }, ...readmeSidebar()],
      plugins: [starlightLlmsTxt()],
    }),
  ],
});
