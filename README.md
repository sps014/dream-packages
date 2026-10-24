# dream-packages

Official Dream libraries, published to [`sps014/dream-registry`](https://github.com/sps014/dream-registry).

The compiler and package manager live in [`sps014/dream`](https://github.com/sps014/dream). Install packages with [`dreamer`](https://github.com/sps014/dream/blob/main/docs/reference/tooling/dreamer.md).

| Package | Description |
|---|---|
| [`semver`](semver/) | Parse, compare, and match Semantic Versioning requirements |
| [`markup`](markup/) | Pure Dream HTML scraping and namespace-aware XML parsing |
| [`sha1`](sha1/) | Pure Dream SHA-1 for existing protocol interoperability |
| [`youtube_explode`](youtube_explode/) | YouTube metadata, channels, playlists, search, streams, downloads, and captions |

```bash
dreamer add semver
```

Install the other packages with `dreamer add markup`, `dreamer add sha1`, or
`dreamer add youtube_explode`. The current versions are `markup` 0.1.0,
`sha1` 0.1.0, `semver` 0.1.2, and `youtube_explode` 0.1.0.
Run `dreamer test` and `dreamer test --release` at this workspace root to test
native and Node targets.

Every library source declares its package module.
To check module declarations, formatting, tests, runnable README examples, and
installation of the workspace libraries from a temporary registry, run:

```bash
python scripts/qualify.py --dream /path/to/dream --dreamer /path/to/dreamer
```
