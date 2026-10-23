# sha1

SHA-1 hashing implemented entirely in Dream, for existing protocol interoperability.
No native libraries or external process/runtime helpers are required. SHA-1 is unsuitable
for new collision-resistant security designs; use a modern digest for new protocols.

## Use in a local project

```toml
[dependencies]
sha1 = { path = "../dream-packages/sha1" }
```

```dream
import system;
import sha1;

fun main(): void {
    let digest = Sha1.hash(Encoding.utf8_encode("abc"));
    System.println(Encoding.hex_encode(digest));
}
```

Output: `a9993e364706816aba3e25717850c26c9cd0d89d`.

`Sha1.hash(data)` borrows bytes without changing them and returns a new 20-byte
big-endian digest. The implementation uses bounded working memory rather than copying
and padding the full message. There is no implicit text encoding: encode text explicitly.

## Validation

Run `dreamer test -p sha1_tests` and `dreamer test -p sha1_tests --release` from
the repository root. Tests run on native and Node, including empty/abc/million-a
vectors and binary inputs around SHA-1 padding boundaries, checked against Python hashlib.

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
