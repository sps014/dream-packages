# youtube_explode

A pure Dream port of the core YoutubeExplode library at upstream commit
`c721f98d1d3272fa7f100f30ed04bd8e20efff0e`. This package is under development and
is not published. The converter extension and demos are outside the port's scope.

## Implemented

- Validated video, playlist, channel, handle, username, and legacy slug identifiers,
  including upstream URL forms, percent decoding, and Unicode names.
- Caption-track metadata extraction from player responses and language lookup.
- Caption/part parsing from srv3 XML, preserving whitespace and fractional millisecond
  timing, including prefixed namespaces, missing timings, and the ac timing fallback.
- Caption/part time lookup and portable SRT serialization with embedded-arrow handling.
- Caption HTTP retrieval through the caller's existing `HttpClient`, query-format
  normalization, cancellation, response cleanup, and categorized failures.
- Video metadata, watch-page extraction, legacy player configuration, thumbnail
  defaults, exact integer view counts, engagement, and upload-date fallback.
- Player requests with cached visitor data, VisionOS/Android fallbacks, and the TV
  signature-timestamp fallback for streams. Broken watch pages retry six times.
- Progressive and DASH stream manifests, audio languages, quality selection,
  signature transforms, cached player source, and size verification through HEAD
  and final-byte probes. SABR-only entries and unavailable streams are skipped.
- Seekable async downloads with bounded range requests, transport retries, partial
  writes, cancellation, file output, and progress callbacks. HLS URL retrieval.

Channel resolution/uploads, playlists, search pagination, purchase-preview errors,
and authenticated player requests are not implemented yet. Player JavaScript is
parsed for the pinned upstream reverse/swap/splice transforms, without evaluation;
future script changes can require an extraction update. This is not a complete
YoutubeExplode replacement.

## Local use

```toml
[dependencies]
youtube_explode = { path = "../dream-packages/youtube_explode" }
```

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

This prints `Hello & world`. `track.to_srt()` returns SRT text in a `Result`.
Time values are doubles measured in milliseconds. SRT output truncates fractional
milliseconds and uses LF line endings. Time lookup includes both caption endpoints;
when captions overlap, the first source-ordered caption wins. Part lookup preserves
the pinned upstream rule: the first part whose relative offset is at or after the
requested time.

For a track URL already obtained from a player response, create
`ClosedCaptionClient(http)` using a caller-owned `system.net.HttpClient`, then await
`client.get(track_info)`. The adapter sets both `format=3` and `fmt=3`, reads at most
16 MiB, and closes received response bodies on success or failure. A supplied
cancellation token overrides the current structured task's inherited token.
Closing the shared HTTP client cancels pending operations. HTTP 429 returns
`rate_limited`; transport/status failures return `http`, XML failures return
`extraction`, and cancelled work returns `cancelled`.

`ClosedCaptionManifest.from_player_response(response)` extracts available tracks
from a `system.json.JsonValue`. Missing caption metadata produces an empty manifest;
malformed required fields return `extraction`. `get_by_language` accepts a language
code or display name, ignoring case. Empty caption text is skipped while spaces
are preserved. Captions lacking valid t/d timing are skipped.

## Video and stream operations

Import `system.net` and create an `HttpClient`, then construct `VideoClient(http)`,
`StreamClient(http)`, or `ClosedCaptionClient(http)` as needed. These clients share
the supplied client's cookies, connection pools, and cancellation policy. Close
the HTTP client when all operations finish. An optional `origin` constructor
argument selects a fixture or compatible mirror for player/watch requests.

Alternatively, construct `YoutubeClient()` and use its `videos`, `streams`, and
`closed_captions` properties. Its `close()` releases its owned default HTTP client.
`YoutubeClient(Option.Some(http))` shares a supplied client; closing this facade
leaves that client open for its owner.

- `VideoClient.get(id)` returns metadata, including upload date and optional
  duration. `Video.from_player_response` and `Video.from_watch_page` extract metadata
  offline and return categorized failures for missing required fields.
- `StreamClient.get_manifest(id)` returns verified streams. `manifest.filter(kind)`,
  `highest_bitrate`, and `highest_video_quality` select components; empty selections
  return `None`. Offline manifest parsers leave unknown lengths as `None`.
- `StreamClient.get(info)` opens a `MediaStream` implementing `system.io.AsyncReader`.
  Use `read_async`, `seek` with an absolute byte offset, `tell`, and `length`.
  Close the stream explicitly. Seeking beyond EOF is allowed; negative offsets,
  concurrent reads, and reads after closure return I/O errors.
- `StreamClient.copy_to(info, writer, progress)` copies into an `AsyncWriter`,
  retries partial writes, flushes on success, and leaves the destination open.
  `download(info, path, progress)` creates or truncates a file and always closes it.
  Both return the byte count; progress is an optional `fun(double): void` callback
  receiving fractions from zero through one after successful writes.
- `StreamClient.get_hls_url(id)` retrieves the live-video manifest URL.
  `ClosedCaptionClient.get_manifest(id)` retrieves caption-track metadata.

Downloads issue query ranges of at most 9,898,989 bytes unless the URL advertises
`ratebypass=yes`. Read failures retry five times from the next undelivered byte;
persistently truncated bodies return `EEOF` instead of looping indefinitely.
Downloads require a known nonnegative byte length. Failures retain partial output;
cancellation before opening a file leaves existing content untouched. Streaming
read errors use `IoError`, while client methods use `YoutubeError` categories
including `unplayable`, `io`, `http`, `extraction`, and `cancelled`.

## Validation

Run `dreamer test -p youtube_explode_tests` and
`dreamer test -p youtube_explode_tests --release` for native/Node fixture tests.
Run `python scripts/qualify_youtube.py --dream /path/to/dream --dreamer /path/to/dreamer`
from the repository root for the isolated loopback HTTP tests. These tests do not
contact YouTube and do not establish end-to-end parity of the unfinished port.
Add `--release` to exercise optimized native and Node builds of the HTTP tests.

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
