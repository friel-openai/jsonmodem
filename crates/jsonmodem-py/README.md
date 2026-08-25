# jsonmodem (Python)

Python bindings for the Rust `jsonmodem` crate, packaged with
`maturin`/`pyo3` as a mixed project. The published Python package
is named `jsonmodem` and contains a native extension module
`jsonmodem._jsonmodem`.

Quickstart (dev):

```
python -m pip install maturin
maturin develop -m crates/jsonmodem-py/Cargo.toml --release
python -c "import jsonmodem, sys; print(jsonmodem.__version__)"
```

## Streaming usage

`JsonModem` exposes the streaming events from the Rust parser. Each event is a
`(kind, path, payload)` triple. The outer event is a normal Python tuple, so
immediate unpacking is fast. `path` is a lightweight `PathView`, and string
payloads are lightweight `StringPayload` objects with `.fragment`,
`.is_initial`, and `.is_final` attributes.

`feed()` accepts one `str`, `bytes`, `bytearray`, or contiguous `memoryview`
chunk, or an iterable of those chunk types. Passing an iterable is the preferred
way to process many small HTTP or LLM fragments because it uses one Python/Rust
call while preserving event order. Immutable bytes-backed input can be borrowed.
Mutable buffers and exporters whose storage cannot be verified as immutable are
copied before parsing, so Python callbacks cannot change text being parsed.

Use constructor options to shape the event stream without switching classes:

```python
JsonModem()                               # all events, decoded strings
JsonModem(paths="content")                # only matching paths
JsonModem(byte_views=True)                # byte-backed string payloads
JsonModem(paths="content", byte_views=True)
```

`paths` accepts a path string or a sequence of path strings. `*` matches one
object key or array index, for example `"items.*.metadata.etag"`. With
`byte_views=True`, `feed()` accepts immutable `bytes` or read-only contiguous
one-dimensional `memoryview` chunks backed by exact `bytes`, or an iterable of
those chunks. Bytes subclasses are rejected in this mode. Unescaped string fragments
that point into the current input are returned as `memoryview` objects; escaped
fragments fall back to `str`.

Direct memoryview inputs in this mode must be backed by `bytes`. Other accepted
read-only exporters are snapshotted into immutable bytes; their payload views
retain the snapshot rather than the original exporter. Parsing and payloads use
the same acquired storage even if an exporter returns different buffers on
successive requests.

```python
from jsonmodem import JsonModem, ParserOptions

parser = JsonModem(ParserOptions(allow_multiple=True))
for kind, path, payload in parser.feed('{"x": 1} {"y": 2}'):
    print(kind, path, payload)
for kind, path, payload in parser.finish():
    print(kind, path, payload)
```

FastAPI exposes Starlette's request object, and Starlette's
`Request.stream()` yields byte chunks without storing the whole body in memory:

```python
from fastapi import Request
from jsonmodem import JsonModem


async def stream_json(request: Request):
    parser = JsonModem(paths="content", byte_views=True)
    batch = []
    async for chunk in request.stream():
        batch.append(chunk)
        if len(batch) < 64:
            continue
        for kind, path, payload in parser.feed(batch):
            if kind == "string":
                fragment = payload["fragment"]
                yield bytes(fragment) if payload["is_view"] else fragment.encode()
        batch.clear()

    if batch:
        for kind, path, payload in parser.feed(batch):
            if kind == "string":
                fragment = payload["fragment"]
                yield bytes(fragment) if payload["is_view"] else fragment.encode()
    for kind, path, payload in parser.finish():
        if kind == "string":
            fragment = payload["fragment"]
            yield bytes(fragment) if payload["is_view"] else fragment.encode()
```

The Python performance benchmarks are written around streams of fragments. The
fair `jiter` comparison reparses every cumulative prefix with
`partial_mode=True`; reassembled full-document decoder timings are kept as
competitor reference results only. Complete-document `loads()` and `dumps()`
have a separate benchmark described below.

## Incremental values

`JsonModemValues` is for callers that want a read-only view of the current JSON
value instead of parser events. It yields `(index, view, path, is_final)`
tuples. `view` is the same reused root `JsonModemValueView` object on every
update, and `path` is a `PathView` pointing at the changed field.

```python
from jsonmodem import JsonModemValues


parser = JsonModemValues()
for index, view, path, is_final in parser.feed([b'{"message":"hel', b'lo"']):
    if path.endswith("message"):
        print(index, view["message"].snapshot(), is_final)
for index, view, path, is_final in parser.feed(b"}"):
    print(index, view.snapshot(), is_final)
```

