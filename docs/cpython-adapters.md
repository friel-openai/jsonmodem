# CPython adapters: ownership and version limits

JSONModem uses small native adapters to avoid repeated reference increments,
conversions, and output copies. These adapters do not make Python object layouts
stable. Every supported CPython minor version needs review and native tests.
Miri checks Rust memory operations; it does not execute CPython's C runtime.

## Borrowed containers

Owning a Python list or dictionary does not freeze its contents. A callback,
descriptor, destructor, or garbage collection can replace entries or resize the
container. Releasing the GIL can let another thread do the same.

The callback-aware encoder retains owning references and uses owning iterators.
It does not retain a pointer to a container slot across output growth or
callbacks.

`DictScalarCursor` has a narrower contract: it borrows entries only while
writing through a Rust buffer, without Python allocation, conversion, decref,
callback, or GIL release. An unsupported entry is promoted to owning references
before general processing. The output-buffer trait is sealed, and the cursor
asserts that its writer cannot allocate Python objects. A Python-bytes writer
must not be substituted there.

## Integer reads are not integer construction

The direct integer readers admit reviewed CPython 3.12/3.13 full-API GIL builds,
with additional platform and layout checks. They check exact types, handle zero
without reading an unused digit, and copy the result into a Rust integer. The
digit-offset check is not a substitute for the version restriction.

Comparable direct reads exist in [Cython 3.1.0](https://github.com/cython/cython/blob/3.1.0/Cython/Utility/TypeConversion.c#L133)
and [msgspec 0.19.0](https://github.com/jcrist/msgspec/blob/0.19.0/msgspec/_core.c#L167).
In contrast, the examined [PyTorch numeric adapters](https://github.com/pytorch/pytorch/blob/v2.7.0/torch/csrc/utils/python_numbers.h)
and [NumPy scalar conversions](https://github.com/numpy/numpy/blob/v2.2.0/numpy/_core/src/multiarray/arraytypes.c.src#L289)
use public integer constructors. These examples support maintaining small
adapters, not constructing CPython headers by hand. JSONModem keeps public
constructors for decoded integers.

Relevant changes are frequent:

| CPython version | Change requiring review |
| --- | --- |
| 3.12 | Integers changed from signed size to a tag and digits. Unicode removed legacy fields. |
| 3.13 | A private integer-conversion signature changed. List slot macros added bounds assertions. Free-threaded object layouts require different synchronization. |
| 3.14 | The ordinary 64-bit object header changed reference-count representation. |

[PEP 757](https://peps.python.org/pep-0757/) describes integer-layout breakage,
including downstream changes for 3.9 and 3.12 and the removal and restoration
of a private constructor during 3.13 development. Newer public writer/export
APIs are preferable to expanding copied layout definitions without review.

## Fresh lists, strings, and bytes

`owned_list::append` constructs and owns a value before inspecting list storage.
It then writes a spare slot, publishes the new length, and transfers the owned
reference without an intervening allocation, callback, or decref. Growth uses
`PyList_Append`. [Cython uses the same spare-capacity technique](https://github.com/cython/cython/blob/3.1.0/Cython/Utility/Optimize.c#L29),
with build restrictions. Unsupported builds use the public API.

The ASCII string constructor first proves that its input is ASCII, calls
`PyUnicode_New`, fills the new object's storage, and only then returns it.
An unfinished string must not be hashed, interned, converted, exposed to Python,
or shared. Those are requirements of [the Unicode construction API](https://docs.python.org/3.14/c-api/unicode.html#c.PyUnicode_New).

`PythonOutput` uniquely owns unpublished bytes. Its initialized length never
exceeds its capacity. Growth checks arithmetic, refreshes the data pointer after
resizing, and invalidates its old pointer after failure. Finishing consumes the
writer. No writable view escapes. [msgspec also resizes private bytes and
refreshes the data pointer](https://github.com/jcrist/msgspec/blob/0.19.0/msgspec/_core.c#L9181).
The comparable implementation does not prove our cleanup or aliasing correct.

## Threads, reentry, and caches

The layout-dependent adapters exclude free-threaded builds. Attaching a Python
thread is not a substitute for locking a mutable container. CPython specifically
warns that borrowed-reference APIs and unlocked list macros can race; use
[owning APIs and the documented container synchronization](https://docs.python.org/3.13/howto/free-threading-extensions.html)
when adding support for those builds.

Caches remain bounded and call-local. Identity keys retain their owners; escaped
key ranges refer to the current output; fixed timezone entries accept only exact,
immutable built-in types. There is no process-global mutable dataclass schema
cache. Reentrant calls create separate caches and output writers.

`test_concurrent_reentry.py` pauses callbacks in separate threads while both
encoders retain unfinished output, exercises recursive calls, and mutates an
input while a callback releases the GIL. These tests complement native GC,
allocation-failure, and sanitizer checks. Passing them is not a proof for every
Python object or interpreter build.

## Text conversion before function entry

PyO3 converts keyword names and some argument-conversion errors before calling
JSONModem. Checks inside the serializer cannot protect those conversions.
The [pinned dependency patch](../vendor/README.md) checks Python-produced UTF-8
before creating a Rust string, including the older limited-API implementation.

Lossy error formatting reads canonical characters with `PyUnicode_GetLength`
and `PyUnicode_ReadChar`. Every index is below the checked length, and each
character is copied into an owned Rust string. The fallback does not call codec
handlers or trust the UTF-8 cache. The initial checked conversion can still
invoke a `strict` handler, and dropping its exception can run a finalizer.
The string must remain owned throughout; callers cannot retain mutable container
storage across the operation.

The tests exercise keyword names, constructor and method arguments, exception
text, replacement codec handlers, recursive conversion and finalizer reentry.
The patch does not audit every PyO3 operation. Miri does not cover these CPython
calls; native tests and sanitizers are required.

Constructors can receive a caller-owned keyword dictionary through the C API.
Generated tuple/dictionary wrappers now copy owning key/value references into
`KeywordArguments` before conversion. The Rust snapshot remains alive through
argument extraction, the Rust call and return conversion. Clearing the original
dictionary during a codec callback or another argument's conversion cannot free
a later argument. Fast function calls keep their existing argument mechanism.
Snapshot collection does not call Python or release the GIL on supported
builds. This does not claim atomic snapshots on free-threaded builds.

`test_keyword_ownership.py` checks object lifetime during codec reentry, later
argument conversion and mutation by another thread. Each diagnostic aborts
before a broken implementation could read the freed later argument.

## Bounded Rust kernels

The shared string classifier accepts `&[u8; 16]`, reads exactly those initialized
bytes, and returns a bitmap. SSE2 admission is compile-time; other targets have
a portable implementation. The classifier does not touch Python, allocate,
retain pointers, or write into caller-provided uninitialized memory.

The classifier's operations work independently on each byte. Comparing
`max(byte, 31)` with `31` identifies control bytes. Two equality comparisons
identify quotes and backslashes. Taking each byte's high bit identifies
non-ASCII bytes when requested. Combining these bits cannot change a different
byte's result. The final mask has exactly sixteen possible bits.

These arguments explain the invariants that tests exercise. Miri checks the
actual intrinsics and allocation boundaries on executed inputs. Exhaustive
single-byte tests and independent scalar comparisons check classification;
they are not a machine-checked proof of the whole parser.

The positive `simd` feature is independent of `cached-zipper`. The cached zipper
keeps its existing owner-bound interface and mutation rules. Disabling both
features forbids unsafe code in the core crate, not in its dependencies or Python
binding. Cargo feature unification can enable either feature through another
dependency; disabling defaults is not a veto.
