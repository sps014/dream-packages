# markup

HTML scraping and namespace-aware XML parsing, implemented entirely in Dream.
There are no native libraries, FFI bindings, JavaScript helpers, or runtime Python dependencies.

## Use in a local project

```toml
[dependencies]
markup = { path = "../dream-packages/markup" }
```

```dream
import system;
import markup;

fun main(): void {
    let result = MarkupDocument.parse_xml(
        "<feed xmlns='urn:feed'><item id='7'>Hello &amp; welcome</item></feed>"
    );
    if result.is_err() {
        let error = result.unwrap_err();
        System.println(error.position.to_string() + ": " + error.message);
        return;
    }

    let document = result.unwrap();
    let item = document.elements("item")[0];
    System.println(item.namespace_uri);
    System.println(item.attribute("id").unwrap_or("missing"));
    System.println(item.text_content());
}
```

Output:

```text
urn:feed
7
Hello & welcome
```

For HTML, use `MarkupDocument.parse_html(source)`. Names and attribute lookups
are ASCII case-insensitive. XML names are case-sensitive.

```dream
import system;
import markup;

fun main(): void {
    let result = MarkupDocument.parse_html(
        "<META name='description' content='A &amp; B'><script>if (a < b) run();</script>"
    );
    if result.is_err() {
        System.println(result.unwrap_err().message);
        return;
    }

    let document = result.unwrap();
    System.println(document.elements("meta")[0].attribute("content").unwrap_or(""));
    System.println(document.elements("script")[0].text_content());
}
```

This prints `A & B` followed by `if (a < b) run();`.

## Behavior

- `nodes` contains top-level nodes, including comments and processing instructions.
- `root` is the first top-level element, or `None` for HTML containing only text.
- `elements(name)` and `node.descendants(name)` return source-ordered element snapshots.
  An empty name matches all elements; `descendants` excludes the receiver.
- Nodes expose `kind`, `name`, `local_name`, `namespace_uri`, `text`, `children`, and `attributes`.
- `attribute(name)` returns a qualified-name match; `attribute_ns(uri, local_name)`
  matches the resolved namespace. Missing attributes return `None`.
- `text_content()` concatenates character data while excluding comments and instructions.
  HTML script/style content is preserved as raw text; title/textarea entities are decoded.
- `MarkupText.decode_html(text, attribute: false)` and `decode_xml(text)` decode
  references without treating the result or literal angle brackets as markup.
  XML decoding returns `Result<string, MarkupError>`; HTML decoding preserves unknown references.
- All HTML named character references, legacy semicolonless forms, numeric references,
  attribute ambiguity rules, and numeric replacement rules are supported.
- XML supports namespaces, predefined/numeric entities, comments, CDATA, processing
  instructions, and XML 1.0 declarations. Unprefixed attributes have no namespace.

XML requires one complete root element, quoted unique attributes, matching end tags,
valid characters and namespace bindings. DTDs, custom entities, and external resources
are rejected. Input is already-decoded Dream text; encoding declarations do not transcode it.

HTML accepts fragments, unquoted/boolean attributes, void elements, optional end tags for
common paragraph/list/table/option cases, and malformed input recovery. It is a scraping
tree, not a conforming HTML5 browser DOM: it does not synthesize html/body/tbody wrappers,
implement the adoption-agency/foster-parenting algorithms, or switch to SVG/MathML rules.
`MarkupSelector.parse` supports the compound selectors needed by YoutubeExplode:
tag names and `*`, `#id`, `.class`, `[attribute]`, `[attribute=value]`, and
`*|local_name` for matching XML elements regardless of namespace prefix. Selectors
can combine these forms, for example `meta[property="og:url"]` or `*|p[t][d]`.
Unsupported combinators, groups, pseudo-classes, and CSS escapes return an error;
this is not a complete CSS-selector engine. HTML names ignore case and attribute
values match exactly. XML names and values remain case-sensitive.

Parse a selector once, then pass it to `document.query(selector)` or
`node.query(selector)`. Both return source-ordered arrays. Document queries include
root elements; node queries exclude the receiver. For example, after parsing a page:

```dream
import system;
import markup;

fun main(): void {
    let page = MarkupDocument.parse_html("<meta property='og:title' content='A &amp; B'>").unwrap();
    let parsed = MarkupSelector.parse("meta[property='og:title']");
    if parsed.is_err() {
        System.println(parsed.unwrap_err().message);
        return;
    }
    let matches = page.query(parsed.unwrap());
    if matches.length > 0 {
        System.println(matches[0].attribute("content").unwrap_or(""));
    }
}
```

This prints `A & B`. Script text follows the HTML escaped/double-escaped states,
and `/>` does not close non-void HTML elements. XML empty-element syntax is preserved.

## Limits and errors

Both parse methods accept `max_chars` (default 16,777,216 UTF-16 units), `max_nodes`
(default 100,000 nodes plus attributes), and `max_depth` (default 128 element levels).
Depth must be 1 through 512; the node limit must be positive and the character limit
nonnegative. Violations return `Err(MarkupError)` without exposing a partial tree.

Document parsing normalizes CRLF and CR to LF. Text decoding does not normalize them.
Error positions are zero-based UTF-16 positions in the corresponding input.
Returned child/attribute arrays are snapshots and nodes
are immutable through the public API. No parent links or external resource ownership
need manual cleanup.

## Validation

From the repository root, run `dreamer test -p markup_tests` and
`dreamer test -p markup_tests --release`. Tests cover native and Node hosts, the
complete named-reference table, namespace scope, CDATA, raw HTML text, malformed
inputs, and resource limits. Python is only used by development scripts to regenerate
reference fixtures and verify standard data.

## YoutubeExplode extraction coverage

Reviewed against core upstream commit `c721f98d1d3272fa7f100f30ed04bd8e20efff0e`:

| Upstream extraction | Dream operation |
| --- | --- |
| Channel Open Graph URL/title/image | `meta[property="..."]` selectors and `attribute("content")` |
| Watch-page availability and upload dates | `#player` in a subtree and `meta[itemprop="..."]` selectors |
| Inline player configuration/response | `elements("script")` and raw `text_content()` |
| DASH representations, URLs, and audio configuration | `*|Representation`, `*|BaseURL`, and `*|AudioChannelConfiguration` selectors |
| Caption/part text and timing | `*|p`, `*|s`, child arrays, `text_content()`, and attributes |

`*|local_name` supports namespace-insensitive extraction without stripping XML
namespace information. Use direct child arrays when an extraction requires direct
children rather than descendants. Keep original page text separately for regex
extraction; parsing normalizes newlines.

The script handling follows the
[HTML parsing specification](https://html.spec.whatwg.org/multipage/parsing.html#script-data-state).
Tests use synthetic watch/channel, DASH, and caption fixtures, including prefixed
namespaces and escaped script text. They validate these parsing primitives;
complete YoutubeExplode parity still requires the port's extraction and HTTP tests.

## License

The parser code is MIT-licensed. The HTML named-reference table is derived from
Python's `html.entities.html5`; the Python license and notices ship in
[src/licenses/PYTHON-LICENSE.txt](src/licenses/PYTHON-LICENSE.txt).

MIT License

Copyright (c) 2026 Shivendra Pratap Singh

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
