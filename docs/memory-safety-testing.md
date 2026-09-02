# Memory-safety tests

Run these commands from the repository root:

```sh
bash .agent/check-miri.sh
bash .agent/check-py-memory.sh
```

The first command executes Rust tests under Miri. The second loads an
AddressSanitizer-instrumented Python extension into CPython. They check different
operations; neither proves that every possible use is safe.

These two commands do not run the Rust tests in `jsonmodem-py`; those tests
need separately linked native executables. The default AddressSanitizer setup
installs maturin and pytest, but not orjson or NumPy. Tests requiring either
optional dependency skip when it is absent; inspect the reported skips.

## Rust tests

Miri needs a Rust nightly toolchain with `miri` and `rust-src`, plus
`cargo-nextest`. `.agent/setup.sh` installs these tools. The script logs the
compiler version so a failure can be reproduced with the same nightly. Set
`JSONMODEM_MEMORY_TOOLCHAIN` to a dated nightly to reproduce a recorded run.

The full suite excludes `jsonmodem-py` and `jsonmodem-fuzz`. It includes the
Rust parser, saved fuzz regression inputs, and `jsonmodem-py-validation`.
The validation crate includes selected production helper files without linking
Python, so Miri checks those pointer operations but not their CPython callers.
It does not run a live fuzzer. Tests that render `insta` snapshots remain
excluded under Miri;
`tests/memory_safety.rs` uses plain assertions for the streaming behavior it
checks, so it does not need snapshot filesystem access.

The targeted `jsonmodem` tests run with execution seeds 0, 1, and 2 under
Stacked Borrows and
Tree Borrows. These are two models Miri uses to detect invalid overlapping Rust
references. The execution seed changes choices such as allocation addresses.
It does not specify the generated JSON inputs. The generated-input test uses
deterministic indices, defaults to 32 cases, and prints the count. Override it
with `JSONMODEM_SAFETY_CASES`; the script explicitly forwards that setting into
Miri's otherwise isolated environment. The two older QuickCheck tests retain
their existing reduced counts under Miri.

For a focused run:

```sh
bash .agent/check-miri.sh targeted
cargo test -p jsonmodem --lib memory_safety
cargo test -p jsonmodem --test memory_safety
```

### Scanner

`parser/scanner/mod.rs` copies text through safe string slices. Rust checks the
slice bounds and character boundaries in release builds as well as tests.
The scanner no longer converts arbitrary bytes with unchecked UTF-8 casts.

`memory_safety_prefix_copy_operations` exercises `finish`,
`switch_to_owned_prefix_if_needed`, and `copy_prefix_to_scratch` with empty,
ASCII, and multibyte prefixes. Each assumes the anchor and cursor select valid
character boundaries in the input string. The test deliberately clears captured
text to exercise the branch that copies from the input batch.

`memory_safety_owned_ascii_and_raw_captures` and
`memory_safety_text_capture_accepts_unicode` exercise `push_text_to_scratch`,
which accepts a `str` rather than arbitrary bytes. The invalid-boundary test
deliberately places a cursor inside a multibyte character and expects string
slicing to panic. It cannot create an invalid Rust string.

The integration test `every_character_boundary_preserves_values_and_strings`
tries every valid split position in short inputs, then feeds each character
separately. It covers Unicode escapes, surrogate pairs, multibyte characters,
empty strings, duplicate keys, and nested containers. Completed values are
compared with `serde_json`; buffered string events are compared with a single
feed of the same input.

### ValueZipper

With `cached-zipper` enabled, `backend/std/value_zipper/cached.rs` caches
pointers to the current value and its ancestors. The root is boxed to keep
its address stable. `align_path` removes descendant pointers before a parent
can grow or be replaced. Its three pointer dereferences return references
tied to the mutable borrow of the owning zipper. The path and value occupy
disjoint fields, so returning both does not require an unsafe reborrow.
Without that feature, `value_zipper.rs` walks the owned tree using safe Rust,
and the core crate forbids unsafe code.

The zipper's containing modules are private. No public API accepts arbitrary
paths for these cached mutations. That restriction and the parser's event
ordering are part of the safety argument. Raw pointers can coexist, but
overlapping live mutable Rust references cannot.

