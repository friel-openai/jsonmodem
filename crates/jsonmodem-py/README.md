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

Use `JsonModemEvents` when you need event payloads but not their paths:

```python
from jsonmodem import JsonModemEvents

parser = JsonModemEvents()
for kind, path, payload in parser.feed('[1, true]'):
    assert path is None
    print(kind, payload)
list(parser.finish())
```

`JsonModemEvents(track_paths=True)` enables paths for that instance. Without
tracking, `EventBackend` keeps the parent container kinds needed to validate
JSON, but does not store property names or array indices in event paths. The
shared lexer can still buffer property-name text, including names split across
feeds. Omitted paths are `None`; an empty path still means the document root.
Parsing, UTF-8 checks,
number handling, error locations, and the nesting limit are unchanged.

`JsonModemEvents` does not build values or cumulative string prefixes. Its
`feed()` still collects the current call's events before returning an iterator.
Use `JsonModemValues` to build values, and `JsonModem` for path filters or byte
views. Existing `JsonModem()` calls continue to include paths. These choices are
per instance, not Cargo features, so another dependency cannot enable tracking
for your parser.

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

The streaming APIs reject nesting beyond 256 containers before emitting an
event for the excess container. Paths reuse object-key text instead of copying it.
`feed()` creates all events from the supplied chunks before returning;
limit the total data passed to each call and consume its result before feeding
more data. Neither API imposes a total input-size or output-size quota.
Applications must set those limits.
`finish()` completes valid root numbers without requiring trailing whitespace.
Python number events preserve integer tokens as `int` and reject non-finite floats.

Rust backends and Python streaming share the long-decimal conversion.
`loads()` keeps its lexical parser for ordinary numbers and uses the shared
conversion for very long tokens. Python still rejects non-finite decoded
floats, and the integer rules are unchanged. Bounded conversion storage does
not impose an input-size or CPU-time limit.

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
- Before a `default` callback, the serializer keeps a shallow copy of each active
  container's entries. The copy keeps references to the entries;
  it does not copy all nested objects. Changes to the original container during
  the callback do not change which entries the serializer visits.
- Combining dataclasses with other containers cannot bypass the nesting limit
  by overflowing the counter. Inputs exceeding the limit raise `TypeError`.
- `datetime.time` fractions retain all six microsecond digits. The pinned
  orjson 3.11.9 reference omits a leading zero for some five-digit microsecond
  values; jsonmodem does not reproduce that change in represented time.

The package is named `jsonmodem`, not `orjson`. Passing orjson's public tests does
not prove identical behavior for every Python object or malformed input. Test the
options and types used by your application.

`loads` uses jsonmodem's complete-document reader and constructs Python values
directly. It does not call `feed()`, allocate events, or clone paths. It normally
validates grammar while constructing containers. For selected malformed container
endings, it finds the first error without building Python values. It rejects
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

Dataclasses, subclasses, sorted converted keys, and callback results share one
output buffer instead of producing one byte string per dataclass. On supported
CPython builds, this buffer starts in Rust storage and can switch to unpublished
Python bytes when it grows. Other builds keep Rust storage. The serializer
retains parent entries before calling field getters or callbacks. Rust formats
exact UUIDs and supported exact date/time objects directly. Python helpers
handle the remaining date/time cases and prepare NumPy arrays. Dataclass fields
retain their order under `OPT_SORT_KEYS`; ordinary dictionaries inside them
are sorted.

Long strings reserve their UTF-8 length and both quotes before writing, avoiding
a second buffer growth just for the closing quote when no escaping is needed.

With `OPT_SERIALIZE_NUMPY`, supported contiguous, native-endian NumPy arrays and
scalars are formatted from an immutable copy of their bytes, preserving float16/float32
precision without `tolist()` or a Python object per element. NumPy is optional.
Rust chooses how to format the number type once per array and processes each
row together. It does not check the number type or update its position in the
outer array for every element. NumPy arrays must point to valid memory; this
does not protect against arrays constructed from invalid native pointers.

