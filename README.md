# dream-packages

Official Dream libraries, published to [`sps014/dream-registry`](https://github.com/sps014/dream-registry).

The compiler and package manager live in [`sps014/dream`](https://github.com/sps014/dream). Install packages with [`dreamer`](https://github.com/sps014/dream/blob/main/docs/reference/tooling/dreamer.md).

| Package | Description |
|---|---|
| [`semver`](semver/) | Parse, compare, and match Semantic Versioning requirements |
| [`markup`](markup/) | Pure Dream HTML scraping and namespace-aware XML parsing |
| [`sha1`](sha1/) | Pure Dream SHA-1 for existing protocol interoperability |

```bash
dreamer add semver
```

The new `markup` and `sha1` packages are available as local path dependencies.
Registry publication follows package qualification. Run `dreamer test` and
`dreamer test --release` at this workspace root to test native and Node targets.

Every library source declares its package module (`semver`, `markup`, or `sha1`).
To check module declarations, formatting, tests, runnable README examples, and
installation of all three packages from a temporary registry, run:

```bash
python scripts/qualify.py --dream /path/to/dream --dreamer /path/to/dreamer
```