Three direct tests exercise the cached pointer operations. They grow
arrays and ordered maps, read the root between mutations, change siblings,
replace nested values, insert beyond an array's current end, and reuse the
zipper after `take_root`. The tests assert values and paths, not just that the
process survives. Integration tests also exercise generated containers, multiple
roots, partial values, iterator drop, and cleanup after parse errors.
A fourth direct test checks that selecting safe traversal preserves the
zipper's `Send` and `Sync` behavior. Cargo feature unification can enable the
cache through another dependency; see [Rust features](../README.md#rust-features).

### Complete-document pointer helpers

`jsonmodem-py-validation` exercises production helpers using small allocations
with only the required fields initialized. The tests check allocation bounds
and which fields are read. Real CPython layouts require separate native checks.

`integer_tests.rs` and `compact_int_tests.rs` test the integer readers with
storage ending immediately after the required digits. Zero must not read an
unused digit. Unsupported tags and out-of-range values select fallback.
`dense_entry_tests.rs` tests dictionary table layouts, deleted entries,
end positions, arithmetic, alignment and replacement allocations. Arithmetic
checks do not prove allocation bounds; callers must supply valid storage.

`owned_list/live_tests.rs` tests `append_live` with empty, full and sorting
lists, first and last spare slots, stale bytes, repeated references and
replacement storage. One case makes the value point to the object containing
the list length. Valid current metadata is a precondition, not something
these helpers can establish from an arbitrary pointer.

`list_live_overwrite.rs` deliberately claims two writable slots for a
one-pointer allocation. Running this example under Miri should report the
eight-byte store beyond that allocation. An unrelated error does not count
as detection of this fault. The example is not part of the production library.

## Python extension

The native check currently requires Linux x86_64, `uv`, a C linker, `nm` from
binutils, a Rust nightly, and Python with a shared `libpython`. Build products
and a separate virtual environment go under `target/python-memory`. The script
installs a wheel there; it does not replace the ordinary editable extension.
It uses `python3` by default. Set `JSONMODEM_MEMORY_PYTHON` to select another
interpreter, for example `3.13` to match CI.
CI tests Python 3.9 and 3.13. The older version exercises synchronous garbage
collection callbacks that can run while `feed()` allocates Python objects.

`scripts/python_memory_runner.rs` starts CPython from a Rust executable linked
with AddressSanitizer. The extension is built with the same Rust toolchain and
instrumentation. This avoids loading a different compiler's sanitizer runtime.
The script checks that the imported extension is inside its own environment and
references `__asan_init`.

Before testing jsonmodem, the script loads `scripts/asan_failure.rs` as a separate
test library. It deliberately reads beyond an allocation. The check must exit
unsuccessfully and report `AddressSanitizer: heap-buffer-overflow`; an import
error or another crash does not count. That library is never linked into the
production extension. The report is retained in
`target/python-memory/asan-failure.log`.

`test_buffer_safety.py` exercises successful and failed buffer acquisition,
invalid UTF-8, input layout rejection, sliced and multidimensional buffers,
bytearray resizing after success and failure, and saved events after their
parser or input is discarded. It tries all 256 single-byte mutations of a short
JSON string. Python 3.12 and later also exercise Python-defined buffer exporters
and count buffer acquisitions and releases.

Two regressions found bugs that the original tests missed. One exporter returned
different immutable bytes for parsing and payload creation. Byte-view mode now
parses the exact retained export. Another test changed a bytearray from a GC
callback during Python 3.9 parsing. Ordinary buffer input is now copied unless
its storage is known to be immutable. `scripts/gc_buffer_regression.py` runs in a
subprocess and requires actual callbacks inside `feed` on Python 3.9-3.11.

Path conversion, slicing, no-copy byte events, and minimal events use
`tuple_from_owned_items`. It prepares and owns every element before allocating
the outer tuple, then checks the length and allocation result. On full-API
CPython, it fills the new tuple with `PyTuple_SET_ITEM`. This unchecked setter
is valid here because the tuple is private, its slots are empty, every index
is in bounds, and each owned reference is transferred once. No Python callback,
Python allocation, or GIL release occurs during filling.

Limited-API builds, PyPy, and GraalPy retain the checked `PyTuple_SetItem`
operation. Allocation or setter failure releases the tuple and any remaining
prepared owners. A GIL-enabled interpreter remains required.

This ordering matters on Python 3.9: allocating an element can run a garbage
collection callback, and `gc.get_objects()` can expose an incomplete outer
tuple. `test_path_tuple_gc.py` observes this on the old implementation without
dereferencing NULL slots. The same test checks conversion, slicing, and byte
events after the fix. The tests also retain nested events and exercise slicing
with large positive and negative steps.

`tuple_tests.rs` checks empty and larger tuples, repeated owners, and element
lifetimes. A native allocation-failure test checks that failed tuple allocation
releases the prepared references and that a later call succeeds. This is
selected failure coverage, not failure injection at every construction step.

The buffer operations are exercised through `with_buffer_text`, `with_readonly_byte_text`,
`supports_buffer_protocol`, and `BufferExport::drop`. `buffer::with_export`
pins the descriptor on the stack before acquisition. The callback borrows the
guard, so it cannot move the descriptor or release it early. The guard uses
PyO3's interpreter-specific FFI definitions rather than a handwritten layout.
Failed acquisition is not released; a successful export is released once.

Bytes-backed views are checked against their owner's allocation and borrowed
through that owner's safe byte slice. Mutable or unknown ordinary exports are
copied to a Rust vector before parser callbacks, without first constructing a
Rust shared slice over external storage. The exporter must still provide a valid
allocation for the requested length and prevent unsynchronized native writes.
Unknown read-only exporters are copied
to immutable bytes before parsing, so their payloads retain the copy. Known
immutable bytes-backed payloads retain their own export after the temporary
guard releases its export.

### Complete-document decoding

`AsciiText` carries validated ASCII and length requirements into
`strings::new_ascii_string`. Decoded strings carry a classification tied to
immutable scanner output. The constructor checks the length and
`PyUnicode_New` result, then copies into fresh one-byte string storage.
No further Python call or allocation occurs before initialization finishes.
Empty, single-character and non-ASCII strings keep the ordinary constructor.
`test_decode_classified_strings.py` checks scan boundaries, escapes, singleton
identity, scratch-buffer reuse, input release and UTF-8 errors.
That module requires orjson and skips without it.

`ErrorDocument` also uses this constructor for ASCII error documents of at
least 1,024 bytes. It checks ASCII before copying. Conversion still occurs
after looking up the exception class and converting the message, preserving
argument order. Allocation failure returns `MemoryError` instead of panicking
in PyO3's infallible string conversion. Smaller and non-ASCII documents use
the original constructor. `test_error_document.py` checks exception fields,
boundaries, Unicode and exception-factory behavior. Separately linked native
tests inject failure into `PyUnicode_New` and check recovery; they do not
simulate failure at every allocation.

`owned_list::append` retains the exact decoded list and incoming value. It
reads current storage after constructing the value, because construction
can permit callbacks. A spare-slot write precedes the length update and
immediate reference transfer. No allocation, Python call, reference release
or possible unwind may intervene. Full lists and the temporary sorting state
use the original append operation.

`test_decode_owned_append.py` checks growth, nesting, input release and error
cleanup. Separately linked Rust tests additionally check reference counts, finalizers,
self-references, clear/shrink/grow/replace operations, sorting and an injected
growth failure followed by recovery. A separate native test explicitly runs
GC callbacks that mutate a retained list between value construction and append.
It checks current storage without relying on automatic GC inside the decoder.

The decoder's integer and float constructors check new references and propagate
allocation errors. `empty_list` and `empty_dict` call the actual builtin types
through PyO3's safe `call0` and checked owning downcasts. The native tests inject
one-shot allocation failures and check `MemoryError` and recovery. They do not
establish recovery from sustained memory exhaustion. Older streaming container
constructors still include PyO3 operations that panic on allocation failure.

### Reading Python storage while encoding

`copy_integer` checks the built-in integer type's digit offset and width before
reading an exact integer's tag and required digits. It retains no pointer.
Unsupported layouts or values use the original conversion.
`signed_integer` calls `PyLong_AsLongLongAndOverflow`; `unsigned_integer` uses
`PyLong_AsSize_t` on 64-bit targets and PyO3 elsewhere. Error sentinels are
checked separately from valid boundary values. `test_number_conversion.py`
and `test_encode_integer64.py` cover bounds, strict-integer options, converted
keys, subclasses, callbacks and recovery.

`text::compact_ascii_text` borrows existing ASCII storage from an exact Python
string on supported builds. It cannot invoke a codec or create a UTF-8 cache.
The owner remains alive for the borrow. `text::string_text` obtains other
Unicode cache bytes through the CPython API and checks them with
`std::str::from_utf8` before returning Rust text. Invalid UTF-8 becomes a Python
error. An owning reference alone does not establish valid UTF-8.

These checks cover jsonmodem's explicit text conversions. PyO3 0.25.1 still
contains unchecked conversions in generated argument handling and error
formatting. Those conversions are not covered by this local change. This is
not a complete fix for every Python entry point.

`test_encode_string_text.py` exercises ordinary text and callback behavior.
`test_unicode_cache.py` adds isolated invalid-cache regressions for the checked
local conversions. The tests do not exercise the known unresolved dependency
conversions with invalid text.

`borrowed_dict::primitive_keys_valid` checks supported primitive keys without
conversion, Python allocation or output. Refusal starts owning validation.
`DictScalarCursor::lookup_entry` can read a dense, combined dictionary table
with exact string keys. Deleted entries, split storage and other key layouts
use `PyDict_Next`. Each call reacquires the current table.

`DictScalarCursor::next` consumes borrowed primitive values only while their
dictionary retains them. No Python call or reference release can intervene;
output growth uses Rust storage. Fallback and Python error construction first
obtain owning references. Borrowed text must not escape this operation.
The original iteration-position and mutation checks remain.

`test_encode_borrowed_dict.py` and `test_borrowed_key_validation.py` cover mixed
values, deleted entries, converted-key duplicates, error priority, callbacks
and output growth. Separately linked Rust tests in `borrowed_dict/tests.rs`, `tests/lookup.rs`
and `tests/key_validation.rs` check ownership, dense and split tables, mutation,
instance insertion order and refusal before output changes.

### Interpreter and build conditions

These shortcuts require CPython 3.12 or 3.13 with the GIL and full CPython API.
They exclude PyPy, GraalPy, limited-API builds and free-threaded Python.
All except `strings::new_ascii_string` also require Linux x86_64, 64-bit
pointers, little-endian storage and no `Py_TRACE_REFS`. The remaining
conditions differ by helper:

- `strings::new_ascii_string` uses PyO3's Unicode accessors without an additional
  platform or debug-build restriction.
- `text::compact_ascii_text` and generic borrowed dictionary operations have no further
  debug-build exclusion.
- `copy_integer` excludes `Py_REF_DEBUG`.
- Dense dictionary reads, primitive-key checks and direct list append exclude
  `Py_DEBUG` and `Py_REF_DEBUG`.

`Py_TRACE_REFS` and `Py_REF_DEBUG` enable reference tracking; `Py_DEBUG` selects
a debug interpreter. These conditions still require valid CPython objects and
allocator-provided storage. Other builds keep existing PyO3 or C API operations.

The output writer and NumPy scalar copies below have separate conditions;
the Linux x86_64 restriction above does not apply to all native operations.

### NumPy scalar copies and date formatting

`NumericScalarTypes` retains admitted immutable numeric type objects. Its safe
`read` method checks the exact value type and current helper identities before
acquiring a scoped buffer export. Its private unsafe helpers require immutable
scalar storage, check the descriptor and byte width, and return owned primitive
bits. The export is released before formatting can grow output storage.
A read-only descriptor alone would not establish immutability. Valid native
NumPy storage and no unsynchronized native writes remain required.

Arrays and other scalar types use owning snapshots. The date formatter retains
one validated calendar-day prefix within a snapshot serialization. It checks
each tick conversion, recomputes clock and fractional digits, and discards the
prefix after that call. This reuse adds no unsafe operation.

The dedicated root-container writer requires GIL-enabled, full-API CPython
3.12 on 64-bit, little-endian Linux x86_64. It excludes `Py_DEBUG`,
`Py_REF_DEBUG`, and `Py_TRACE_REFS` builds. It owns all admitted entries before
writing, uses only existing ASCII key storage, and checks helper dictionaries
before performing callback-free lookups. Scoped numeric exports retain the
requirements for valid immutable NumPy storage.

The writer grows Rust storage until the final Python bytes allocation. It must
not invoke Python callbacks or release the GIL between checking the helpers
and completing the buffer. Any unsupported case declines before publication;
a publication error is returned rather than retried with earlier helper checks.

`test_numpy_root_vec.py` and `test_numpy_root_dict_vec.py` include output,
admission, helper replacement, and callback-order cases. Separate native tests
exercise writer admission and output-allocation failure followed by recovery.
Those NumPy-dependent native tests are ignored by default and require explicit
execution; an ordinary test-suite exit code does not establish their coverage.

### Other Python calls

`number.rs` normalizes very long JSON decimals before converting them to `f64`.
The normalization uses safe Rust and fixed-size temporary storage. It preserves
floating-point rounding and negative zero while accounting for the exponent
and decimal-point position together. The shared helper may return infinity;
Python and finite-only backends reject that result.

The direct tests in `number.rs` exercise rounding midpoints, discarded nonzero
digits, exponent cancellation, and the overflow policies of the Rust backends.
`test_streaming_numbers.py` includes long-number cases completed by a delimiter,
by `finish()`, and by feeds split into 4,096-byte chunks. These tests describe
the intended coverage; results must identify the revision that ran them.

Streaming `load_number` uses `PyFloat_FromDouble`, `PyLong_FromLongLong`, and
`PyLong_FromUnsignedLongLong` after checking the number's range. Each call runs
while Python is attached and immediately passes the new reference to PyO3's
`from_owned_ptr_or_err`. A null return becomes a Python exception. Integers
outside these ranges still use Python's integer parser and its digit limit.
`test_streaming_numbers.py` covers values, events, byte views, chunk splits,
signed zero, and the digit limit. The tests do not inject a null return into
each constructor; those branches also require source review.

`compat/objects.rs` retains container entries before invoking field getters
or callbacks. Its snapshots, frame storage, class cache, and output buffer use
fallible growth.
`test_dataclass_native.py` checks callback mutation, field ordering, depth,
cleanup, and allocation failures in subprocesses with address-space limits.
The callback-free encoder retains its existing allocation policy; these tests
do not establish catchable allocation failure for every operation in the package.

### Output storage

`OutputBuffer` has two implementations. `Vec<u8>::finish` retains initialized
Rust bytes until `PyBytes_FromStringAndSize` completes its synchronous copy.
The new reference is checked and allocation failure becomes a Python exception.

`PythonOutput` starts with a Rust vector and can promote it to private Python
bytes. `len` counts initialized bytes; `capacity` counts writable storage.
Writes reserve storage before forming destination pointers, initialize the
bytes, and then advance the length. The small vector's own length is updated
when the writer transfers the vector back to its caller.

Growth checks length arithmetic and space for the CPython object header.
`_PyBytes_Resize` receives an exact, uniquely owned, unpublished bytes object.
It can move storage, so the writer refreshes its pointer before writing again.
Cached output ranges use offsets rather than pointers. A failed resize frees
and nulls the object; cleanup must not release it a second time.

`finish()` consumes the writer, sets the initialized length and terminator,
and transfers its one owned reference. No borrowed view can outlive a resize.
The sealed `OutputBuffer::PYTHON_ALLOCATION` flag excludes this writer from
`DictScalarCursor`, which must not retain borrowed dictionary entries across
Python allocation. That cursor keeps Rust-only output storage.

`PythonOutput` requires GIL-enabled CPython 3.12 or 3.13 with the full API and
without `Py_TRACE_REFS`. Other builds keep the Rust vector implementation.
`test_owned_output.py` and native tests cover growth, retained bytes, callbacks,
copied output ranges, empty output and failed reservations. Miri does not run
the live CPython writer. These tests do not prove recovery from every allocation
failure or that freed capacity is returned to the operating system. Measure
allocation traffic, peak live bytes and process RSS separately.

## Measuring buffer-copy cost

`benchmarks/bench_buffer_inputs.py` compares two installed release builds using
the existing synthetic array-of-strings workload, split into 512-byte chunks.
Both environments need Python 3.12 or later, `pyperf`, and `memray`. For example:

```sh
python crates/jsonmodem-py/benchmarks/bench_buffer_inputs.py \
  --baseline-python /path/to/baseline/bin/python \
  --candidate-python /path/to/candidate/bin/python > comparison.json
```

The script alternates the builds' execution order for seven paired measurements.
Each measurement times 200 streams three times and takes the median. It also
tracks allocations over 100 streams in separate Memray runs. Allocation counts
exclude free and unmap records; peak tracked memory is not process RSS. Timings
on a shared host are evidence for that run, not a performance guarantee.

## Limits

The extension rejects `Py_GIL_DISABLED` builds. On those builds a PyO3 Python
token proves thread attachment, not that concurrent Python writes are excluded.
Setting `gil_used=true` is insufficient because callers can force the GIL off.
The current raw copies and tuple initialization require a GIL-enabled build.

CPython itself and the prebuilt Rust standard library are not instrumented by
the native script. `PYTHONMALLOC=malloc` makes Python allocations visible to the
sanitizer allocator, but does not add checks inside CPython. Leak detection is
disabled because CPython retains allocations during shutdown. Buffer-release
assertions detect the specific export leaks they exercise; they do not establish
general leak freedom.

The Python tests do not inject allocation failures into every tuple-construction
step. Those cleanup branches also require source review. They do not fabricate
invalid pointers, prove an arbitrary native exporter's allocation size, or
establish safety under concurrent mutation by another native extension.

Miri does not execute the CPython foreign calls in this setup. The sanitizer
does not check all Rust reference-aliasing rules. Both tools check executions
selected by the tests, not all executions. Coverage here means named assumptions
and tests, not a measured percentage of all unsafe instructions or proof of
soundness.
