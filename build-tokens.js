/**
 * Clent Consort - Design Token Compiler
 * Forked from looseleaf-ui/build-tokens.js. Parses design-tokens.json and
 * writes native CSS Custom Properties to choir/static/css/site/global/
 * variables.css - this project's own single source of truth, no longer
 * synced from looseleaf-ui's generic/brand-neutral version.
 *
 * One extension beyond the upstream script: a category whose name ends in
 * "-invert" (e.g. "colors-invert") does not land in the main :root block.
 * Its keys compile to the same custom property names as the base category
 * they extend (colors-invert.surface-base -> --colors-surface-base, not
 * --colors-invert-surface-base) but are wrapped in a
 * ".invert, [data-variant=\"invert\"] { ... }" block instead - the same
 * dark-scope opt-in every inverted card on this site already uses. That
 * block also always sets color: var(--colors-text-base), since redefining
 * the custom properties alone doesn't apply any of them - confirmed the
 * hard way earlier in this project (text kept inheriting the light-theme
 * body color until this line existed).
 */

const fs = require("fs");
const path = require("path");

const tokenSourcePath = path.join(__dirname, "design-tokens.json");
const cssOutputPath = path.join(
  __dirname,
  "choir",
  "static",
  "css",
  "site",
  "global",
  "variables.css",
);

const INVERT_SUFFIX = "-invert";

try {
  if (!fs.existsSync(tokenSourcePath)) {
    throw new Error(`Source file missing at: ${tokenSourcePath}`);
  }

  const rawData = fs.readFileSync(tokenSourcePath, "utf8");
  const tokenGroups = JSON.parse(rawData);

  let rootContent = "";
  let invertContent = "";

  for (const [category, tokens] of Object.entries(tokenGroups)) {
    // 1. Skip over documentation block comments in the JSON source
    if (category.startsWith("_")) continue;

    const isInvert = category.endsWith(INVERT_SUFFIX);
    const propertyPrefix = isInvert
      ? category.slice(0, -INVERT_SUFFIX.length)
      : category;

    let block = `\n  /* --- ${category.toUpperCase()} --- */\n`;

    // JS object keys that look like a plain non-negative integer ("0",
    // "6") are always iterated in ascending numeric order ahead of every
    // other key, regardless of insertion order - a scale with negative
    // steps (e.g. step: "-2".."6") ends up with "-2"/"-1" reordered to
    // the end instead of the front. Re-sort numerically whenever every
    // key in a category is a plain integer, so generated output reads
    // in the same order it's defined in the design system (small..large).
    const entries = Object.entries(tokens).filter(([key]) => !key.startsWith("_"));
    const isPureIntegerScale = entries.every(([key]) => /^-?\d+$/.test(key));
    if (isPureIntegerScale) {
      entries.sort(([a], [b]) => Number(a) - Number(b));
    }

    for (const [key, value] of entries) {
      block += `  --${propertyPrefix}-${key}: ${value};\n`;
    }

    if (isInvert) {
      invertContent += block;
    } else {
      rootContent += block;
    }
  }

  let cssContent = `/* ==========================================================================
   AUTO-GENERATED CUSTOM PROPERTIES - DO NOT EDIT DIRECTLY
   ==========================================================================
   Generated on: ${new Date().toISOString().split("T")[0]}
   Source Document: design-tokens.json
   ========================================================================== */\n\n:root {\n${rootContent}}\n`;

  if (invertContent) {
    cssContent += `\n/* --------------------------------------------------------------------------
   DARK SCOPE - opt-in via .invert or [data-variant="invert"]
   -------------------------------------------------------------------------- */\n.invert,\n[data-variant="invert"] {\n${invertContent}\n  color: var(--colors-text-base);\n}\n`;
  }

  const outputDir = path.dirname(cssOutputPath);
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  fs.writeFileSync(cssOutputPath, cssContent, "utf8");
  console.log(
    "✨ Clent Consort tokens compiled cleanly to choir/static/css/site/global/variables.css",
  );
} catch (error) {
  console.error(`❌ Token compilation failed: ${error.message}`);
  process.exit(1);
}
