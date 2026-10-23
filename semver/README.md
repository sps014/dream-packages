# semver

Parse, compare, and match [Semantic Versioning](https://semver.org/) requirements in Dream.
Useful for feature gates, plugin loaders, and any code that speaks the same version language as
`dream.toml` / `dreamer`.

## Install

```bash
dreamer add semver --version "^0.1"
```

```toml
[dependencies]
semver = "0.1"
```

## Usage

```dream
import system;
import system.text;
import semver;

fun main(): void {
    let v = SemVer.parse("1.2.3-beta.1+build").unwrap_or(SemVer(0, 0, 0, "", ""));
    System.println(v.to_string());
    System.println(v.major.to_string() + "." + v.minor.to_string() + "." + v.patch.to_string());

    let a = SemVer.parse("1.2.0").unwrap_or(SemVer(0, 0, 0, "", ""));
    let b = SemVer.parse("1.10.0").unwrap_or(SemVer(0, 0, 0, "", ""));
    System.println(SemVer.compare(a, b).to_string()); // -1
    System.println(a.lt(b));                           // true

    System.println(SemVer.satisfies(v, "^1.2"));              // true
    System.println(SemVer.satisfies(v, "~1.2.0"));             // true (same major.minor)
    System.println(SemVer.satisfies(v, ">=1.0.0, <2.0.0"));    // true
    System.println(SemVer.satisfies(v, "1.2.3"));              // false (exact; prerelease ≠ release)
}
```

## API

```dream
public class SemVer {
    public major: int;
    public minor: int;
    public patch: int;
    public prerelease: string;   // "" if none
    public build: string;        // "" if none

    public static fun parse(s: string): Result<SemVer, string>;
    public fun to_string(): string;

    public static fun compare(a: SemVer, b: SemVer): int;
    public fun eq(other: SemVer): bool;
    public fun lt(other: SemVer): bool;
    public fun lte(other: SemVer): bool;
    public fun gt(other: SemVer): bool;
    public fun gte(other: SemVer): bool;

    /// Supports exact (`1.2.3`), `^`, `~`, `>=` / `>` / `<=` / `<`,
    /// and comma-separated AND lists (`>=1.0.0, <2.0.0`).
    public static fun satisfies(version: SemVer, req: string): bool;
}
```

Build metadata is ignored for precedence (SemVer §10). A release version is greater than any
prerelease with the same numeric triple.

## Current limitations

The numeric core uses Dream's nonnegative `int` range; out-of-range values return
an error. Prerelease and build identifiers must be nonempty ASCII alphanumeric or
hyphen components. Numeric prerelease components cannot have leading zeros;
build components may. Prerelease precedence compares each component in sequence,
compares numeric identifiers by numeric value without integer conversion, orders
numeric identifiers below nonnumeric ones, and ignores build metadata.

Requirements support the operators listed above, with comma-separated AND
clauses; wildcards, OR clauses, and hyphen ranges are not supported.

## License

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
