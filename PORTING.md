# YoutubeExplode port

Implement the core library at upstream commit
`c721f98d1d3272fa7f100f30ed04bd8e20efff0e` as `youtube_explode`, then publish to
`sps014/dream-registry`. Exclude the converter extension and demo applications.

## Prerequisites

All additional runtime package code is written in Dream. `markup` provides the
HTML/XML tree, queries, namespaces, and entity decoding. `sha1` provides the digest
needed for YouTube authentication. JSON, URLs, streams, cancellation, and HTTP use
Dream's existing standard library. Cookie storage belongs in `system.net` and is
committed in Dream as `60882226`; no curl transport or separate cookie package is used.

HTML parsing is deliberately a scraping tree rather than a browser DOM. The port
must verify upstream extraction against fixtures and add any required parsing
behavior here rather than silently dropping an upstream feature.

## Next work

Inventory every upstream public core API and test; record a Dream equivalent and
validation before implementation. Cover video/playlist/channel metadata, all channel
identifier forms and uploads, mixed/filtered paginated search, playlist batches,
stream manifests and selection, cipher resolution and client fallbacks, DASH/HLS,
segmented seekable downloads, captions/parts/time lookup/SRT, authentication, retries,
progress, and cancellation. Use typed Result errors and async iteration.

Build deterministic page/JSON/XML fixtures and local HTTP servers for failure modes.
Keep live YouTube smoke tests separate. Validate supported native platforms before
publishing prerequisites and `youtube_explode`, and verify a clean registry consumer.
Support-package implementation alone does not complete YoutubeExplode parity.
