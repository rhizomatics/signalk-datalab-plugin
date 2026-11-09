// Renders GitHub's Markdown alerts in README.md, e.g.
//
//   > [!NOTE]
//   > Some text
//
// as Starlight asides, so the README needs no site-specific syntax: GitHub and
// npm show the same blockquotes as alerts. Starlight's own `:::note` directive
// isn't an option there, since GitHub would print it literally.
//
// A Sätteri mdast plugin, since Sätteri is Astro 7's Markdown processor
// (`markdown.remarkPlugins` would need the old unified processor). It turns the
// blockquote into the <aside class="starlight-aside starlight-aside--note">
// that Starlight's <Aside> renders, with its title, so Starlight's CSS styles
// it. Starlight's inner content <div> is left out, as the plugin only changes
// nodes in place rather than moving the blockquote's children.
import { defineMdastPlugin } from "satteri";

// GitHub has five alert types; Starlight has four aside variants
const VARIANTS = {
  NOTE: { variant: "note", title: "Note" },
  TIP: { variant: "tip", title: "Tip" },
  IMPORTANT: { variant: "note", title: "Important" },
  WARNING: { variant: "caution", title: "Warning" },
  CAUTION: { variant: "danger", title: "Caution" },
};

const MARKER = /^\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\][ \t]*\n?/;

export default defineMdastPlugin({
  name: "github-alerts",
  blockquote(node, ctx) {
    const paragraph = node.children?.[0];
    const text = paragraph?.type === "paragraph" ? paragraph.children?.[0] : undefined;
    const match = text?.type === "text" ? MARKER.exec(text.value) : null;
    if (!match) return;
    const { variant, title } = VARIANTS[match[1]];

    ctx.setProperty(node, "data", {
      hName: "aside",
      hProperties: {
        ariaLabel: title,
        className: ["starlight-aside", `starlight-aside--${variant}`],
      },
    });
    ctx.insertBefore(paragraph, {
      type: "paragraph",
      data: { hProperties: { className: ["starlight-aside__title"], ariaHidden: "true" } },
      children: [{ type: "text", value: title }],
    });

    // Then drop the [!TYPE] marker, and its paragraph if nothing else was in it
    const rest = text.value.slice(match[0].length);
    if (rest) ctx.setProperty(text, "value", rest);
    else if (paragraph.children.length > 1) ctx.removeNode(text);
    else ctx.removeNode(paragraph);
  },
});
