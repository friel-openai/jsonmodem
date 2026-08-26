# jsonmodem (Python)

`jsonmodem` reads JSON as it arrives and provides Python views of incomplete
documents. It also provides `loads()` and `dumps()` for complete documents.
The Python package calls a Rust extension, `jsonmodem._jsonmodem`, built with
PyO3 and maturin.

Quickstart (dev):

```
python -m pip install maturin
maturin develop -m crates/jsonmodem-py/Cargo.toml --release
python -c "import jsonmodem, sys; print(jsonmodem.__version__)"
```

## Streaming usage

`JsonModem` returns parser events as `(kind, path, payload)` tuples.
`path` is a `PathView` identifying the location in the document. String
payloads are `StringPayload` objects with `.fragment`,
`.is_initial`, and `.is_final` attributes.

`feed()` accepts one `str`, `bytes`, `bytearray`, or contiguous `memoryview`
chunk, or an iterable of those chunk types. Passing an iterable is the preferred
way to process many small HTTP or LLM fragments because it uses one Python/Rust
call while preserving event order. Immutable bytes-backed input can be borrowed.
Mutable buffers and exporters whose storage cannot be verified as immutable are
copied before parsing, so Python callbacks cannot change text being parsed.

Use constructor options to choose which events are returned:

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

The streaming benchmarks feed both libraries the same sequence of fragments.
For `jiter`, each call reparses all text received so far with
`partial_mode=True`. Timings for a single complete document are reported
separately: they do not measure the cost of reading a stream as it arrives.

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
time the returned iterator is consumed. To keep earlier values, feed one root
at a time and call `view.snapshot()` before feeding the next root.

Both streaming APIs reject nesting beyond 256 containers before emitting an
event for the excess container. Paths reuse object-key text instead of copying it.
`feed()` creates all events from the supplied chunks before returning;
limit the total data passed to each call and consume its result before feeding
more data. Neither API imposes a total input-size or output-size quota.
Applications must set those limits.
`finish()` completes valid root numbers without requiring trailing whitespace.
Python number events preserve integer tokens as `int` and reject non-finite floats.

When a synchronous source already has many tiny fragments available, pass the
fragment iterable to `feed()` instead of calling `feed()` once per fragment.
This avoids repeated Python-to-Rust calls:

```python
for index, view, path, is_final in parser.feed(chunks):
    ...
```

Build wheels for release:

```
maturin build -m crates/jsonmodem-py/Cargo.toml --release
```

## orjson-compatible loads and dumps

`jsonmodem.loads` and `jsonmodem.dumps` implement the common `orjson` API:

```python
import jsonmodem as orjson

document = orjson.dumps(
    {"b": 1, "a": 2},
    option=orjson.OPT_SORT_KEYS | orjson.OPT_APPEND_NEWLINE,
)
assert orjson.loads(document) == {"a": 2, "b": 1}
```

The package includes `JSONDecodeError`, `JSONEncodeError`, `Fragment`, a
`default` callback, datetime/UUID/dataclass support, and the public `OPT_*`
constants from orjson 3.11.9. Tests compare both libraries on the same inputs,
including the exact output bytes and the exceptions they raise. Unknown
option bits fail instead of being ignored. Integers from `-2**63` through
`2**64 - 1` decode exactly; larger integer tokens decode as finite floats or
raise `JSONDecodeError`, matching orjson. `loads()` permits 1,024 nested containers.
`dumps()` permits 254 nested ordinary containers, or 255 when the last is a
dataclass containing no further containers. Empty lists and tuples do not add
to the encoding depth count.

`Fragment` inserts bytes or text verbatim, including malformed JSON. Only use
trusted content. Converted non-string dictionary keys may produce duplicate
output keys, and decoding duplicate keys keeps the last value. There is no
duplicate-rejection option or extra duplicate-tracking set.

These behaviors deliberately differ from orjson:

- `loads()` rejects released memoryviews with `JSONDecodeError` instead of
  reading their old buffer metadata.
- NumPy datetime unit multipliers and dates outside the supported range raise
  `TypeError`. Date calculations check for overflow. They do not reproduce
  crashes or arithmetic overflow found in orjson.
- Before calling a user-provided function, the Python serializer makes a shallow
  copy of the container's entries. The copy keeps references to the entries;
  it does not copy all nested objects. Changes to the original container during
  the callback do not change which entries the serializer visits.
- Combining dataclasses with other containers cannot bypass the nesting limit
  by overflowing the counter. Inputs exceeding the limit raise `TypeError`.

The package is named `jsonmodem`, not `orjson`. Passing orjson's public tests does
not prove identical behavior for every Python object or malformed input. Test the
options and types used by your application.

`loads` uses jsonmodem's complete-document reader and constructs Python values
directly. It does not call `feed()`, allocate events, clone paths, or run a second
grammar parser. It validates grammar while constructing containers and rejects
trailing commas, non-finite numbers, invalid UTF-8, and unpaired UTF-16
surrogates. `dumps` rejects cycles, unsupported types, and integers outside
orjson's signed/unsigned 64-bit range. A non-callable default fails only if needed.
Non-finite Python floats serialize as JSON `null`, matching orjson.

`loads()` accepts C-contiguous memoryviews, including views supplied by native
extensions and views with non-byte element formats. CPython copies the raw
bytes before the Rust parser reads them. Read-only views are copied too: the
underlying storage may still be mutable. Native providers must supply accurate
buffer metadata and keep the storage valid until the copy completes. Copying
does not make fabricated pointers safe. The streaming APIs retain their separate
buffer restrictions described above.

