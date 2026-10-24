"""Exercise YouTube video, caption, and stream HTTP contracts against local fixtures."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import tempfile
from threading import Thread
from urllib.parse import parse_qs, urlencode, urlsplit

ROOT = Path(__file__).resolve().parents[1]


class Handler(BaseHTTPRequestHandler):
    requests = []
    profiles = []
    retry_attempts = {}
    range_attempts = {}

    def do_HEAD(self):
        target = urlsplit(self.path)
        Handler.requests.append("HEAD " + target.path)
        self.send_response(404 if target.path == "/gone" else 200)
        self.send_header("Content-Length", "10")
        self.end_headers()

    def stream_player(self, video_id, profile):
        response = self.player(video_id)
        base = f"http://127.0.0.1:{self.server.server_port}"
        if video_id == "tvfallback1" and profile != "TVHTML5_SIMPLY_EMBEDDED_PLAYER":
            response["playabilityStatus"] = {"status": "UNPLAYABLE"}
            return response
        formats = []
        for index, path in enumerate(["/media", "/gone", "/mismatch", "/signed", "/empty"]):
            stream = {"itag": 140 + index, "bitrate": 128000,
                      "mimeType": 'audio/mp4; codecs="mp4a.40.2"'}
            if path == "/signed":
                stream["signatureCipher"] = urlencode({"url": base + path + "?keep=1", "s": "abcdef", "sp": "signature"})
            else:
                stream["url"] = base + path
            if path in {"/mismatch", "/signed", "/empty"}:
                stream["contentLength"] = "0" if path == "/empty" else "10"
            formats.append(stream)
        response["streamingData"] = {"formats": formats, "hlsManifestUrl": base + "/live.m3u8"}
        if video_id == "dashrate123":
            response["streamingData"]["dashManifestUrl"] = base + "/rate"
        return response

    @staticmethod
    def player(video_id):
        return {"playabilityStatus": {"status": "OK"}, "videoDetails": {
            "videoId": video_id, "title": "Fixture video", "author": "Fixture channel",
            "channelId": "UC3xnGqlcL3y-GXz5N3wiTJQ", "lengthSeconds": "12",
            "viewCount": "123", "shortDescription": "Local HTTP fixture"},
            "microformat": {"playerMicroformatRenderer": {"uploadDate": "2026-10-23"}}}

    def log_message(self, *args):
        pass

    def do_GET(self):
        target = urlsplit(self.path)
        Handler.requests.append(target.path)
        body = b""
        status = 200
        if target.path == "/captions":
            if parse_qs(target.query) != {"keep": ["1"], "format": ["3"], "fmt": ["3"], "hl": ["en"]}:
                status = 400
            body = b"<timedtext><body><p t='1000' d='2000'><s>Hello &amp; world</s></p></body></timedtext>"
        elif target.path == "/bad":
            body = b"<broken>"
        elif target.path == "/caption_srt":
            body = "<timedtext><body><p t='1000' d='2000'>Hello Ω --&gt;</p><p t='4000' d='500'>Second</p></body></timedtext>".encode()
        elif target.path == "/rate":
            status = 429
        elif target.path == "/watch":
            query = parse_qs(target.query)
            video_id = query.get("v", [""])[0]
            if query.get("bpctr") != ["9999999999"]:
                status = 400
            if video_id == "abcdefghijk":
                body = b"<html>temporarily broken page</html>"
            elif video_id == "unavailable":
                body = b"<div id=player></div>"
            else:
                html = "<meta property=og:url><meta itemprop=uploadDate content=2026-10-23><div id=player></div>"
                if video_id == "yIVRs6YSbOM":
                    html += "<script>var ytInitialPlayerResponse=" + json.dumps(self.player(video_id)) + ";</script>"
                body = html.encode()
        elif target.path == "/sw.js_data":
            data = [None] * 14
            data[13] = "visitor-fixture"
            body = (")]}'" + json.dumps([[None, None, [[data]]]])).encode()
        elif target.path == "/iframe_api":
            body = b'var src="https://www.youtube.com/s/player/abcd1234/player_ias.vflset/en_US/base.js";'
        elif target.path == "/s/player/abcd1234/player_ias.vflset/en_US/base.js":
            body = b'var H$={sw:function(a,b){var c=a[0];a[0]=a[b%a.length];a[b]=c},sp:function(a,b){a.splice(0,b)},rv:function(a){a.reverse()}};S=function(a){a=a.split("");H$.sw(a,2);H$.rv(a,0);H$.sp(a,1);return a.join("")};signatureTimestamp:12345'
        elif target.path in {"/media", "/mismatch", "/signed"}:
            query = parse_qs(target.query)
            if query.get("range") != ["8-9"]:
                status = 400
            elif target.path == "/mismatch":
                status = 404
            elif target.path == "/signed" and query != {"range": ["8-9"], "keep": ["1"], "signature": ["edabc"], "hl": ["en"]}:
                status = 400
            body = b"89"
        elif target.path in {"/bytes", "/retry", "/truncated", "/large"}:
            value = parse_qs(target.query).get("range", [""])[0]
            start, end = map(int, value.split("-"))
            if target.path == "/large":
                if (start, end) not in {(0, 9898988), (9898990, 9898993)}:
                    raise AssertionError(f"Wrong bounded range: {value}")
                body = b"0123" if start else b""
            else:
                if not 0 <= start <= end < 10:
                    raise AssertionError(f"Wrong stream range: {value}")
                attempts = Handler.retry_attempts.get(target.path, 0)
                Handler.retry_attempts[target.path] = attempts + 1
                key = (target.path, start)
                range_attempt = Handler.range_attempts.get(key, 0)
                Handler.range_attempts[key] = range_attempt + 1
                if target.path == "/truncated":
                    body = b""
                elif target.path == "/retry" and start == 5 and range_attempt % 2 == 0:
                    status = 503
                else:
                    body = b"0123456789"[start:end + 1]
        else:
            status = 404
        self.send_response(status)
        self.send_header("Content-Type", "application/xml; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        Handler.requests.append(urlsplit(self.path).path)
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length))
        client = payload["context"]["client"]
        profile = client["clientName"]
        Handler.profiles.append(profile)
        status = 200
        if client.get("visitorData") != "visitor-fixture":
            status = 400
        if profile == "TVHTML5_SIMPLY_EMBEDDED_PLAYER":
            if payload.get("playbackContext", {}).get("contentPlaybackContext", {}).get("signatureTimestamp") != "12345":
                status = 400
        elif payload.get("contentCheckOk") is not True:
            status = 400
        if payload["videoId"] in {"streamtest1", "tvfallback1", "dashrate123"}:
            response = self.stream_player(payload["videoId"], profile)
        elif profile == "VISIONOS":
            response = self.player(payload["videoId"])
            response["playabilityStatus"] = {"status": "UNPLAYABLE", "reason": "try fallback"}
        elif profile == "ANDROID":
            response = self.player(payload["videoId"])
        else:
            response = {}
            status = 400
        body = json.dumps(response).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dream", required=True)
    parser.add_argument("--dreamer", required=True)
    parser.add_argument("--release", action="store_true")
    args = parser.parse_args()
    dream = str(Path(args.dream).resolve())
    dreamer = str(Path(args.dreamer).resolve())
    os.environ["DREAM_BIN"] = dream
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    work = Path(tempfile.mkdtemp(prefix="dream-youtube-http-"))
    (work / "dream.toml").write_text(
        '[package]\nname = "youtube_http_tests"\nversion = "0.1.0"\ntype = "test"\n'
        '[dependencies]\nyoutube_explode = { path = ' + json.dumps(str(ROOT / "youtube_explode")) + ' }\n'
        '[test]\ntargets = ["native", "node"]\n', encoding="utf-8")
    base = f"http://127.0.0.1:{server.server_port}"
    code = r'''module youtube_http_tests;
import system;
import system.net;
import system.io;
import system.json;
import system.collections;
import system.testing;
import youtube_explode;

@test
@timeout(15000)
async fun caption_http_contract(): void {
    let http = HttpClient();
    let youtube = YoutubeClient(Option.Some(http), BASE);
    youtube.close().unwrap();
    let client = youtube.closed_captions;
    let language = Language("en", "English");
    let track = client.get(ClosedCaptionTrackInfo(BASE + "/captions?keep=1&format=old&fmt=old&fmt=duplicate", language, false)).await.unwrap();
    Assert.eq(track.captions[0].text, "Hello & world");
    Assert.eq(track.to_srt().unwrap(), "1\n00:00:01,000 --> 00:00:03,000\nHello & world\n\n");
    let malformed = client.get(ClosedCaptionTrackInfo(BASE + "/bad", language, false)).await;
    Assert.eq(malformed.unwrap_err().code(), "extraction");
    let limited = client.get(ClosedCaptionTrackInfo(BASE + "/rate", language, false)).await;
    Assert.eq(limited.unwrap_err().code(), "rate_limited");
    let source = CancellationSource();
    source.cancel();
    let cancelled = client.get(ClosedCaptionTrackInfo(BASE + "/cancelled", language, false), Option.Some(source.token)).await;
    Assert.eq(cancelled.unwrap_err().code(), "cancelled");
    http.close().unwrap();
    let owned = YoutubeClient(Option.None, BASE);
    owned.close().unwrap();
    Assert.eq(owned.videos.get(VideoId.parse("yIVRs6YSbOM").unwrap()).await.unwrap_err().code(), "http");
}

@test
@timeout(15000)
async fun video_http_and_player_fallback(): void {
    let http = HttpClient();
    let client = VideoClient(http, BASE);
    let inline = client.get(VideoId.parse("yIVRs6YSbOM").unwrap()).await.unwrap();
    Assert.eq(inline.title, "Fixture video");
    Assert.eq(inline.description, "Local HTTP fixture");
    let fallback_id = VideoId.parse("Fcds0_MrgNU").unwrap();
    let fallback = client.get(fallback_id).await.unwrap();
    Assert.eq(fallback.id, fallback_id);
    Assert.eq(fallback.engagement.view_count, 123L);
    Assert.eq(client.get(fallback_id).await.unwrap().duration_ms.unwrap(), 12000.0d);
    Assert.eq(client.get(VideoId.parse("unavailable").unwrap()).await.unwrap_err().code(), "unavailable");
    Assert.eq(client.get(VideoId.parse("abcdefghijk").unwrap()).await.unwrap_err().code(), "extraction");
    let source = CancellationSource();
    source.cancel();
    Assert.eq(client.get(fallback_id, Option.Some(source.token)).await.unwrap_err().code(), "cancelled");
    Assert.eq(VideoClient(http, "invalid origin").get(fallback_id).await.unwrap_err().code(), "invalid_input");
    http.close().unwrap();
}

@test
@timeout(15000)
async fun streams_http_sizes_cipher_cache_and_tv_fallback(): void {
    let http = HttpClient();
    let client = StreamClient(http, BASE);
    let id = VideoId.parse("streamtest1").unwrap();
    let manifest = client.get_manifest(id).await.unwrap();
    Assert.eq(manifest.streams.length, 3);
    Assert.eq(manifest.streams[0].size.unwrap().bytes, 10L);
    Assert.eq(manifest.streams[1].size.unwrap().bytes, 10L);
    Assert.eq(manifest.streams[2].size.unwrap().bytes, 0L);
    Assert.eq(Url.parse(manifest.streams[1].url).unwrap().query.get("signature").unwrap(), "edabc");
    Assert.eq(client.get_manifest(VideoId.parse("tvfallback1").unwrap()).await.unwrap().streams.length, 3);
    Assert.eq(client.get_hls_url(id).await.unwrap(), BASE + "/live.m3u8");
    Assert.eq(client.get_manifest(VideoId.parse("dashrate123").unwrap()).await.unwrap_err().code(), "rate_limited");
    let source = CancellationSource();
    source.cancel();
    Assert.eq(client.get_manifest(id, Option.Some(source.token)).await.unwrap_err().code(), "cancelled");
    http.close().unwrap();
}

fun download_info(path: string, size: long = 10L): StreamInfo {
    let response = Json.deserialize<JsonValue>("{\"streamingData\":{\"formats\":[{\"itag\":140,\"bitrate\":128000,\"mimeType\":\"audio/mp4; codecs=\\\"mp4a.40.2\\\"\",\"url\":\"" + BASE + path + "\",\"contentLength\":\"" + size.to_string() + "\"}]}}").unwrap();
    return StreamManifest.from_player_response(response).unwrap().streams[0];
}

class ShortWriter: AsyncWriter {
    target: MemoryStream;

    public constructor(target: MemoryStream) {
        this.target = target;
    }

    public async unique fun write_async(data: byte[], token: Option<CancellationToken> = Option.None): Result<int, IoError> {
        let count = data.length > 2 ? 2 : data.length;
        return this.target.write(data.slice(0, count));
    }

    public async unique fun flush_async(token: Option<CancellationToken> = Option.None): Result<Unit, IoError> {
        return this.target.flush();
    }
}

@test
@timeout(15000)
async fun seekable_downloads_retries_and_progress(): void {
    let http = HttpClient();
    let client = StreamClient(http, BASE);
    let info = download_info("/bytes");
    Assert.eq(client.get(download_info("/rate")).await.unwrap_err().code(), "rate_limited");
    let input = client.get(info).await.unwrap();
    Assert.eq(input.length, 10L);
    Assert.eq(Encoding.utf8_decode(input.read_async(3).await.unwrap()), "012");
    Assert.eq(input.read_async(0).await.unwrap().length, 0);
    Assert.eq(input.tell().unwrap(), 3L);
    Assert.is_true(input.seek(-1L).is_err());
    Assert.eq(input.tell().unwrap(), 3L);
    input.seek(7L).unwrap();
    Assert.eq(Encoding.utf8_decode(input.read_async(10).await.unwrap()), "789");
    Assert.eq(input.read_async(1).await.unwrap().length, 0);
    input.seek(12L).unwrap();
    Assert.eq(input.read_async(1).await.unwrap().length, 0);
    let cancelled = CancellationSource();
    cancelled.cancel();
    Assert.eq(input.read_async(1, Option.Some(cancelled.token)).await.unwrap_err().code(), "ECANCELLED");
    input.close();
    input.close();
    Assert.eq(input.read_async(1).await.unwrap_err().code(), "ECLOSED");
    let output = MemoryStream();
    let progress = List<double>();
    let report: fun(double): void = (value: double) => { progress.push(value); };
    Assert.eq(client.copy_to(info, ShortWriter(output), Option.Some(report)).await.unwrap(), 10L);
    Assert.eq(Encoding.utf8_decode(output.to_bytes().unwrap()), "0123456789");
    Assert.eq(progress.length, 5);
    Assert.eq(progress[0], 0.2d);
    Assert.eq(progress[4], 1.0d);
    Assert.eq(client.copy_to(download_info("/empty", 0L), output, Option.Some(report)).await.unwrap(), 0L);
    Assert.eq(progress[5], 1.0d);
    let retry = client.get(download_info("/retry")).await.unwrap();
    Assert.eq(retry.read_async(4).await.unwrap().length, 4);
    retry.seek(5L).unwrap();
    Assert.eq(Encoding.utf8_decode(retry.read_async(8).await.unwrap()), "56789");
    retry.close();
    let truncated = client.get(download_info("/truncated")).await.unwrap();
    Assert.eq(truncated.read_async(4).await.unwrap_err().code(), "EEOF");
    truncated.close();
    let large = client.get(download_info("/large", 9898994L)).await.unwrap();
    large.seek(9898990L).unwrap();
    Assert.eq(Encoding.utf8_decode(large.read_async(4).await.unwrap()), "0123");
    large.close();
    let directory = TempDirectory.create().unwrap();
    let path = directory.path + "/download";
    Assert.eq(client.download(info, path).await.unwrap(), 10L);
    Assert.eq(File.read(path).await.unwrap(), "0123456789");
    Assert.eq(client.download(info, path, Option.None, Option.Some(cancelled.token)).await.unwrap_err().code(), "cancelled");
    Assert.eq(File.read(path).await.unwrap(), "0123456789");
    directory.close().unwrap();
    http.close().unwrap();
}

@test
@timeout(15000)
async fun caption_srt_writers_progress_and_files(): void {
    let http = HttpClient();
    let client = ClosedCaptionClient(http);
    let info = ClosedCaptionTrackInfo(BASE + "/caption_srt", Language("en", "English"), false);
    let expected = "1\n00:00:01,000 --> 00:00:03,000\nHello Ω ––>\n\n2\n00:00:04,000 --> 00:00:04,500\nSecond\n\n";
    let output = MemoryStream();
    let progress = List<double>();
    let report: fun(double): void = (value: double) => { progress.push(value); };
    Assert.eq(client.write_to(info, ShortWriter(output), Option.Some(report)).await.unwrap(), (long)Encoding.utf8_encode(expected).length);
    Assert.eq(Encoding.utf8_decode(output.to_bytes().unwrap()), expected);
    Assert.eq(progress.length, 2);
    Assert.eq(progress[0], 0.5d);
    Assert.eq(progress[1], 1.0d);
    let directory = TempDirectory.create().unwrap();
    let path = directory.path + "/captions.srt";
    client.download(info, path).await.unwrap();
    Assert.eq(File.read(path).await.unwrap(), expected);
    let cancelled = CancellationSource();
    let stop: fun(double): void = (value: double) => { cancelled.cancel(); };
    let partial = MemoryStream();
    Assert.eq(client.write_to(info, partial, Option.Some(stop), Option.Some(cancelled.token)).await.unwrap_err().code(), "cancelled");
    Assert.eq(Encoding.utf8_decode(partial.to_bytes().unwrap()), "1\n00:00:01,000 --> 00:00:03,000\nHello Ω ––>\n\n");
    Assert.eq(client.download(info, path, Option.None, Option.Some(cancelled.token)).await.unwrap_err().code(), "cancelled");
    Assert.eq(File.read(path).await.unwrap(), expected);
    output.close().unwrap();
    Assert.eq(client.write_to(info, output).await.unwrap_err().code(), "io");
    directory.close().unwrap();
    http.close().unwrap();
}
'''.replace("BASE", json.dumps(base))
    (work / "http.dream").write_text(code, encoding="utf-8")
    try:
        subprocess.run([dreamer, "test"] + (["--release"] if args.release else []), cwd=work, check=True)
        video_requests = ["/watch", "/watch", "/sw.js_data", "/youtubei/v1/player", "/youtubei/v1/player",
                          "/watch", "/youtubei/v1/player", "/youtubei/v1/player", "/watch"] + ["/watch"] * 6
        probes = ["HEAD /media", "/media", "HEAD /gone", "/mismatch", "/signed"]
        stream_requests = ["/sw.js_data", "/youtubei/v1/player", "/iframe_api",
                           "/s/player/abcd1234/player_ias.vflset/en_US/base.js"] + probes + [
                           "/youtubei/v1/player", "/youtubei/v1/player", "/youtubei/v1/player"] + probes + ["/youtubei/v1/player", "/youtubei/v1/player", "/rate"]
        download_requests = ["/rate"] + ["/bytes"] * 3 + ["/retry"] * 3 + ["/truncated"] * 6 + ["/large"] * 2 + ["/bytes"] + ["/caption_srt"] * 4
        if Handler.requests != (["/captions", "/bad", "/rate"] + video_requests + stream_requests + download_requests) * 2:
            raise SystemExit(f"Unexpected requests (including cancelled work): {Handler.requests}")
        if Handler.profiles != (["VISIONOS", "ANDROID", "VISIONOS", "ANDROID"] +
                                ["VISIONOS", "VISIONOS", "ANDROID", "TVHTML5_SIMPLY_EMBEDDED_PLAYER", "VISIONOS", "VISIONOS"]) * 2:
            raise SystemExit(f"Wrong player fallback order: {Handler.profiles}")
    except Exception:
        print(f"Requests at failure: {Handler.requests}; range attempts: {Handler.range_attempts}", flush=True)
        raise
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    print(f"PASS: video/player fallback, visitor/cipher caches, stream probes, TV fallback, captions, cancellation, and cleanup on native/Node. Evidence: {work}")


if __name__ == "__main__":
    main()