`JsonModemValueView` exposes read-only operations such as `kind`, `snapshot()`,
`__getitem__()`, and `__len__()`. Python's type system does not have a general
`ReadOnly[T]` for arbitrary objects. Use read-only interfaces such as
`Mapping`/`Sequence` or protocol classes when annotating consumer code;
`typing.ReadOnly` is specific to `TypedDict` fields, and `Final` prevents
rebinding rather than mutation.

The root view is live. If `allow_multiple=True` and one `feed()` call contains
several complete root values, stored updates will all see the latest root by the
time the returned iterator is consumed. Feed and consume one root at a time when
historical root snapshots matter.

Both streaming APIs reject nesting beyond 256 containers before emitting an
event for the excess container. Retained paths share immutable object-key text.
`feed()` still materializes the events from all supplied chunks before returning;
use bounded chunks and consume each result before feeding more data. Neither API
imposes a total input-size or output-size quota. Applications must set those limits.
`finish()` completes valid root numbers without requiring trailing whitespace.
Python number events preserve integer tokens as `int` and reject non-finite floats.

When a synchronous source already has many tiny fragments available, pass the
fragment iterable to `feed()` instead of calling `feed()` once per fragment.
This keeps the same API shape but avoids repeated Python-to-Rust call overhead:

```python
for index, view, path, is_final in parser.feed(chunks):
    ...
```

Build wheels for release:

```
maturin build -m crates/jsonmodem-py/Cargo.toml --release
```

## orjson-compatible frontend

`jsonmodem.loads` and `jsonmodem.dumps` implement the common `orjson` API:

```python
import jsonmodem as orjson

document = orjson.dumps(
    {"b": 1, "a": 2},
    option=orjson.OPT_SORT_KEYS | orjson.OPT_APPEND_NEWLINE,
)
assert orjson.loads(document) == {"a": 2, "b": 1}
```

The frontend includes `JSONDecodeError`, `JSONEncodeError`, `Fragment`, a
`default` callback, datetime/UUID/dataclass support, and the public `OPT_*`
constants from orjson 3.11. Unknown option bits fail instead of being ignored.
This is compatibility for common operations, not a complete drop-in replacement.
Float formatting, exception messages/types for unsupported inputs, NumPy handling,
and uncommon object behavior can differ. Validate application-specific options
before replacing orjson.

Intentional differences include:

- `loads` preserves every integer as a Python `int`; it never rounds an integer
  larger than 64 bits through a float.
- decoding and encoding reject documents nested beyond 256 containers.
- memoryviews with external buffer exporters are rejected.
- `Fragment` content is validated, including after insertion into its container.
- collisions after converting non-string dictionary keys raise an error rather
  than dropping a value or emitting duplicate keys.

`loads` uses jsonmodem's complete-document reader and constructs Python values
directly. It does not call `feed()`, allocate events, clone paths, or run a second
grammar parser. It validates grammar while constructing containers and rejects
trailing commas, non-finite numbers, invalid UTF-8, and unpaired UTF-16
surrogates. `dumps` rejects cycles, unsupported types, integers outside
orjson's signed/unsigned 64-bit range, and non-callable defaults. Non-finite
Python floats serialize as JSON `null`, matching orjson.

`dumps` writes ordinary JSON types directly from Python objects to a Rust byte
buffer. Both native operations use heap-backed container stacks. Cycle and depth
checks run during serialization. Unsupported types and sorted dictionaries use
a slower Python fallback; user callbacks run only after native iterators are
released. This fallback does not have the native operations' throughput.

Wheels are interpreter-specific rather than `abi3-py39`. This lets PyO3 use
CPython's public UTF-8 string access without an encoded copy on Python 3.9.
Build a wheel separately for each supported CPython version.

Tests exercise the compiled Python extension with generated documents, malformed
bytes, numeric chunk splits, callback mutation, restricted buffers, resource
limits, and small thread stacks. Miri covers the Rust core only; it does not prove
the PyO3 binding or CPython FFI free of memory-safety bugs.

## Benchmark

Install `orjson`, build jsonmodem in release mode, and run:

```bash
python crates/jsonmodem-py/benchmarks/bench_orjson_compat.py --output /tmp/jsonmodem-benchmark.json
```

Run from the repository root. The benchmark pins a CPU where supported,
alternates library order, calibrates batches, and reports median paired time
ratios over 11 rounds. It checks semantic equality before timing and records
exact-byte equality separately. The output JSON includes raw timing samples.
See [the experiment record](../../plans/orjson-performance/record.md) for measured
results and workloads that exceed 2x. Measurements are not a guarantee for other
inputs, options, machines, or Python versions.
