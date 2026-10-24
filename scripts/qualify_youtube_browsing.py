"""Qualify YouTube paging, channel resolution, request policy, and native authentication."""
import argparse
from collections import Counter
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import tempfile
from threading import Thread
import time
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
CHANNEL = "UC3xnGqlcL3y-GXz5N3wiTJQ"
VIDEOS = ["yIVRs6YSbOM", "Fcds0_MrgNU", "abcdefghijk"]
KEY = "AIzaSyA8eiZmM1FaDVjRy-df2KTyQ_vz_yYM39w"


def nested(path, value):
    for key in reversed(path.split("/")):
        value = {key: value}
    return value


def video(index):
    owner = {"text": "Creator Ω", **nested("navigationEndpoint/browseEndpoint/browseId", CHANNEL)}
    result = {"videoId": VIDEOS[index], "title": {"simpleText": "Video " + str(index)},
              "shortBylineText": {"runs": [owner]}, "lengthText": {"simpleText": "1:02"},
              **nested("navigationEndpoint/watchEndpoint/index", index)}
    if index == 2:
        result["lengthSeconds"] = "1.5"
        result["shortBylineText"]["runs"][0]["navigationEndpoint"] = nested(
            "showDialogCommand/panelLoadingStrategy/inlineContent/dialogViewModel/customContent/listViewModel/listItems",
            [nested("listItemViewModel/rendererContext/commandContext/onTap/innertubeCommand/browseEndpoint/browseId", CHANNEL)])
    return result


def playlist_page(indices):
    return {**nested("contents/twoColumnWatchNextResults/playlist/playlist", {
        "title": "System mix", "totalVideosText": {"runs": [{"text": "3"}]},
        "contents": [{"playlistPanelVideoRenderer": video(i)} for i in indices]}),
        "responseContext": {"visitorData": "playlist-visitor"}}


def search_page(indices, continuation=None, mixed=False):
    contents = [{"videoRenderer": video(i)} for i in indices]
    if mixed:
        contents = [
            {"channelRenderer": {"channelId": CHANNEL, "title": {"simpleText": "Channel"}}},
            {"playlistRenderer": {"playlistId": "PLbrowse", "title": {"simpleText": "Playlist"}}},
        ] + contents
    if continuation is not None:
        contents.append(nested("continuationItemRenderer/continuationEndpoint/continuationCommand/token", continuation))
    return {"contents": contents}