Supported exact immutable numeric scalars use a scoped buffer export and copy
their primitive bits before formatting. Other scalars retain the Python helper
and owning byte snapshot. Date arrays can reuse one validated calendar-day
prefix within a single serialization; clock and fractional digits are still
computed for every value. No date prefix persists between `dumps()` calls.

On eligible CPython 3.12 builds, root lists, tuples, and dictionaries containing
supported exact NumPy numeric scalars can use a dedicated Rust output buffer.
It supports `OPT_SERIALIZE_NUMPY` alone or with `OPT_APPEND_NEWLINE`. It retains
the container entries, checks helper identities, and copies each scalar's
primitive bits before formatting. Dictionary keys must be exact built-in
strings with existing compact ASCII storage; other keys use the regular
serializer without conversion during the attempted shortcut.

The writer finishes the Rust buffer before allocating the returned Python
bytes. It does not restart serialization after that allocation succeeds or
fails. Other options, types, and interpreter builds keep the regular serializer.

Wheels are interpreter-specific rather than `abi3-py39`. They use CPython's
UTF-8 access API and the binding's local validation instead of requiring an
encoded copy on Python 3.9. Build a wheel separately for each supported
CPython version.

The native extension requires a GIL-enabled Python build. Free-threaded builds
are rejected at compile time, even if their GIL could be enabled at runtime.
Raw buffer copies and tuple initialization rely on excluding concurrent Python
access; a PyO3 thread-attachment token alone does not establish that exclusion.

Both complete-document operations use unsafe Rust and call CPython. During
`loads()`, `strings::new_ascii_string` fills a fresh Python string before
publishing it. `owned_list::append` can transfer an owned value into a list's
spare storage. It initializes the entry before increasing the list length;
CPython still handles allocation and growth.

During `dumps()`, `copy_integer` reads selected exact Python integers directly.
`text::compact_ascii_text` borrows existing ASCII storage from an owned Python
string. Other explicit text conversions check the Unicode cache's UTF-8 bytes
before Rust borrows them. PyO3-generated argument handling and error formatting
still contain unchecked text conversions, so these local checks do not cover
every Python entry point.

`borrowed_dict::DictScalarCursor` handles primitive entries without temporary
Python owners. It permits no Python call or reference release while entry
storage is borrowed. Other entries gain owning references before general
serialization continues. Callback serialization keeps its owning snapshots.

`output::PythonOutput` owns its writable storage until serialization finishes.
Each write checks capacity and initializes bytes before increasing the written
length. No pointer or borrowed view of that storage is exposed to callers.
Resizing refreshes the storage pointer. Before returning Python bytes, `finish()`
sets the final size and terminator and transfers ownership once. This
implementation requires GIL-enabled CPython 3.12 or 3.13 with the full API and
excludes `Py_TRACE_REFS` builds. Other builds use a Rust vector and copy its
initialized contents at the end. Borrowed dictionary entries use Rust-only
output storage, so growth cannot call Python while those entries are borrowed.

These optimizations have interpreter and build restrictions. Raw object-layout
readers and the list writer require CPython 3.12 or 3.13 with the GIL on 64-bit,
little-endian Linux x86_64. Debug and reference-tracing restrictions differ by
helper. ASCII construction has separate conditions. Other GIL-enabled builds keep
the existing PyO3 or C API operations. The
[memory-safety document](../../docs/memory-safety-testing.md) names the
conditions, ownership rules and tests.

Python tests cover values, exact output, malformed input, callbacks, buffer
lifetimes and resource limits. Native tests exercise CPython ownership and
selected allocation failures. Miri checks the Rust parser and selected pointer
helpers without executing CPython. AddressSanitizer checks the compiled
extension; CPython itself is not instrumented. Neither tool proves memory
safety or protects against a native extension that supplies invalid storage.

