# youtube_explode

A pure Dream port of YoutubeExplode's core library at upstream commit
`c721f98d1d3272fa7f100f30ed04bd8e20efff0e`. The converter extension and demos are
outside this package's scope. HTTP uses `system.net.HttpClient`; markup and SHA-1
use the pure Dream `markup` and `sha1` packages.

## Install

```bash
dreamer add youtube_explode
```

For a local checkout:

```toml
[dependencies]
youtube_explode = { path = "../dream-packages/youtube_explode" }
```

## Offline caption parsing

```dream
import system;
import youtube_explode;

fun main(): void {
    let parsed = ClosedCaptionTrack.parse_xml(
        "<timedtext><body><p t='1000' d='2000'><s>Hello &amp; world</s></p></body></timedtext>"
    );
    if parsed.is_err() {
        System.println(parsed.unwrap_err().message());
        return;
    }
    let track = parsed.unwrap();
    System.println(track.get_by_time(1500.0d).unwrap().text);
}
```

This prints `Hello & world`. `track.to_srt()` returns numbered SRT cues with LF
line endings. Times are doubles in milliseconds; SRT truncates fractional
milliseconds. Caption time lookup includes both endpoints and selects the first
source-ordered caption when ranges overlap. Part lookup preserves upstream's rule:
the first part whose relative offset is at or after the requested time.

## Search and pagination

This complete program prints up to three video results. It needs access to YouTube;
transport and extraction failures are printed as typed errors.

```dream
// Requires YouTube network access.
import system;
import youtube_explode;

async fun main(): void {
    let client = YoutubeClient();
    let count = 0;
    await for (let result in client.search.results(
        "Dream programming language",
        SearchFilter.Video
    )) {
        if result.is_err() {
            System.println(result.unwrap_err().code() + ": " + result.unwrap_err().message());
            break;
        }
        System.println(result.unwrap().title + " " + result.unwrap().url);
        count = count + 1;
        if count >= 3 {
            break;
        }
    }
    client.close().unwrap();
}
```

`SearchClient.get_page(query, filter, continuation)` retrieves one `SearchPage`.
`page.results` is a snapshot and `page.continuation` is `None` at EOF. `batches`
lazily yields `Result<YoutubeBatch<SearchResult>, YoutubeError>`; `results` flattens
those batches. Both deduplicate IDs across pages. Repeated continuation tokens end
iteration instead of looping indefinitely. A failed page yields one `Err` and ends.
Breaking `await for` or closing its iterator stops further page requests.

`SearchFilter.All`, `.Video`, `.Playlist`, and `.Channel` control the request.
Switch on a `SearchResult`'s `Video`, `Playlist`, or `Channel` variant to access its
specific ID, uploader/owner, duration, and thumbnails. Common `title` and `url`
properties work for every kind. Video results with malformed uploader IDs are
skipped as upstream does. Both classic renderers and playlist lockups are parsed.

## Client lifetime and cookies

`YoutubeClient()` owns a default HTTP client. Its `videos`, `streams`,
`closed_captions`, `channels`, `playlists`, and `search` properties share connection
pools and a native YouTube cookie jar. `close()` cancels requests on an owned HTTP
client. Extracted service objects retain the HTTP client if the facade is released.

`YoutubeClient(Option.Some(http))` uses a caller-owned `HttpClient`; closing the
facade leaves it open. Individual service clients also accept `http`, an optional
`origin`, and an optional `cookies` jar. Closing the shared HTTP client cancels all
pending operations. Received response bodies are closed on success and failure.
`origin` selects a fixture or compatible mirror for watch/API/player-source requests;
absolute stream and caption URLs remain as supplied by YouTube.

On native hosts, an omitted jar creates an in-memory `system.net.CookieJar`.
The facade shares it across all services. Like upstream's YouTube handler, this
YouTube-specific jar is separate from a supplied raw HTTP client's automatic jar.
Pass a populated jar through the `cookies` constructor argument for authenticated
requests; use `CookieJar.store` with a YouTube URL and a Set-Cookie-formatted value.
Cookies are neither loaded from a browser nor saved to disk.

The request policy seeds YouTube's pinned SOCS consent cookie without replacing a
supplied SOCS value, ingests Set-Cookie, and respects cookie expiry, domains, paths,
and secure matching through the stdlib jar. SAPISIDHASH authentication prefers
`__Secure-3PAPISID` over `SAPISID`, using a fresh timestamp and the request's scheme
and host, matching the pinned upstream handler. Existing credentials are never
included in error messages. HTTP 5xx responses retry five times; HTTP 429 never
retries and returns `rate_limited`. Localization, API keys, Origin, and default
user-agent headers are supplied automatically.

Node supports stateless public requests. The stdlib does not expose managed cookie
jars there; supplied jars and cookie-based authentication require a native host.
The default Node requests still include YouTube consent where applicable.

## Video, channel, and playlist metadata

- `client.videos.get(VideoId.parse(input).unwrap())` fetches metadata through the
  watch page and player fallbacks. Duration is optional; view counts retain exact
  64-bit integers. Metadata includes upload date, description, uploader, keywords,
  engagement, and thumbnails, including upstream's default video images.
- `client.channels.get(id)`, `get_by_handle`, `get_by_user`, and `get_by_slug`
  resolve canonical channels. Identifier parsers accept raw values and upstream
  URL forms; a raw handle excludes `@`, while its URL includes it.
  `channel.uploads_playlist_id` derives the UU playlist. `client.channels.uploads`
  lazily enumerates its videos. The Movies & TV channel uses upstream's static art.