class Handler(BaseHTTPRequestHandler):
    counts = Counter()
    issues = []

    def log_message(self, *args):
        pass

    def check(self, condition, message):
        if not condition:
            Handler.issues.append(message)

    def policy(self):
        target = urlsplit(self.path)
        query = parse_qs(target.query)
        self.check(query.get("hl") == ["en"], "missing localization: " + self.path)
        self.check(self.headers.get("Origin") == self.origin, "wrong Origin")
        self.check(bool(self.headers.get("User-Agent")), "missing User-Agent")
        if target.path.startswith("/youtubei/"):
            self.check(query.get("key") == [KEY], "missing API key")
        auth = self.headers.get("Authorization")
        if auth:
            header = self.headers.get("Cookie", "")
            cookies = dict(pair.strip().split("=", 1) for pair in header.split(";") if "=" in pair)
            self.check("SOCS" not in cookies, "cookie domain leak")
            timestamp, digest = auth.removeprefix("SAPISIDHASH ").split("_", 1)
            session = cookies.get("__Secure-3PAPISID", cookies.get("SAPISID"))
            expected = hashlib.sha1(f"{timestamp} {session} {self.origin}".encode()).hexdigest().upper()
            self.check(digest == expected and abs(int(timestamp) - time.time()) < 60, "invalid SAPISID auth")
        return target

    @property
    def base(self):
        return f"http://127.0.0.1:{self.server.server_port}"

    @property
    def origin(self):
        return "http://127.0.0.1"

    def reply(self, data, status=200, cookies=()):
        body = data if isinstance(data, bytes) else json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        for value in cookies:
            self.send_header("Set-Cookie", value)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        target = self.policy()
        Handler.counts["GET " + target.path] += 1
        if target.path == "/playlist":
            playlist = parse_qs(target.query).get("list", [""])[0]
            self.check(playlist in {"RDsystem", "RDlimited"}, "wrong playlist warm-up")
            return self.reply(b"ignored", 429 if playlist == "RDlimited" else 500)
        if target.path == "/sw.js_data":
            data = [None] * 14
            data[13] = "visitor-fixture"
            return self.reply((")]}'" + json.dumps([[None, None, [[data]]]])).encode())
        if target.path == "/@broken":
            return self.reply(b"<html>no channel metadata</html>")
        if target.path == "/@auth":
            self.check("SAPISID=rotated" in self.headers.get("Cookie", ""), "cookies not shared across services")
        html = f"<meta property=og:url content=https://www.youtube.com/channel/{CHANNEL}><meta property=og:title content='Channel Ω'><meta property=og:image content=https://example.test/s144>"
        return self.reply(html.encode())

    def do_POST(self):
        target = self.policy()
        payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
        client = payload.get("context", {}).get("client", {})
        if target.path == "/youtubei/v1/player":
            Handler.counts["purchase"] += 1
            self.check(client.get("clientName") == "VISIONOS", "purchase should stop client fallbacks")
            return self.reply({"playabilityStatus": {"status": "UNPLAYABLE", "errorScreen": {
                "playerLegacyDesktopYpcTrailerRenderer": {"trailerVideoId": VIDEOS[0]}}}})
        self.check(client.get("clientName") == "WEB" and client.get("clientVersion") == "2.20210408.08.00", "wrong WEB profile")
        self.check(client.get("hl") == "en" and client.get("gl") == "US" and client.get("utcOffsetMinutes") == 0, "wrong client locale")
        if target.path == "/youtubei/v1/browse":
            key = payload["browseId"]
            Handler.counts["browse " + key] += 1
            if key in {"VLRDsystem", "VLRDlimited"}:
                return self.reply({})
            self.check(key == "VLPLbrowse", "wrong browse ID")
            return self.reply(nested("sidebar/playlistSidebarRenderer/items", [{
                "playlistSidebarPrimaryInfoRenderer": {"title": {"simpleText": "Browse title"}, "stats": [{"simpleText": "2 videos"}]}
            }]))
        if target.path == "/youtubei/v1/next":
            key = payload["playlistId"]
            index = payload["playlistIndex"]
            Handler.counts["next " + key] += 1
            if key == "RDlimited":
                return self.reply({})
            if key == "RDsystem":
                return self.reply({} if Handler.counts["next RDsystem"] % 2 else playlist_page([0]))
            if client.get("visitorData") is None:
                self.check(payload.get("videoId") is None and index == 0, "wrong first playlist cursor")
                page = playlist_page([0, 1] if key not in {"PLbad", "UU" + CHANNEL[2:]} else [0])
                if key == "PLbad":
                    page["contents"]["twoColumnWatchNextResults"]["playlist"]["playlist"]["contents"][0]["playlistPanelVideoRenderer"]["navigationEndpoint"]["watchEndpoint"].pop("index")
                return self.reply(page)
            self.check(client["visitorData"] == "playlist-visitor" and payload["videoId"] == VIDEOS[index], "playlist cursor or visitor was lost")
            if key == "PLunavailable":
                return self.reply({})
            return self.reply(playlist_page([1, 2] if index == 1 else [index]))
        if target.path != "/youtubei/v1/search":
            return self.reply({}, 404)
        query = payload["query"]
        token = payload.get("continuation")
        Handler.counts["search " + query] += 1
        if query == "expired":
            self.check(not self.headers.get("Authorization") and not self.headers.get("Cookie"), "expired credentials were sent")
            return self.reply({})
        if query == "detached":
            return self.reply({})
        if query == "auth":
            expected = "seed" if Handler.counts["search auth"] == 1 else "rotated"
            self.check("SAPISID=" + expected in self.headers.get("Cookie", ""), "wrong auth cookie")
            self.check(bool(self.headers.get("Authorization")), "missing auth header")
            return self.reply({}, cookies=["SAPISID=rotated; Path=/", "ignored=secret; Domain=evil.test"])
        if query == "retry":
            return self.reply({}, 503 if Handler.counts["search retry"] % 3 else 200)
        if query == "rate":
            return self.reply({}, 429)
        if query == "http_error":
            return self.reply({}, 503)
        if query == "page_error" and token is not None:
            return self.reply(b"not JSON")
        if query.startswith("filter_"):
            expected = {"filter_video": "EgIQAQ%3D%3D", "filter_playlist": "EgIQAw%3D%3D", "filter_channel": "EgIQAg%3D%3D"}[query]
            self.check(payload.get("params") == expected, "wrong search filter")
            return self.reply(search_page([0], mixed=True))
        self.check(payload.get("params") is None, "unexpected search filter")
        Handler.counts["continuation " + str(token)] += 1
        if token is None:
            return self.reply(search_page([0], "A", mixed=query != "page_error"))
        if token == "A":
            return self.reply(search_page([0, 1], "B"))
        self.check(token == "B", "unknown continuation")
        return self.reply(search_page([], "B", mixed=True))