The separate AddressSanitizer runner instruments the Python extension and
launches subprocess tests with the same runtime. Virtual-address limits apply
in ordinary tests, not under AddressSanitizer, whose own shadow memory needs
a large address range. The same depth and lifetime assertions still run.

To repeat the release tests, check out `ijl/orjson` tag `3.11.9` separately,
install that checkout's test requirements into this development environment,
and run `python crates/jsonmodem-py/benchmarks/check_orjson_release.py /path/to/orjson`
from the repository root. The runner checks the release commit and excludes
only four assertions about the package's name or version. Tests that compare
both libraries use orjson 3.11.9 on Python 3.10 or later. Python 3.9 runs the
remaining tests.

## Optional Python acceleration

The Python crate enables its `python-acceleration` Cargo feature by default.
It caches up to eight validated fixed-timezone offsets for one `dumps()` call.
Only datetimes inside containers use the cache. A root datetime cannot reuse
an offset later in the call. After sixteen consecutive misses, the cache stops
looking up and adding entries, but keeps existing owners until the call ends.
Custom timezones, timedelta subclasses, and timezone names that are string
subclasses are not cached.

The cache contains only safe Rust and owns each retained timezone reference.
It compares object identity without calling Python equality or hashing. Only
exact built-in timezones with exact `timedelta` offsets and string names are
admitted, so reuse cannot skip a custom offset callback or delay a custom
name's finalizer. The cache never stores a borrowed pointer to a container item.
Miri can check the cache's actual Rust source; it cannot verify PyO3 or CPython.

To select the ordinary implementation for a caller, use:

```python
import jsonmodem.portable as jsonmodem

encoded = jsonmodem.dumps({"value": 42})
```

`jsonmodem.portable` exports the same API and option constants. Only `dumps()`
selects a different implementation. The choice is per call and does not change
other clients. Package-owned nested key conversion preserves the choice;
callbacks and replaced helpers can make their own explicit library calls.

To omit the additional implementations when building the extension:

```sh
maturin build -m crates/jsonmodem-py/Cargo.toml --release --no-default-features
```

Cargo combines features requested by dependencies, so another dependency may
enable a feature omitted by one declaration. Portable calls remain available
and effective in a feature-enabled build. Neither choice disables existing
native code in PyO3, CPython or jsonmodem, and neither changes the core Rust
crate's `cached-zipper` feature. Both implementations preserve input validation
and supported JSON behavior. Internal allocation and reference counts can differ.

## Benchmark

The [fixed-timezone cache report](benchmarks/PYTHON_ACCELERATION.md) compares
this change with PR #7 and orjson 3.11.9. Repeated fixed timezones improve;
cache misses and some unrelated cases regress. It includes absolute times,
the 275-case mean, streaming controls, Memray and separate process RSS.

The [corrected-build report](benchmarks/PERFORMANCE_SAFE_CAPABILITIES_CORRECTED.md)
measures runtime `96318df` against PR #6 and orjson 3.11.9. It includes
complete calls, streaming, allocations, RSS, and regressions, including the
long non-ASCII string slowdown. orjson 3.12.0 was not measured.

See the [Python performance report](benchmarks/PERFORMANCE.md) for streaming
comparisons, complete-document comparisons with orjson, and CPU and allocation
profiles. The [large-document and worst-case report](benchmarks/PERFORMANCE_24H.md)
records its measured optimizations, allocations, RSS and remaining
regressions. The [public-document and date/time report](benchmarks/PERFORMANCE_36H.md)
covers the preceding builds. The [safer-storage report](benchmarks/PERFORMANCE_SAFE_CAPABILITIES.md)
measures runtime revision `7b7e21c`, before the later decimal, Unicode, tuple,
and NumPy changes. Published results apply only to the runtime revisions
recorded in each report. They do not measure subsequent source changes.
The [earlier report](benchmarks/PROFILE.md) covers performance after
PR #74 and the SIMD build experiments from that revision.

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