- `client.playlists.get(id)` tries browse metadata, then next for system playlists.
  Owner and count can be absent; description defaults to empty. `video_batches`
  and `videos` lazily follow the last video/index and visitor token, suppressing
  duplicate IDs. Unavailability after a successful indexed page ends iteration.
  Initial system playlists receive the upstream warm-up request when needed.

Broken watch and channel pages retry up to six attempts. Offline extraction is
available through `Video.from_player_response`, `Video.from_watch_page`,
`Channel.from_page`, `Playlist.from_browse_response`, `Playlist.from_next_response`,
and `SearchPage.from_response`. Invalid required metadata returns `extraction`;
unavailable playlists/videos return `unavailable`.

## Stream manifests and downloads

`client.streams.get_manifest(id)` uses VisionOS/Android player fallbacks, cached
visitor data, cached player signatures, and the TV timestamp fallback. It parses
progressive formats and DASH, skips SABR-only entries, probes missing sizes with
HEAD, and verifies final bytes before including streams. `filter(kind)`,
`highest_bitrate`, and `highest_video_quality` select streams; empty selections
return `None`. `get_hls_url` returns live-video HLS URLs.

`StreamInfo.kind` identifies audio-only, video-only, or muxed components. Optional
fields describe audio language/default status, codecs, video quality/resolution,
and super-resolution flags. `container` is a `Container`; `bitrate` is a `Bitrate`.
`size` is `Option<FileSize>` because offline parsers can encounter unknown lengths.
HTTP-verified manifests contain sizes. Access exact values through `size.unwrap().bytes`
and `bitrate.bits_per_second`; conversions use binary scales of 1024. These value
types support comparison, equality, hashing, and readable unit formatting.

`client.streams.get(info)` opens a `MediaStream` implementing `system.io.AsyncReader`.
Use `read_async`, absolute `seek`, `tell`, and `length`, then close it explicitly.
Seeking beyond EOF is allowed. Negative positions, concurrent reads, and closed
streams return I/O errors. Downloads request ranges of at most 9,898,989 bytes
unless `ratebypass=yes` is advertised. Read transport failures retry five times
from the next undelivered byte; persistent truncation returns `EEOF`.

`copy_to(info, writer, progress)` copies into an `AsyncWriter`, handles partial
writes, flushes on success, and leaves the writer open. `download(info, path, progress)`
creates/truncates and always closes a file. Both return the byte count. Progress is
an optional `fun(double): void` callback receiving completed fractions in [0, 1].
Failures retain partial output; cancellation before opening leaves existing files
untouched. A supplied cancellation token overrides the structured task's inherited
one; rate limits and cancellation are not retried.

A pay-to-play response returns `purchase_required`, with its trailer identifier in
`error.preview_video_id`.

## Caption retrieval and SRT output

`client.closed_captions.get_manifest(id)` lists tracks. `get_by_language` accepts a
language code or display name ignoring case. Missing caption metadata yields an
empty manifest. `get(track_info)` downloads at most 16 MiB, sets `format=3` and
`fmt=3`, and parses srv3 XML, including namespaces and CDATA. Empty text and missing
or invalid t/d timing are skipped; whitespace-only text is preserved. Part timing
uses t, then ac, then zero.

`write_to(track_info, writer, progress)` writes UTF-8 SRT to an `AsyncWriter`,
handles partial writes, reports progress after complete cues, and flushes on success.
It leaves the destination open and reports no progress for an empty track.
`download(track_info, path, progress)` creates/truncates and always closes a file.
Both return the byte count. Errors and cancellation preserve completed writes.
SRT replaces embedded `-->` sequences with en-dash arrows and rejects cue times
that cannot be represented safely.

## Errors and scope

Client operations return `Result` with `YoutubeError`; async iterables yield one
terminal error. Categories are `invalid_input`, `extraction`, `unavailable`,
`unplayable`, `purchase_required`, `http`, `io`, `cancelled`, and `rate_limited`.
`MediaStream.read_async` uses `IoError` to satisfy the standard reader interface.
Metadata arrays are snapshots rather than mutable views into stored collections.

The core capabilities above mirror the pinned upstream implementation through
Dream APIs, rather than C# interface names, blocking wrappers, or deprecated aliases.
No player JavaScript is executed: only upstream's reverse/swap/splice transforms
are recognized. YouTube can change response schemas and player code independently
of this package; unsupported forms return extraction errors. Browser-only fetching,
converter/transcoding support, and a full browser HTML5 parser are outside this port.

## Validation

`dreamer test` and `dreamer test --release` run the workspace's native/Node fixtures.
The full offline qualification also checks module declarations, formatting, runnable
README examples, compilation of network examples without executing them, archive
licenses, clean registry installation, and loopback HTTP contracts:

```bash
python scripts/qualify.py --dream /path/to/dream --dreamer /path/to/dreamer
```

`qualify_youtube.py` exercises video/caption/stream HTTP behavior, seeking, SRT output,
files, partial writes, progress, and cancellation. `qualify_youtube_browsing.py`
exercises channel resolution, playlist/search paging, early exit, duplicate handling,
request policy, purchase errors, and native authenticated-cookie behavior.
Both accept `--release`; fixtures contact only their loopback servers, not YouTube.

## License and attribution

Adapted from [YoutubeExplode](https://github.com/Tyrrrz/YoutubeExplode), by Oleksii Holub.

MIT License

Copyright (c) 2016-2026 Oleksii Holub

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
