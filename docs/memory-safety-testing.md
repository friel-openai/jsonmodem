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

`parser/scanner/mod.rs` has four unchecked UTF-8 conversions. Test and Miri builds
check the selected bytes before each conversion. These assertions are absent
from normal release builds.

`memory_safety_prefix_copy_operations` exercises `finish`,
`switch_to_owned_prefix_if_needed`, and `copy_prefix_to_scratch` with empty,
ASCII, and multibyte prefixes. Each assumes the anchor and cursor select valid
character boundaries in the input string. The test deliberately clears captured
text to exercise the branch that copies from the input batch.

`memory_safety_owned_ascii_and_raw_captures` exercises `push_ascii_to_scratch`,
whose text branch requires ASCII input. The invalid-UTF-8 test deliberately
violates that private helper's requirement and expects the test-only assertion
to panic before unchecked conversion. This confirms the assertion is active
without creating an invalid Rust string.

The integration test `every_character_boundary_preserves_values_and_strings`
tries every valid split position in short inputs, then feeds each character
separately. It covers Unicode escapes, surrogate pairs, multibyte characters,
empty strings, duplicate keys, and nested containers. Completed values are
compared with `serde_json`; buffered string events are compared with a single
feed of the same input.

### ValueZipper

`backend/std/value_zipper.rs` stores pointers to the current value and its
ancestors. `align_path` must discard pointers to old children before inserting
into a parent that might move its contents. `with_leaf` and `with_leaf_mut`
return references tied to the borrow of the zipper, preventing callers from
mutating the tree while those references remain in use.

Three direct tests exercise all five explicit unsafe operations. They grow
arrays and ordered maps, read the root between mutations, change siblings,
replace nested values, insert beyond an array's current end, and reuse the
zipper after `take_root`. The tests assert values and paths, not just that the
process survives. Integration tests also exercise generated containers, multiple
roots, partial values, iterator drop, and cleanup after parse errors.

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

The tuple-building unsafe operations are exercised by saved nested events,
path conversion, path slicing, and no-copy byte events. The buffer operations
are exercised through `with_buffer_text`, `with_readonly_byte_text`,
`supports_buffer_protocol`, and `PyBufferGuard::drop`. The exporter must supply a
valid allocation for the requested length, and the guard must keep the export
alive until the Rust borrow or copy ends. Unknown read-only exporters are copied
to immutable bytes before parsing, so their payloads retain the copy. Known
immutable bytes-backed payloads retain their own export after the temporary
guard releases its export.

### Complete-document decoding

`strings::new_ascii_string` receives ASCII text longer than one byte. Decoded
strings carry a classification tied to immutable scanner output. It checks the length and
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

### Reading Python storage while encoding

`copy_integer` checks the built-in integer type's digit offset and width before
reading an exact integer's tag and required digits. It retains no pointer.
Unsupported layouts or values use the original conversion.
`signed_integer` calls `PyLong_AsLongLongAndOverflow`; `unsigned_integer` uses
`PyLong_AsSize_t` on 64-bit targets and PyO3 elsewhere. Error sentinels are
checked separately from valid boundary values. `test_number_conversion.py`
and `test_encode_integer64.py` cover bounds, strict-integer options, converted
keys, subclasses, callbacks and recovery.

`string_text` borrows compact ASCII from an exact owned string. The owner
outlives the borrow; other strings use PyO3's UTF-8 conversion.
`test_encode_string_text.py` checks ASCII bytes, lengths around buffer and
cache boundaries, Unicode fallback, subclasses and callback mutation.

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
- `string_text` and generic borrowed dictionary operations have no further
  debug-build exclusion.
- `copy_integer` excludes `Py_REF_DEBUG`.
- Dense dictionary reads, primitive-key checks and direct list append exclude
  `Py_DEBUG` and `Py_REF_DEBUG`.

`Py_TRACE_REFS` and `Py_REF_DEBUG` enable reference tracking; `Py_DEBUG` selects
a debug interpreter. These conditions still require valid CPython objects and
allocator-provided storage. Other builds keep existing PyO3 or C API operations.

### Other Python calls

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
fallible growth. `Encoder::bytes` in `compat.rs` calls `PyBytes_FromStringAndSize` with a
borrow of the initialized Rust output. The borrow remains valid until the
synchronous copy returns. PyO3 takes ownership of the new Python object or
propagates the allocation error. No raw pointer escapes the call.
`test_dataclass_native.py` checks callback mutation, field ordering, depth,
cleanup, and allocation failures in subprocesses with address-space limits.
The callback-free encoder retains its existing allocation policy; these tests
do not establish catchable allocation failure for every operation in the package.

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