`dumps` writes ordinary JSON types directly from Python objects to a Rust byte
buffer. `loads()` and `dumps()` store their position in up to two nested containers
without a separate memory allocation. Deeper documents use additional heap
storage, not recursive Rust calls. Cycle and depth checks run while writing.
Rust handles sorted dictionaries, Fragments, and primitive non-string keys.

Datetimes, UUIDs, dataclasses, subclasses, sorted converted keys, and callbacks
can use a slower Python serializer. It writes output directly instead of first
copying the entire object graph. It does not replace Fragment placeholders.
It releases Rust container iterators before calling user code. Dataclasses with
values that need no callback can use Rust to write the copied field entries.
Long strings reserve their UTF-8 length and both quotes before writing, avoiding
a second buffer growth just for the closing quote when no escaping is needed.

With `OPT_SERIALIZE_NUMPY`, supported contiguous, native-endian NumPy arrays and
scalars are formatted from an immutable copy of their bytes, preserving float16/float32
precision without `tolist()` or a Python object per element. NumPy is optional.
Rust chooses how to format the number type once per array and processes each
row together. It does not check the number type or update its position in the
outer array for every element. NumPy arrays must point to valid memory; this
does not protect against arrays constructed from invalid native pointers.

Wheels are interpreter-specific rather than `abi3-py39`. This lets PyO3 use
CPython's public UTF-8 string access without an encoded copy on Python 3.9.
Build a wheel separately for each supported CPython version.

Tests exercise the compiled Python extension with generated documents, malformed
bytes, numeric chunk splits, callback mutation, restricted buffers, resource
limits, and small thread stacks. Miri checks the Rust core for certain kinds of
invalid memory access. It does not check the Python binding or its calls into
CPython. The complete-document reader and writers contain no explicit `unsafe`
blocks, but other parts of the package and its native dependencies use unsafe
code. Passing tests is not a proof of memory safety.

To repeat the release tests, check out `ijl/orjson` tag `3.11.9` separately,
install that checkout's test requirements into this development environment,
and run `python crates/jsonmodem-py/benchmarks/check_orjson_release.py /path/to/orjson`
from the repository root. The runner checks the release commit and excludes
only four assertions about the package's name or version. Tests that compare
both libraries use orjson 3.11.9 on Python 3.10 or later. Python 3.9 runs the
remaining tests.

## Benchmark

Install `orjson`, build jsonmodem in release mode, and run:

```bash
python crates/jsonmodem-py/benchmarks/bench_orjson_compat.py --output /tmp/jsonmodem-benchmark.json
```

Run from the repository root. For each input, the script takes 11 timing
measurements of each library. Each measurement times a batch of many calls,
not a single call. The script uses the same call count for both libraries and
increases it until the slower library's batch takes at least 0.03 seconds by
default, or the duration set by `--seconds`. It divides the batch time by the
number of calls to get time per call.

The script alternates which library runs first and uses one CPU core where the
operating system supports that restriction. For each pair of measurements, it
divides jsonmodem's time per call by orjson's. The reported ratio is the median:
the middle of those 11 ratios after sorting them. A ratio of 0.69 means jsonmodem
took 31% less time; 2.0 means it took twice as long.

Before timing, the script checks that the libraries produce equivalent values.
It records whether their output bytes also match. The output JSON contains all
measurements. The [earlier compatibility results](../../plans/orjson-compatibility/record.md)
include cases that take more than twice as long as orjson. Results can change
with the input, options, machine, or Python version.

The [subsequent speedup record](../../plans/orjson-speedups/record.md) reports
three tests where jsonmodem beat orjson. Each used the numbers 0 through 99,999,
arranged in 25,000 rows of four. Writing the array took 31% less time for int64,
and 14% less for float32 and float64. A separate experiment with 15 measurements
per library repeated those results. One-dimensional arrays and arrays with
100 elements per row remained slower. These tests write complete JSON documents;
they do not measure streaming or establish a speed advantage for all NumPy arrays.

For NumPy, dataclass, Fragment, and option timings, install NumPy and run
`benchmarks/bench_compat_objects.py --output /tmp/jsonmodem-objects.json` from
this package directory. Add `--numpy-shapes rows4 flat rows100` to compare
arrays with four elements per row, one-dimensional arrays, and arrays with
100 elements per row.
For allocation counts and peak live bytes, install Memray and run
`benchmarks/bench_allocations.py --output /tmp/jsonmodem-alloc.json`.
Repeat with `--module orjson`. Allocation profiling is separate from timing.

The [buffer comparison](benchmarks/BUFFERS.md) measures complete-document
`loads()` with bytes, bytearrays, and memoryviews, including the time and memory
cost of copying a native-backed view. Use `--operations loads` and
`--loads-inputs bytes bytearray memoryview array_view` with
`bench_orjson_compat.py` to repeat it.

See [memory compared with orjson](benchmarks/MEMORY.md) for direct Memray
comparisons and a separate measurement of the whole process's resident memory
(RSS), including workloads where jsonmodem uses more memory. On Linux, repeat
the RSS comparison with
`python crates/jsonmodem-py/benchmarks/bench_rss.py --output /tmp/rss-comparison.json`
from the repository root.
