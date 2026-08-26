# Performance after PR #74

This report measures the compatibility frontend after rebasing onto
[PR #74](https://github.com/AaronFriel/jsonmodem/pull/74), which fixes streaming
buffer ownership. The runtime commit is
[`38812b1`](https://github.com/friel-openai/jsonmodem/commit/38812b1bbd62b80b3a89113f4c7575bedd0f2f8a).
The complete-document reader and writer are unchanged by the rebase. Streaming
keeps PR #74's snapshots and retained buffer export, plus the frontend's
byte-view dimension and bytes-subclass restrictions.

Measurements use CPython 3.12.13, orjson 3.11.9, NumPy 2.5.2 and a release
build with Rust 1.94.1 on an AMD EPYC 7763. Timing is pinned to CPU 0, except
for the initial streaming runs explicitly labeled below. Tests, builds and profiling
finish before timing starts. This is a shared host, so small differences are
not evidence of a general speedup.

## Benchmark results

Complete-document ratios below are jsonmodem time divided by orjson time.
A ratio of 1.75 means 75% longer; 0.68 means 32% less time. Each measurement
times many calls, with the same call count for both libraries, calibrated until
the slower batch takes at least 0.1 seconds. The libraries alternate running
first. The table gives the median of 11 measurement ratios. Results and output
bytes are checked before timing. Profiling is disabled.

The AVX2 column uses identical source compiled with
`RUSTFLAGS='-C target-feature=+avx2'` in a separate package. It is an experiment,
not the shipped configuration. This flag affects all newly compiled crates,
so the results do not isolate `memchr` or a particular scanner.

| Input | Portable loads | AVX2 loads | Portable dumps | AVX2 dumps |
| --- | ---: | ---: | ---: | ---: |
| small | 1.22 | 1.19 | 1.75 | 1.85 |
| medium | 1.68 | 1.75 | 1.87 | 1.89 |
| integers | 1.59 | 1.62 | 2.73 | 2.71 |
| floats | 1.87 | 2.01 | 1.07 | 1.03 |
| strings | 1.40 | 1.38 | 1.81 | 2.21 |
| escaped strings | 1.97 | 1.99 | 2.53 | 2.42 |
| long string | 0.49 | 0.68 | 1.79 | 2.38 |

A repeat with 15 measurements per library gave portable small loads/dumps
ratios of 1.34/1.97 and medium ratios of 1.71/1.86. These remain below twice
orjson's time, but the other rows show that this is not true for every input.
The long-string repeat measured 23.6 microseconds for portable loads versus
31.5 for AVX2, and 19.5 versus 25.1 for dumps. The AVX2 flag made these cases
slower in both experiments. The portable build remains the default.

Objects and options use the same method. NumPy arrays contain the numbers
0 through 99,999, arranged as specified. Consecutive whole numbers do not
represent every possible floating-point input.

| Workload | First portable run | Portable repeat | AVX2 run |
| --- | ---: | ---: | ---: |
| sorted medium | 2.35 | 2.34 | 2.17 |
| 1,000 dataclasses | 22.23 | 22.26 | 22.61 |
| 1,000 integer keys | 1.19 | 1.19 | 1.16 |
| 1,000 Fragments | 1.41 | 1.43 | 1.36 |
| NumPy int64, 25,000 x 4 | 0.68 | 0.69 | 0.69 |
| NumPy float32, 25,000 x 4 | 0.86 | 0.86 | 0.86 |
| NumPy float64, 25,000 x 4 | 0.86 | 0.86 | 0.82 |

The repeats and AVX2 object run use 15 measurements. In the first portable
run, flat NumPy arrays took 1.74/1.12/1.08 times orjson for int64/float32/float64.
Arrays with 100 values per row took 1.48/1.10/1.07 times orjson. The four-column
array advantage does not generalize to all layouts.

Portable memoryview loads were rerun separately with 11 measurements. Inputs
are constructed before timing; views backed by arrays use `array.array("B")`.

| Input | bytes | bytearray | bytes-backed view | array-backed view |
| --- | ---: | ---: | ---: | ---: |
| small | 1.23 | 1.25 | 1.72 | 1.72 |
| medium | 1.72 | 1.76 | 1.71 | 1.72 |
| long string | 0.25 | 0.57 | 0.29 | 0.59 |

Long-string orjson times varied between roughly 46 and 93 microseconds across
input types and runs; the cause was not established. Keep the whole table
rather than treating its lowest ratios as a new optimization. The earlier
[buffer report](BUFFERS.md) also records this variation.

## Streaming

The buffer benchmark compares the pre-rebase `aaec131` package with `38812b1`.
It processes 1,024 four-byte strings in 512-byte chunks and consumes every event.
Seven pairs alternate which interpreter runs first. Each interpreter reports
the median of three measurements of 200 streams. The ratio is new time divided
by old time, not a comparison with orjson. All event counts matched.

| Input mode | New / old time | Range of the seven ratios | Allocations per stream, old / new |
| --- | ---: | ---: | ---: |
| bytes | 0.797 | 0.764-0.898 | 2,921.46 / 2,921.46 |
| bytearray | 0.800 | 0.763-0.915 | 2,936.07 / 2,936.07 |
| memoryview | 0.788 | 0.755-0.917 | 3,011.07 / 2,921.07 |
| byte views from bytes | 0.920 | 0.899-0.967 | 4,111.07 / 4,126.07 |

Allocation profiling runs separately over 100 streams. Memoryviews avoid the
older repeated copies and attribute-name allocations. Byte-view mode adds one
dimension-check attribute name per chunk. The timing improvement also occurs
for bytes, where the parsing work is unchanged; this experiment does not
attribute all of that improvement to buffer ownership changes.

The same comparison between portable and AVX2 builds gave these ratios:

| Input mode | Four-byte strings, 512-byte chunks | 256-byte strings, 4,096-byte chunks |
| --- | ---: | ---: |
| bytes | 1.043 | 1.021 |
| bytearray | 1.017 | 1.020 |
| memoryview | 1.014 | 1.028 |
| byte views from bytes | 0.981 | 0.997 |
| byte views from a read-only exporter | 0.969 | 0.992 |

All allocation counts matched between those two builds. Byte-view timing
ranges crossed 1.0, and ordinary event modes were generally slower with AVX2.
This provides no reason to enable the compiler flag globally, even for larger
chunks. Runtime dispatch or a different classification algorithm still needs
its own experiment.

Initial streaming runs did not pin CPU affinity. In the input order above,
the four rebase ratios were 0.829/0.820/0.815/0.903. The five AVX2 ratios were
1.047/1.037/1.037/0.994/0.992 for short strings and
1.023/1.032/1.028/1.006/1.003 for longer strings. The tables use the later
CPU-pinned runs; the benchmark now pins both the parent and its workers.

The existing jiter comparison was also rerun with jiter 0.16.0, 1,024 four-byte
strings and 512-byte chunks. pyperf's quick run reported means of 496 us for
`JsonModemValues` update iteration, 503 us for its iterable-input form, 1.04 ms
for `view()` plus `repr` after every chunk, and 695 us for jiter reparsing and
formatting every cumulative prefix. Update iteration and full-prefix observation
do different work; the view representation also includes a wrapper string.
These figures do not establish a general streaming advantage. pyperf warned
that the quick sample was insufficient to establish less than 1% variation.

## Allocations compared with orjson

Memray 1.20.0 recorded 30 calls after ten unmeasured calls. Inputs were built
before tracking and results discarded. Events count allocation requests;
peak bytes is the most tracked memory held at once. Neither is process RSS.
Counts include the benchmark loop. Each cell lists **jsonmodem / orjson**.

| Workload | Events over 30 calls | Peak bytes |
| --- | ---: | ---: |
| medium loads | 135,842 / 134,943 | 289,852 / 928,870 |
| small dumps | 127 / 97 | 388 / 1,129 |
| medium dumps | 397 / 277 | 119,199 / 65,641 |
| long-string dumps | 157 / 127 | 286,797 / 2,097,257 |
| sorted medium | 30,457 / 30,337 | 122,823 / 69,305 |
| 1,000 Fragments | 307 / 217 | 30,458 / 16,489 |
| 1,000 dataclasses | 1,436,019 / 247 | 63,733 / 32,873 |
| NumPy float32 | 1,568 / 751,027 | 2,293,021 / 4,073,865 |
| late default callback | 2,397,759 / 487 | 42,675,883 / 33,558,273 |
| small loads, array view | 337 / 247 | 3,372 / 4,336 |
| small loads, bytes | 247 / 247 | 330 / 4,336 |
| medium loads, array view | 135,948 / 134,958 | 343,576 / 928,870 |
| long-string loads, array view | 187 / 127 | 288,172 / 1,867,857 |
| long-string loads, bytes | 97 / 127 | 143,473 / 1,867,857 |

The allocation benchmark's medium input has three fields per object, while
the ordinary timing benchmark has four; both libraries receive the same data
within each comparison. [MEMORY.md](MEMORY.md) retains separately labeled
earlier RSS results. RSS was not rerun for this rebase.

## What profiling found

Native CPU profiles use py-spy 0.4.2 at 49 samples per second for eight seconds
per case. The counts below include only samples inside the workload loop.
Each count includes time in the named function's callees, so rows overlap and
must not be added. These are indications of where to investigate, not predicted
speedups. cProfile counts Python calls separately; Memray records allocations
separately. None of these instrumented runs supplies benchmark timings.

| Workload | Observed work | Samples |
| --- | --- | ---: |
| integer-array dumps | appending each formatted number to output | 182 / 382 |
| integer-array dumps | extracting Python integers | 66 / 382 |
| integer-array dumps | formatting integers | 60 / 382 |
| float-array loads | standard-library `f64::from_str` | 126 / 391 |
| float-array loads | `DocumentReader::number` | 68 / 391 |
| integer-array loads | creating Python numbers | 103 / 387 |
| integer-array loads | appending Python list elements | 101 / 387 |
| integer-array loads | `DocumentReader::number` | 63 / 387 |
| medium loads | looking up cached keys | 71 / 389 |
| escaped-string dumps | `plain_string_prefix` | 79 / 381 |
| NumPy float32 dumps | `zmij` formatting | 263 / 364 |

The integer dumps profile lost five samples, escaped-string dumps lost eight,
and NumPy lost 23. The loads profiles had no sampling errors. Some samples
occurred during setup and are excluded from the denominators above. Stripped
CPython and orjson symbols limit native attribution. Separate long-string
jsonmodem and NumPy orjson profiles lost most of their samples; no function
percentages are claimed from them. Structured speedscope JSON preserves Rust
type names that contain semicolons, which are ambiguous in folded-stack text.

For 100 calls serializing 1,000 dataclasses, cProfile recorded 1,902,002 function
calls in jsonmodem versus 102 in orjson. jsonmodem called `_dumps_fields`
100,000 times, `isinstance` 600,600 times, and `startswith` 200,000 times.
These counts explain interpreter overhead; cProfile's elapsed times are not
comparable to the uninstrumented benchmark.

Memray's native traces locate two temporary Python string allocations per
`loads(memoryview)` call: the attribute name `c_contiguous` and method name
`tobytes`. Across 30 calls, each caused 30 allocations. Copying the view caused
another 30 allocations. The copy protects input ownership and should remain;
interning the two names does not require changing that protection.

## SIMD opportunities

The string scanner already uses SIMD. Disassembly of the portable release
build shows two 128-bit SSE2 loads per 32-byte batch in
[`plain_string_prefix`](../../jsonmodem/src/document.rs). Its Rust source uses
checked eight-byte loads and integer masks; LLVM vectorizes the larger loop.
An AVX2-only experimental build generates 256-bit instructions. Compiler flags
alone do not establish an end-to-end speedup, and that experimental wheel must
not be distributed to machines without AVX2.

The Python build currently enables `memchr`'s `alloc` feature, but not `std`.
Enabling `std` only for Python would allow runtime AVX2 selection while retaining
the core's default `no_std` build. This uses an existing dependency and requires
no handwritten intrinsics. It is a candidate experiment, not a measured benefit
of that feature alone. [memchr documents this distinction](https://docs.rs/memchr/latest/memchr/#crate-features).

The streaming scanner's `consume_string_ascii_fast` first uses `memchr2` for
quotes and backslashes, then scans the same prefix for control and non-ASCII
bytes. A combined vector comparison could replace those two passes. The
complete-document scanner can similarly classify quote, backslash and control
bytes with a mask. Keep short-input and final-byte handling bounded, preserve
chunk carryover, and test every alignment and split. Do not read beyond the
input to fill a vector.

`DocumentReader::number` scans digits before the Python decoder parses the
token again. Combining validation with conversion could remove repeated work.
Rust 1.94.1's [float parser](https://github.com/rust-lang/rust/blob/1.94.1/library/core/src/num/dec2flt/parse.rs)
already reduces eight-digit groups with integer arithmetic. The opportunity
is to avoid the separate JSON scan, or accelerate that scan and integer
conversion, rather than duplicate the float parser's existing optimization.
Eight-digit conversion also appears in
[simdjson's number parser](https://github.com/simdjson/simdjson/blob/master/include/simdjson/generic/numberparsing.h).
Keep short integers cheap and retain exact 64-bit bounds, JSON number grammar,
floating-point rounding, non-finite rejection and a fallback for long tokens.
Runtime CPU selection belongs outside the per-number loop, not on every group
of eight digits. [simd-json's implementation](https://github.com/simd-lite/simd-json/blob/main/src/numberparse.rs)
also explains why dispatch overhead matters for these small operations.

SIMD cannot eliminate Python object construction or callbacks. Numeric loads
still create one Python object per number. NumPy float formatting also has
variable-length output and exact decimal-format requirements; vectorizing
arithmetic alone is not enough. Any proposal needs random bit patterns,
subnormals, exponents, non-finite values and mixed digit lengths, not only an
array containing consecutive whole numbers.

## Other priorities

The largest measured gap is dataclass serialization. Move more of its outer
loop into Rust and append fields to the parent output buffer, while retaining
owning field snapshots before calls into Python. The current implementation
creates a field dictionary and a separate encoded result for every object.
Memray attributed 480,000 allocation requests to field-dictionary construction
over 30 calls. Tests must preserve extra attributes, slots, private-field
filtering, callback order, mutations and mixed-container depth limits.

For integer arrays, benchmark output batching or formatting directly into
checked output storage before replacing the number formatter. The native
profile places more samples in small output copies than in integer formatting.
Preserve exact output bytes and avoid uninitialized or out-of-bounds writes.
The subsequent [output-buffer experiments](OUTPUT_BUFFERS.md) tested both
approaches. Neither candidate improved integer output, so both were removed.

For repeated dictionary keys, test a small bounded cache before the current
hash map. Four repeated keys should not require a full hash calculation on
every lookup. Compare diverse and adversarial keys too; do not replace
randomized hashing with an unbounded collision risk.

Interning `c_contiguous` and `tobytes` is the smallest allocation change to try.
The existing streaming code already uses `pyo3::intern!` for `obj`. Confirm
the expected two-allocation reduction with Memray and measure tiny inputs,
where setup costs matter most. Apart from the rejected buffer experiments,
these proposals have not been implemented or benchmarked.

## Reproduction

Build with `.agent/check-py.sh`. The benchmark scripts accept output paths for
all measurements, including the individual timing samples. Run profiling in
separate processes from timing:

```sh
python crates/jsonmodem-py/benchmarks/bench_orjson_compat.py \
  --rounds 11 --seconds 0.1 --output /tmp/ordinary.json
python crates/jsonmodem-py/benchmarks/bench_compat_objects.py \
  --rounds 11 --seconds 0.1 --numpy-shapes rows4 flat rows100 \
  --output /tmp/objects.json
python crates/jsonmodem-py/benchmarks/bench_orjson_compat.py \
  --workloads small medium long_string --rounds 15 --seconds 0.1 \
  --output /tmp/ordinary-repeat.json
python crates/jsonmodem-py/benchmarks/bench_orjson_compat.py \
  --workloads small medium long_string --operations loads \
  --loads-inputs bytes bytearray memoryview array_view \
  --rounds 11 --seconds 0.1 --output /tmp/buffers.json
python crates/jsonmodem-py/benchmarks/bench_allocations.py \
  --module jsonmodem --calls 30 --output /tmp/allocations.json
```

Repeat the object benchmark with 15 measurements and its default `rows4` layout.
Repeat allocations with `--module orjson` and a new output path. For streaming,
install the two release wheels in separate environments, then run:

```sh
python crates/jsonmodem-py/benchmarks/bench_buffer_inputs.py \
  --baseline-python /path/to/baseline/bin/python \
  --candidate-python /path/to/candidate/bin/python \
  --cases bytes bytearray memoryview byte_views_bytes
python crates/jsonmodem-py/benchmarks/bench_jiter_chunked.py \
  --group partial_values --workload array_strings_1024 --chunk-size 512 \
  --fast --affinity 0 -o /tmp/jiter.json
```

For the SIMD experiment, build a separate wheel using the AVX2 flag shown above
and a separate `CARGO_TARGET_DIR`. Do not overwrite the portable environment.
Rerun the ordinary and object scripts with that interpreter. Compare portable
and AVX2 streaming with all default cases, then repeat with
`--string-length 256 --chunk-size 4096`. Both environments need `pyperf` and
Memray; the jiter comparison additionally needs jiter.

CPU and allocation profiles:

```sh
py-spy record --native --format speedscope --rate 49 --duration 8 \
  -o /tmp/integers.speedscope.json -- python \
  crates/jsonmodem-py/benchmarks/profile_compat.py \
  --module jsonmodem --workload dumps_integers --mode loop --seconds 10 --calls 100
python crates/jsonmodem-py/benchmarks/profile_compat.py \
  --module jsonmodem --workload dataclasses_1000 --mode cprofile \
  --calls 100 --output /tmp/dataclasses.prof
python crates/jsonmodem-py/benchmarks/profile_compat.py \
  --module jsonmodem --workload dataclasses_1000 --mode memray \
  --calls 30 --output /tmp/dataclasses.bin
```

Repeat the last two commands with `--module orjson` and different output paths.
Memray profiles include native stacks and Python allocator requests. Install
`py-spy`, `memray`, `orjson` and NumPy in the benchmark environment. Native
sampling requires permission to inspect the benchmark's child process.
