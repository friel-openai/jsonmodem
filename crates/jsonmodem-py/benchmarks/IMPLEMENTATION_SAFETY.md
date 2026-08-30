# Memory safety and implementation

This comparison covers [jsonmodem b0f3190](https://github.com/friel-openai/jsonmodem/tree/b0f3190fb72af0396d9d25256f8d0174efd7ae23)
and [orjson 3.11.9](https://github.com/ijl/orjson/tree/705515d77b28429d0b7c30c3d781abe52e8a1e5a)
on GIL-enabled CPython. jsonmodem makes some ownership rules easier to inspect;
that does not establish that it is more secure overall.

## Ownership and complexity

jsonmodem's [complete-document decoder](https://github.com/friel-openai/jsonmodem/blob/b0f3190fb72af0396d9d25256f8d0174efd7ae23/crates/jsonmodem-py/src/compat.rs#L142)
uses checked Rust input and an explicit container stack. It does not create
streaming events or copy a path for every value. Its
[callback encoder](https://github.com/friel-openai/jsonmodem/blob/b0f3190fb72af0396d9d25256f8d0174efd7ae23/crates/jsonmodem-py/src/compat/objects.rs#L22)
retains active containers and their entries before invoking Python. These
shallow snapshots keep entries alive if a callback changes the container;
they do not freeze or copy nested objects.

orjson's [list serializer](https://github.com/ijl/orjson/blob/705515d77b28429d0b7c30c3d781abe52e8a1e5a/src/serialize/per_type/list.rs#L42)
and [bytes writer](https://github.com/ijl/orjson/blob/705515d77b28429d0b7c30c3d781abe52e8a1e5a/src/serialize/writer/byteswriter.rs#L18)
require more manual pointer-lifetime and capacity reasoning. Rust types make
ownership easier to inspect in these jsonmodem functions. However, jsonmodem's
separate complete-document and incremental parsers, plus Python fallbacks,
also add maintenance work. Neither implementation is simple throughout.

The [changes since b7fe329](https://github.com/friel-openai/jsonmodem/compare/b7fe329765f3e90064cc38f127d3594165116c71...b0f3190fb72af0396d9d25256f8d0174efd7ae23)
add no new local `unsafe` Rust blocks. Existing binding code still uses unsafe
[CPython integer conversions](https://github.com/friel-openai/jsonmodem/blob/b0f3190fb72af0396d9d25256f8d0174efd7ae23/crates/jsonmodem-py/src/compat.rs#L352)
and a [bytes constructor](https://github.com/friel-openai/jsonmodem/blob/b0f3190fb72af0396d9d25256f8d0174efd7ae23/crates/jsonmodem-py/src/compat.rs#L487).
Streaming code and dependencies, including PyO3 and simdutf8, also contain
unsafe implementations. Safe PyO3 datetime accessors still depend on CPython
internals.

## Rejection and resource use

jsonmodem [creates Python values while validating JSON](https://github.com/friel-openai/jsonmodem/blob/b0f3190fb72af0396d9d25256f8d0174efd7ae23/crates/jsonmodem-py/src/compat.rs#L142).
orjson's [yyjson backend](https://github.com/ijl/orjson/blob/705515d77b28429d0b7c30c3d781abe52e8a1e5a/src/deserialize/backend/yyjson.rs#L100)
checks that yyjson successfully validated and built its C document before
constructing Python values. A late syntax error can therefore make jsonmodem
create and discard many Python objects that orjson never creates. yyjson
still allocates parser storage; its rejection is not allocation-free.

jsonmodem copies [memoryview input](https://github.com/friel-openai/jsonmodem/blob/b0f3190fb72af0396d9d25256f8d0174efd7ae23/crates/jsonmodem-py/src/compat.rs#L303)
and [NumPy storage](https://github.com/friel-openai/jsonmodem/blob/b0f3190fb72af0396d9d25256f8d0174efd7ae23/crates/jsonmodem-py/python/jsonmodem/_numpy.py#L17)
into owned bytes before decoding or formatting. Copies cost memory but avoid
borrowing the original storage during subsequent Rust processing. Both
libraries still require valid native pointers, lengths and lifetimes.
Copying cannot repair fabricated buffers or invalid NumPy arrays.

[Grammar, UTF-8, depth and cycle checks](https://github.com/friel-openai/jsonmodem/blob/b0f3190fb72af0396d9d25256f8d0174efd7ae23/crates/jsonmodem-py/README.md#L169)
address specific failures. Applications still need their own limits on input
size, memory use and CPU time. Some output growth returns `MemoryError`, but
[ordinary Rust allocations](https://github.com/friel-openai/jsonmodem/blob/b0f3190fb72af0396d9d25256f8d0174efd7ae23/crates/jsonmodem-py/src/compat.rs#L450)
can still abort the process on allocation failure. `Fragment` inserts
unvalidated JSON and requires trusted content. Duplicate keys remain allowed;
decoding keeps the last value. Neither behavior provides canonicalization.

## What the checks cover

The [AddressSanitizer runner](https://github.com/friel-openai/jsonmodem/blob/b0f3190fb72af0396d9d25256f8d0174efd7ae23/.agent/check-py-memory.sh#L23)
instruments the extension and launcher, not CPython, the prebuilt Rust
standard library or the orjson wheel. It disables leak detection. It checks
executions in the test suite, not every input or every Rust reference rule.

The [Miri runner](https://github.com/friel-openai/jsonmodem/blob/b0f3190fb72af0396d9d25256f8d0174efd7ae23/.agent/check-miri.sh#L18)
checks Rust execution but excludes the Python binding. Compiling with
`cfg(miri)` does not run Miri. The [Rust fuzz targets](https://github.com/friel-openai/jsonmodem/blob/b0f3190fb72af0396d9d25256f8d0174efd7ae23/fuzz/Cargo.toml#L16)
also omit the Python binding. Passing tests, or larger test counts, is not
proof of memory safety.
