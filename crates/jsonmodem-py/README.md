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
constants from orjson 3.11.9, the release used for differential testing. Unknown
option bits fail instead of being ignored. Integers from `-2**63` through
`2**64 - 1` decode exactly; larger integer tokens decode as finite floats or
raise `JSONDecodeError`, matching orjson. Decoding permits 1,024 containers;
encoding permits 254 ordinary containers (255 for a dataclass leaf), with empty
lists/tuples handled as scalar values.

`Fragment` inserts bytes or text verbatim, including malformed JSON. Only use
trusted content. Converted non-string dictionary keys may produce duplicate
output keys, and decoding duplicate keys keeps the last value. There is no
duplicate-rejection option or extra duplicate-tracking set.

The remaining deliberate restrictions are specific:

- `loads(memoryview(...))` requires an exact built-in bytes, bytearray, or
  BytesIO buffer owner. External exporters are rejected with `JSONDecodeError`.
- NumPy datetime unit multipliers and unrepresentable dates raise `TypeError`;
  the formatter uses checked arithmetic rather than reproducing native faults
  or overflowing calendar calculations in the reference implementation.
- Containers handled by the Python callback serializer are snapshotted before
  callbacks. Mutating those containers from a callback does not change the
  snapshot or invalidate a native iterator.
- Mixed dataclass/container nesting cannot wrap the recursion counter to bypass
  the depth limit. Such inputs raise `TypeError`.

Package identity remains `jsonmodem`. Passing the public release tests does not
prove equivalence for every Python object or malformed input; validate the
options and types used by your application.

`loads` uses jsonmodem's complete-document reader and constructs Python values
directly. It does not call `feed()`, allocate events, clone paths, or run a second
grammar parser. It validates grammar while constructing containers and rejects
trailing commas, non-finite numbers, invalid UTF-8, and unpaired UTF-16
surrogates. `dumps` rejects cycles, unsupported types, integers outside
orjson's signed/unsigned 64-bit range. A non-callable default fails only if needed. Non-finite
Python floats serialize as JSON `null`, matching orjson.

`dumps` writes ordinary JSON types directly from Python objects to a Rust byte
buffer. Both native operations use heap-backed container stacks. Cycle and depth
checks run during serialization. Sorted dictionaries and Fragments are native.
Datetimes, UUIDs, dataclasses, subclasses, sorted converted keys, and callbacks use a
slower direct-output Python serializer, without copying the whole object graph
or replacing Fragment placeholders. User callbacks run only after native
iterators are released. This serializer does not have native throughput.
Primitive non-string keys are written natively. Dataclass field snapshots also
use the native writer when their values need no Python callback.

With `OPT_SERIALIZE_NUMPY`, supported contiguous, native-endian NumPy arrays and
scalars are formatted from immutable byte snapshots, preserving float16/float32
precision without `tolist()` or a Python object per element. NumPy is optional.
This assumes valid NumPy storage, not arrays forged from invalid foreign pointers.

Wheels are interpreter-specific rather than `abi3-py39`. This lets PyO3 use
CPython's public UTF-8 string access without an encoded copy on Python 3.9.
Build a wheel separately for each supported CPython version.

Tests exercise the compiled Python extension with generated documents, malformed
bytes, numeric chunk splits, callback mutation, restricted buffers, resource
limits, and small thread stacks. Miri covers the Rust core only; it does not prove
the PyO3 binding or CPython FFI free of memory-safety bugs.

To repeat the release tests, check out `ijl/orjson` tag `3.11.9` separately,
install that checkout's test requirements into this development environment,
and run `python crates/jsonmodem-py/benchmarks/check_orjson_release.py /path/to/orjson`
from the repository root. The runner checks the release commit and excludes
only four package identity assertions. Local differential tests use the pinned
orjson wheel on Python 3.10 or later; Python 3.9 runs the remaining regressions.

## Benchmark

Install `orjson`, build jsonmodem in release mode, and run:

```bash
python crates/jsonmodem-py/benchmarks/bench_orjson_compat.py --output /tmp/jsonmodem-benchmark.json
```

Run from the repository root. The benchmark pins a CPU where supported,
alternates library order, calibrates batches, and reports median paired time
ratios over 11 rounds. It checks semantic equality before timing and records
exact-byte equality separately. The output JSON includes raw timing samples.
See [the compatibility experiment record](../../plans/orjson-compatibility/record.md) for measured
results and workloads that exceed 2x. Measurements are not a guarantee for other
inputs, options, machines, or Python versions.

For NumPy, dataclass, Fragment, and option timings, install NumPy and run
`benchmarks/bench_compat_objects.py --output /tmp/jsonmodem-objects.json` from
this package directory. For allocation counts and peak live bytes, install
Memray and run `benchmarks/bench_allocations.py --output /tmp/jsonmodem-alloc.json`.
Repeat with `--module orjson`. Allocation profiling is separate from timing.
