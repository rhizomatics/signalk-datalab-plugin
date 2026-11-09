import { defineCollection } from "astro:content";
import { docsLoader, i18nLoader } from "@astrojs/starlight/loaders";
import { docsSchema, i18nSchema } from "@astrojs/starlight/schema";

export const collections = {
  docs: defineCollection({ loader: docsLoader(), schema: docsSchema() }),
  // Starlight looks up its UI strings here on every page; defining the
  // collection, even with no translations, stops Astro warning that it's missing
  i18n: defineCollection({ loader: i18nLoader(), schema: i18nSchema() }),
};
