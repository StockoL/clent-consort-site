"""
Builds choir/static/css/site/site.min.css: every file index.css imports,
in the same order and cascade layers, joined into one minified file.

    python scripts/build_css.py

The source files stay the ones to edit, and index.css still loads them
directly when DEBUG is on. In production the browser fetches this one file
instead of index.css followed by its 52 imports one after another, which
held back every page's first paint. build.sh runs it before collectstatic;
the output is generated, like staticfiles/, and not tracked.

Each `@import "x.css" layer(name);` becomes `@layer name{...x.css...}`,
which the cascade treats the same way. Relative url()s are rewritten for
the bundle's location. The minifying is deliberately conservative:
comments and repeated whitespace go, and spaces around { } ; , and after :
(none of which carry meaning there); quoted strings are left untouched.
"""

import posixpath
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "choir" / "static" / "css" / "site"
INDEX = SITE / "index.css"
OUTPUT = SITE / "site.min.css"

IMPORT = re.compile(r'@import\s+"([^"]+)"\s+layer\((\w+)\)\s*;')
LAYER_ORDER = re.compile(r"@layer\s+[\w\s,]+;")
URL = re.compile(r'url\(\s*(["\']?)([^"\')]+)\1\s*\)')
# Comments and strings in one pass, so whichever opens first wins: an
# apostrophe inside a comment isn't a string, and /* inside a string isn't
# a comment.
COMMENT_OR_STRING = re.compile(r'/\*.*?\*/|"(?:[^"\\\n]|\\.)*"|\'(?:[^\'\\\n]|\\.)*\'', re.S)


def minify(css):
    strings = []

    def strip_or_keep(match):
        if match.group(0).startswith("/*"):
            return " "
        strings.append(match.group(0))
        return f"\0{len(strings) - 1}\0"

    css = COMMENT_OR_STRING.sub(strip_or_keep, css)
    css = re.sub(r"\s+", " ", css)
    css = re.sub(r"\s*([{};,])\s*", r"\1", css)
    css = re.sub(r":\s+", ":", css)
    css = css.replace(";}", "}")
    return re.sub(r"\0(\d+)\0", lambda m: strings[int(m.group(1))], css).strip()


def rebase_urls(css, source):
    """Rewrite relative url()s in `source` (a path under SITE) so they
    resolve the same from the bundle's folder."""
    folder = posixpath.dirname(source)

    def rebase(match):
        quote, url = match.groups()
        if url.startswith(("data:", "http:", "https:", "/", "#")):
            return match.group(0)
        target = posixpath.normpath(posixpath.join(folder, url))
        return f'url("{target}")'

    return URL.sub(rebase, css)


def build(output=OUTPUT):
    index = INDEX.read_text(encoding="utf-8")
    order = LAYER_ORDER.search(index)
    imports = IMPORT.findall(index)
    if not order or not imports:
        sys.exit("build_css: index.css has no @layer order or no imports")
    parts = [order.group(0)]
    for path, layer in imports:
        css = (SITE / path).read_text(encoding="utf-8")
        parts.append(f"@layer {layer}{{{minify(rebase_urls(css, path))}}}")
    bundle = "\n".join(parts) + "\n"
    output.write_text(bundle, encoding="utf-8")
    return imports, bundle


if __name__ == "__main__":
    imports, bundle = build()
    source = sum((SITE / path).stat().st_size for path, _ in imports)
    print(f"build_css: {len(imports)} files, {source:,} bytes -> {OUTPUT.name}, {len(bundle.encode()):,} bytes")