SOURCE = r'''module youtube_browsing_http;
import system;
import system.net;
import system.collections;
import system.testing;
import youtube_explode;

@test
@timeout(15000)
async fun channels_routes_retries_uploads_and_cancellation(): void {
    let client = YoutubeClient(Option.None, BASE);
    let id = ChannelId.parse("UC3xnGqlcL3y-GXz5N3wiTJQ").unwrap();
    Assert.eq(client.channels.get(id).await.unwrap().title, "Channel Ω");
    Assert.eq(client.channels.get_by_handle(ChannelHandle.parse("fixture").unwrap()).await.unwrap().id, id);
    Assert.eq(client.channels.get_by_user(UserName.parse("fixture").unwrap()).await.unwrap().id, id);
    Assert.eq(client.channels.get_by_slug(ChannelSlug.parse("fixture").unwrap()).await.unwrap().id, id);
    Assert.eq(client.channels.get_by_handle(ChannelHandle.parse("broken").unwrap()).await.unwrap_err().code(), "extraction");
    Assert.eq(client.channels.get(ChannelId.parse("UCuVPpxrm2VAgpH3Ktln4HXg").unwrap()).await.unwrap().title, "Movies & TV");
    let count = 0;
    await for (let value in client.channels.uploads(id)) {
        let video = value.unwrap();
        Assert.eq(video.playlist_id.value, "UU3xnGqlcL3y-GXz5N3wiTJQ");
        count++;
    }
    Assert.eq(count, 1);
    let cancelled = CancellationSource();
    cancelled.cancel();
    Assert.eq(client.channels.get(id, Option.Some(cancelled.token)).await.unwrap_err().code(), "cancelled");
    client.close().unwrap();
}

@test
@timeout(15000)
async fun playlist_paging_system_fallback_and_early_close(): void {
    let client = YoutubeClient(Option.None, BASE);
    Assert.eq(client.playlists.get(PlaylistId.parse("PLbrowse").unwrap()).await.unwrap().title, "Browse title");
    Assert.eq(client.playlists.get(PlaylistId.parse("RDsystem").unwrap()).await.unwrap().title, "System mix");
    Assert.eq(client.playlists.get(PlaylistId.parse("RDlimited").unwrap()).await.unwrap_err().code(), "rate_limited");
    let titles = List<string>();
    await for (let value in client.playlists.videos(PlaylistId.parse("PLfixture").unwrap())) {
        let video = value.unwrap();
        titles.push(video.title);
        if video.id.value == "abcdefghijk" {
            Assert.eq(video.duration_ms.unwrap(), 1500.0d);
            Assert.eq(video.author.channel_id.value, "UC3xnGqlcL3y-GXz5N3wiTJQ");
        }
    }
    Assert.eq(titles.length, 3);
    Assert.eq(titles[0], "Video 0");
    Assert.eq(titles[2], "Video 2");
    let count = 0;
    await for (let batch in client.playlists.video_batches(PlaylistId.parse("PLunavailable").unwrap())) {
        count = count + batch.unwrap().count;
    }
    Assert.eq(count, 2);
    let bad = client.playlists.videos(PlaylistId.parse("PLbad").unwrap()).iterator();
    Assert.eq(bad.next().await.unwrap().unwrap_err().code(), "extraction");
    Assert.is_true(bad.next().await.is_none());
    bad.close();
    await for (let value in client.playlists.videos(PlaylistId.parse("PLfixture").unwrap())) {
        Assert.eq(value.unwrap().title, "Video 0");
        break;
    }
    client.close().unwrap();
}

@test
@timeout(15000)
async fun search_continuations_filters_retries_and_errors(): void {
    let client = YoutubeClient(Option.None, BASE);
    let titles = List<string>();
    await for (let value in client.search.results("pages")) {
        titles.push(value.unwrap().title);
    }
    Assert.eq(titles.length, 4);
    Assert.eq(titles[0], "Video 0");
    Assert.eq(titles[1], "Playlist");
    Assert.eq(titles[2], "Channel");
    Assert.eq(titles[3], "Video 1");
    Assert.eq(client.search.get_page("filter_video", SearchFilter.Video).await.unwrap().results.length, 1);
    Assert.eq(client.search.get_page("filter_playlist", SearchFilter.Playlist).await.unwrap().results.length, 1);
    Assert.eq(client.search.get_page("filter_channel", SearchFilter.Channel).await.unwrap().results.length, 1);
    await for (let value in client.search.results("pages")) {
        Assert.eq(value.unwrap().title, "Video 0");
        break;
    }
    let errors = client.search.results("page_error").iterator();
    Assert.eq(errors.next().await.unwrap().unwrap().title, "Video 0");
    Assert.eq(errors.next().await.unwrap().unwrap_err().code(), "extraction");
    Assert.is_true(errors.next().await.is_none());
    errors.close();
    Assert.eq(client.search.get_page("retry").await.unwrap().results.length, 0);
    Assert.eq(client.search.get_page("rate").await.unwrap_err().code(), "rate_limited");
    Assert.eq(client.search.get_page("http_error").await.unwrap_err().code(), "http");
    let cancelled = CancellationSource();
    cancelled.cancel();
    let cursor = client.search.results("cancelled", SearchFilter.All, Option.Some(cancelled.token)).iterator();
    Assert.eq(cursor.next().await.unwrap().unwrap_err().code(), "cancelled");
    Assert.is_true(cursor.next().await.is_none());
    cursor.close();
    let purchase = client.streams.get_manifest(VideoId.parse("purchase123").unwrap()).await.unwrap_err();
    Assert.eq(purchase.code(), "purchase_required");
    Assert.eq(purchase.preview_video_id.unwrap().value, "yIVRs6YSbOM");
    let detached = YoutubeClient(Option.None, BASE).search;
    Assert.eq(detached.get_page("detached").await.unwrap().results.length, 0);
    client.close().unwrap();
}

@test
@timeout(15000)
async fun native_cookie_auth_rotation_scope_and_service_sharing(): void {
    if HttpCapabilities.cookie_jars {
        let jar = CookieJar();
        let target = Url.parse(BASE).unwrap();
        jar.store(target, "SAPISID=seed; Path=/").unwrap();
        let youtube = Url.parse("https://www.youtube.com").unwrap();
        jar.store(youtube, "SOCS=custom; Domain=youtube.com; Path=/").unwrap();
        let http = HttpClient(false);
        let client = YoutubeClient(Option.Some(http), BASE, Option.Some(jar));
        Assert.eq(client.search.get_page("auth").await.unwrap().results.length, 0);
        Assert.eq(client.search.get_page("auth").await.unwrap().results.length, 0);
        jar.store(Url.parse("https://127.0.0.1").unwrap(), "__Secure-3PAPISID=secure; Secure; Path=/").unwrap();
        Assert.eq(client.channels.get_by_handle(ChannelHandle.parse("auth").unwrap()).await.unwrap().title, "Channel Ω");
        Assert.eq(jar.header(youtube).unwrap(), "SOCS=custom");
        Assert.eq(jar.header(target).unwrap(), "SAPISID=rotated; __Secure-3PAPISID=secure");
        jar.store(Url.parse("https://secure.example.test").unwrap(), "__Secure-3PAPISID=scoped; Secure; Path=/").unwrap();
        Assert.eq(jar.header(Url.parse("http://secure.example.test").unwrap()).unwrap(), "");
        jar.store(target, "SAPISID=expired; Max-Age=0; Path=/").unwrap();
        jar.store(Url.parse("https://127.0.0.1").unwrap(), "__Secure-3PAPISID=expired; Max-Age=0; Secure; Path=/").unwrap();
        Assert.eq(client.search.get_page("expired").await.unwrap().results.length, 0);
        client.close().unwrap();
        http.close().unwrap();
    }
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dream", required=True)
    parser.add_argument("--dreamer", required=True)
    parser.add_argument("--release", action="store_true")
    args = parser.parse_args()
    os.environ["DREAM_BIN"] = str(Path(args.dream).resolve())
    dreamer = str(Path(args.dreamer).resolve())
    work = Path(tempfile.mkdtemp(prefix="dream-youtube-browsing-"))
    (work / "dream.toml").write_text(
        '[package]\nname="youtube_browsing_http"\nversion="0.1.0"\ntype="test"\n'
        '[dependencies]\nyoutube_explode={path=' + json.dumps(str(ROOT / "youtube_explode")) + '}\n'
        '[test]\ntargets=["native","node"]\n', encoding="utf-8")
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    (work / "browsing.dream").write_text(SOURCE.replace("BASE", json.dumps(base)), encoding="utf-8")
    try:
        subprocess.run([dreamer, "test"] + (["--release"] if args.release else []), cwd=work, check=True)
        expected = {
            "GET /channel/" + CHANNEL: 2, "GET /@fixture": 2, "GET /user/fixture": 2, "GET /c/fixture": 2,
            "GET /@broken": 12, "GET /playlist": 14, "GET /sw.js_data": 2,
            "GET /@auth": 1, "browse VLPLbrowse": 2, "browse VLRDsystem": 2,
            "browse VLRDlimited": 2, "next RDlimited": 2,
            "next RDsystem": 4, "next PLfixture": 8, "next PLunavailable": 14, "next PLbad": 2,
            "next UU" + CHANNEL[2:]: 4, "search pages": 8, "search page_error": 4,
            "search filter_video": 2, "search filter_playlist": 2, "search filter_channel": 2,
            "search detached": 2, "search expired": 1, "search retry": 6, "search rate": 2, "search http_error": 12, "search auth": 2,
            "continuation None": 6, "continuation A": 2, "continuation B": 2, "purchase": 2,
        }
        if Handler.issues or Handler.counts != expected:
            raise AssertionError(f"Policy violations: {Handler.issues}; requests: {dict(Handler.counts)}; expected: {expected}")
    finally:
        (work / "requests.json").write_text(json.dumps({"counts": dict(Handler.counts), "issues": Handler.issues}, indent=2), encoding="utf-8")
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    print(f"PASS: native/Node channels, uploads, playlist/search paging, retries, errors, cancellation, and native SAPISID auth. Evidence: {work}")


if __name__ == "__main__":
    main()
