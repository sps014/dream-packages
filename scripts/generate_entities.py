"""Regenerate the pure Dream HTML reference table and its complete decoding fixture."""
import argparse
import html.entities
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def expressions(text):
    return "\n        + ".join(json.dumps(text[i:i + 600], ensure_ascii=False)
                              for i in range(0, len(text), 600))


def artifacts():
    entries = sorted(html.entities.html5.items())
    if len(entries) != 2231:
        raise SystemExit("The upstream entity table changed; review the data and license before updating.")
    rows = [name + "=" + ",".join(f"{ord(c):X}" for c in value) + "\n"
            for name, value in entries]
    chunks = ["".join(rows[i:i + 24]) for i in range(0, len(rows), 24)]
    data = ("module markup;\n\n"
            "// WHATWG named character references, represented as name=Unicode scalars.\n"
            "// Generated from Python html.entities.html5 by scripts/generate_entities.py.\n"
            "internal static class HtmlEntityData {\n"
            "    internal static fun table(): string {\n        return "
            + "\n            + ".join(json.dumps(chunk) for chunk in chunks)
            + ";\n    }\n}\n")
    source = "<r>" + "".join("&" + name + "|" for name, _ in entries) + "</r>"
    expected = "".join(value + "|" for _, value in entries)
    test = ("module markup_tests;\nimport system.testing;\nimport markup;\n\n@test\n"
            "fun complete_html_named_reference_table(): void {\n    let source = "
            + expressions(source) + ";\n    let expected = " + expressions(expected)
            + ";\n    Assert.eq(MarkupDocument.parse_html(source).unwrap().root.unwrap().text_content(), expected);\n}\n")
    return {ROOT / "markup/src/html_entity_data.dream": data,
            ROOT / "tests/markup/entities.dream": test}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for path, expected in artifacts().items():
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != expected:
                raise SystemExit(f"Stale reference data: {path}")
        else:
            path.write_text(expected, encoding="utf-8", newline="\n")
    print("HTML references: 2231 entries verified." if args.check else "HTML references generated.")


if __name__ == "__main__":
    main()
