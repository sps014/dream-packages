"""Qualify pure Dream packages, their examples, and registry archive installation."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def run(command, cwd=ROOT, capture=False):
    print("RUN " + " ".join(map(str, command)), flush=True)
    result = subprocess.run(command, cwd=cwd, check=True, text=True, encoding="utf-8",
                            stdout=subprocess.PIPE if capture else None,
                            stderr=subprocess.PIPE if capture else None)
    return result.stdout if capture else ""


def tool(explicit, variable, name):
    value = explicit or os.environ.get(variable) or shutil.which(name)
    if not value:
        raise SystemExit(f"Set {variable} or pass --{name}.")
    return str(Path(value).resolve())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dream")
    parser.add_argument("--dreamer")
    args = parser.parse_args()
    dream = tool(args.dream, "DREAM_BIN", "dream")
    dreamer = tool(args.dreamer, "DREAMER_BIN", "dreamer")
    os.environ["DREAM_BIN"] = dream
    members = tomllib.loads((ROOT / "dream.toml").read_text(encoding="utf-8"))["workspace"]["members"]
    packages = {}
    for member in members:
        folder = ROOT / member
        package = tomllib.loads((folder / "dream.toml").read_text(encoding="utf-8"))["package"]
        if package["type"] == "lib":
            packages[package["name"]] = package["version"]
        source_root = folder / "src" if package["type"] == "lib" else folder
        for directory, folders, files in os.walk(source_root):
            folders[:] = sorted(name for name in folders if name not in {"dream_packages", "target"})
            for name in sorted(files):
                source = Path(directory) / name
                if source.suffix == ".dream" and not source.read_text(encoding="utf-8").startswith(f'module {package["name"]};\n'):
                    raise SystemExit(f"Missing package module declaration: {source}")
    run([sys.executable, "scripts/generate_entities.py", "--check"])
    run([dream, "fmt", "--check", "markup/src", "sha1/src", "semver/src", "tests"])
    run([dreamer, "test"])
    run([dreamer, "test", "--release"])
    target = ROOT / "target"
    target.mkdir(exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="qualification-", dir=target))
    expected = {"markup": ["urn:feed\n7\nHello & welcome\n", "A & B\nif (a < b) run();\n", "A & B\n"],
                "sha1": ["a9993e364706816aba3e25717850c26c9cd0d89d\n"],
                "semver": ["1.2.3-beta.1+build\n1.2.3\n-1\ntrue\ntrue\ntrue\ntrue\nfalse\n"]}
    for package, outputs in expected.items():
        text = (ROOT / package / "README.md").read_text(encoding="utf-8")
        examples = [code for code in re.findall(r"```dream\n(.*?)\n```", text, re.S)
                    if "fun main()" in code]
        if len(examples) != len(outputs):
            raise SystemExit(f"Review expected example outputs for {package}.")
        for index, (code, output) in enumerate(zip(examples, outputs)):
            path = work / f"{package}_example_{index}.dream"
            path.write_text("module " + package + "_example;\n" + code + "\n", encoding="utf-8", newline="\n")
            actual = run([dream, "run", path], capture=True)
            if output not in actual:
                raise SystemExit(f"Unexpected example output: {path}\n{actual}")
    registry = work / "registry"
    registry.mkdir()
    for package, version in packages.items():
        run([dreamer, "publish", "-p", package, "--registry", str(registry)])
        archive = registry / "dl" / package / f"{package}-{version}.tar.gz"
        if archive.stat().st_size > 10 * 1024 * 1024:
            raise SystemExit(f"Registry archive too large: {archive}")
        with tarfile.open(archive) as packed:
            names = packed.getnames()
            readme = packed.extractfile("README.md").read().decode("utf-8")
            if "MIT License" not in readme:
                raise SystemExit(f"Missing shipped license: {package}")
            if package == "markup" and "src/licenses/PYTHON-LICENSE.txt" not in names:
                raise SystemExit("Python table license is missing from the archive.")
    # Keep the consumer outside the workspace so no ancestor dependency install can satisfy imports.
    consumer = Path(tempfile.mkdtemp(prefix="dream-package-consumer-"))
    manifest = ('[package]\nname = "package_consumer"\nversion = "0.1.0"\ntype = "test"\n'
                '[dependencies]\n' + ''.join(f'{name} = "{version}"\n' for name, version in packages.items()) +
                '[registries]\ndefault = ' + json.dumps(str(registry)) + '\n'
                '[test]\ntargets = ["native", "node"]\n')
    (consumer / "dream.toml").write_text(manifest, encoding="utf-8", newline="\n")
    (consumer / "consumer.dream").write_text(
        'module package_consumer;\nimport system;\nimport system.testing;\nimport markup;\nimport sha1;\nimport semver;\n'
        '@test\nfun consumer(): void {\n'
        '    Assert.eq(SemVer.parse("1.2.3").unwrap().major, 1);\n'
        '    let doc = MarkupDocument.parse_xml("<r>A &amp; B</r>").unwrap();\n'
        '    Assert.eq(doc.root.unwrap().text_content(), "A & B");\n'
        '    Assert.eq(Encoding.hex_encode(Sha1.hash(Encoding.utf8_encode("abc"))), '
        '"a9993e364706816aba3e25717850c26c9cd0d89d");\n}\n',
        encoding="utf-8", newline="\n")
    run([dreamer, "test"], cwd=consumer)
    print(f"PASS: native/Node debug/release, README examples, archive licenses, and clean registry consumer. Evidence: {work}; consumer: {consumer}")


if __name__ == "__main__":
    main()
