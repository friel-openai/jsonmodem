# jsonmodem
*Incremental, event‑driven **streaming JSON** parser for Rust* 🚀


Parse → filter → act **while the bytes are still in flight**.

[![Crates.io](https://img.shields.io/crates/v/jsonmodem)](https://crates.io/crates/jsonmodem)
[![Docs.rs](https://img.shields.io/docsrs/jsonmodem)](https://docs.rs/jsonmodem)
![Tests](https://github.com/aaronfriel/jsonmodem/actions/workflows/test.yml/badge.svg?branch=main)
![Fuzzing](https://github.com/aaronfriel/jsonmodem/actions/workflows/fuzz.yml/badge.svg?branch=main)
![Miri](https://github.com/aaronfriel/jsonmodem/actions/workflows/miri.yml/badge.svg?branch=main) [![MSRV
1.85](https://img.shields.io/badge/MSRV-1.85-blue)](#msrv)

---

## ✨ Why jsonmodem?

* **Linear performance, bounded memory** – work grows with bytes received; peak usage is limited to
  the largest in‑flight fragment when default options are used.
* **LLM‑ready** – handles multi‑kilobyte tool calls without the quadratic “buffer, patch, re‑parse”
  dance.
* **First‑class moderation hooks** – inspect or cancel as soon as a sentinel field appears.
* **Hardened core** – QuickCheck property tests, `cargo‑fuzz` (via `libafl_libfuzzer`), and Miri
  runs to verify safety.

---

## 📦 Installation

```bash
cargo add jsonmodem
````

*(Python, Node‑API, and WASM bindings are on the roadmap.)*

### Rust features

`cached-zipper` is enabled by default. It lets value-building adapters cache
pointers along the current branch instead of walking from the root for each
access. Its unsafe implementation has safe interfaces tied to the tree's owner;
enabling it does not permit unchecked JSON or overlapping mutable references.

To use safe tree traversal in this unreleased implementation, pin its Git
revision and disable default features:

```toml
[dependencies]
jsonmodem = { git = "https://github.com/friel-openai/jsonmodem", rev = "7b7e21c3bd49d22c0964c4a30be16b5367160caf", default-features = false }
```

Without `cached-zipper`, the core crate uses `forbid(unsafe_code)`. The public
parsing and value APIs stay the same, but value building can be slower,
especially for deeply nested documents. This guarantee covers the core crate's
source, not its dependencies or the Python extension.

Cargo combines dependency features. If any other dependency enables
`cached-zipper`, including through jsonmodem's defaults, your application also
uses the cache. `default-features = false` is not a veto. Check the resolved
features with `cargo tree -e features -i jsonmodem` in your application.

The independent `serde` feature can be enabled with or without `cached-zipper`.

### Events without paths

Use `JsonModem<EventBackend>` when you need events but not their locations.
`EventBackend` keeps the parent container kinds needed to validate JSON, but
does not store event paths. Choose `LexemeBackend` when paths are needed.
The shared lexer can still buffer property-name text, especially across feeds.
This choice belongs to each parser, not to Cargo features; another dependency
cannot turn path tracking on for that parser. The Python equivalent is
[`JsonModemEvents`](crates/jsonmodem-py/README.md#streaming-usage).

---

## 🧪 Quick start – reacting to moderation while streaming code


The full runnable program lives at
[`examples/llm_tool_call.rs`](crates/jsonmodem/examples/llm_tool_call.rs).

```rust
use jsonmodem::{JsonModemBuffers, ParserOptions, BufferOptions, BufferedEvent, path};

let mut parser = JsonModemBuffers::new(
    ParserOptions::default(),
    BufferOptions::default()
);

for chunk in llm_stream() {           // ← bytes from the model
    let mut it = parser.feed(&chunk); // lending iterator over buffered events
    while let Some(ev) = it.next() {
        match ev.unwrap() {
            // 1️⃣ Abort early if the model flags a policy violation
            BufferedEvent::String { path, value: Some(prefix), .. }
                if path == path!["moderation", "decision"]
                   && prefix.starts_with("block") =>
            {
                return Err("content blocked".into());
            }

            // 2️⃣ Forward code fragments to the UI immediately
            BufferedEvent::String { path, fragment, .. }
                if path == path!["code"] =>
            {
                ui_write(fragment);   // render incrementally
            }

            _ => {}
        }
    }
}
```

*Result*: harmful output is rejected **before** the document finishes, while valid code streams to
the user with minimal latency.

---

## 📊 Performance

**Streaming‑JSON benchmark**

* 16 KiB JSON streamed in 100 / 1 000 / 5 000 pieces (the `response_large.json` file).
* Measured as time total time to parse all chunks, medians.

**Implementations**:

  * `jsonmodem::JsonModem` (events) — emits low‑overhead parse events.
  * `jsonmodem::JsonModemValues` (values) — yields partial/complete values per chunk.
  * `parse_partial_json` – Rust port of [vercel/ai](https://github.com/vercel/ai)'s JSON fixing with `serde_json`.
  * `fix_json_parse` – helper from Vercel AI's library.
  * `jiter` – the parser used in Pydantic 2.0.


| chunks | `JsonModem` | `JsonModemValues`  | `parse_partial_json`  | `fix_json_parse`  | `jiter`   |
| -----: | ----------: | -----------------: | --------------------: | ----------------: | --------: |
|    100 |      163 μs |             175 μs |              3,969 μs |          2,957 μs |  1,239 μs |
|  1 000 |      184 μs |             202 μs |             38,320 μs |         27,637 μs | 11,493 μs |
|  5 000 |      245 μs |             274 μs |            163,510 μs |        119,810 μs | 48,477 μs |

_Benchmarks recorded on an AMD Ryzen Threadripper PRO 5975WX (64 cores @ 4.56 GHz) running Fedora Linux 42._

## 🔭 Roadmap

| Target              | Status      | Notes                       |
| ------------------- | ----------- | --------------------------- |
| Rust crate          | ✅ released |                             |
| **Python** bindings | 🛠 next      | `pyo3`, published to PyPI  |
| **Node‑API** module | ⏩ queued   | Native addon for TS/JS      |
| **WASM** build      | ⏩ queued   | For browsers and more       |

---

## 🤝 Contributing

Issues and PRs—especially fuzz corpora and non‑Rust bindings—are very welcome. A `CONTRIBUTING.md`
will land before the first non‑Rust release.

---

## 📝 License

MIT or Apache 2 © 2025 Aaron Friel
## 🧱 Architecture

- `JsonModem` is the minimal, low‑overhead event core. It emits fragment‑only string events and never builds composite values. Internally it now uses a single `Vec<ParseEvent>` buffer (no `EventsOut`), which the iterators drain.
- `JsonModemBuffers` is an adapter over the core that coalesces consecutive string fragments per path and optionally attaches a full value or growing prefix.
- `JsonModemValues` is an adapter that maintains its own `ValueBuilder` and a small per‑feed output queue to emit partial/complete values with low overhead.

This separation keeps the core lean and predictable while enabling higher‑level behaviors via small, focused adapters.

### Streaming Values Example

```rust
use jsonmodem::{JsonModemValues, ParserOptions};

let mut vals = JsonModemValues::new(ParserOptions::default());

// Multi-root stream: two objects back-to-back
let out: Vec<_> = vals
    .feed("{\"a\":1}{\"b\":2}")
    .map(|r| r.unwrap())
    .collect();
assert!(out.iter().all(|sv| sv.is_final));
assert_eq!(out.len(), 2);

// Split across chunks: only emits once the root completes
let partial: Vec<_> = vals.feed("{\"msg\":\"he").collect();
assert!(partial.is_empty());
let done: Vec<_> = vals
    .feed("llo\"}")
    .map(|r| r.unwrap())
    .collect();
assert_eq!(done.len(), 1);
```

### Buffered Strings Example

```rust
use jsonmodem::{
    JsonModemBuffers, ParserOptions, BufferOptions, BufferedEvent, path
};

// Values mode: attach the full string only when it ends
let mut b = JsonModemBuffers::new(
    ParserOptions::default(),
    BufferOptions::default()
);

// No event until string completes across chunks
let mut seen = false;
{
    let mut it = b.feed("{\"a\":\"he");
    while let Some(_ev) = it.next() {
        seen = true;
    }
}
assert!(!seen);

let mut matched = false;
{
    let mut it = b.feed("llo\"}");
    while let Some(ev) = it.next() {
        match ev.unwrap() {
            BufferedEvent::String { path, value: Some(v), is_final: true, .. }
                if path == path!["a"] && v.as_ref() == "hello" =>
            {
                matched = true;
            }
            _ => {}
        }
    }
}
assert!(matched);

// Prefixes mode: attach the growing prefix on every flush
let mut p = JsonModemBuffers::new(
    ParserOptions::default(),
    BufferOptions::default()
);

// End-of-chunk flush emits current prefix with is_final=false
let mut saw_prefix = false;
{
    let mut it = p.feed("{\"code\":\"ab");
    while let Some(ev) = it.next() {
        if let BufferedEvent::String { path, fragment, value: Some(v), is_final: false } = ev.unwrap() {
            if path == path!["code"] && fragment.as_ref() == "ab" && v.as_ref() == "ab" {
                saw_prefix = true;
            }
        }
    }
}
assert!(saw_prefix);
```
