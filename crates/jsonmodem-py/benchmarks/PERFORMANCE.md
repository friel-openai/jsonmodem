# Python performance results

This report gives absolute timings and allocation measurements for jsonmodem,
orjson and jiter. Streaming value snapshots are compared with jiter. orjson
does not provide an incremental parser, so its results are for complete
documents. The overall complete-document summary is the only ratio table.

The [decoding follow-up](PERFORMANCE_FOLLOWUP.md) measures the next changes
against this report's jsonmodem build and orjson.
The later [public-document and date/time report](PERFORMANCE_36H.md) adds
external parser benchmarks and compares the subsequent changes with orjson.
The [large-document and worst-case report](PERFORMANCE_24H.md) records the
next optimizations, CPU profiles, allocations and RSS.
The [safer-storage and optional-path report](PERFORMANCE_SAFE_CAPABILITIES.md)
measures runtime revision `7b7e21c`, including its complete calls, streaming,
allocations, RSS and regressions. It predates the later decimal, Unicode,
tuple, and NumPy changes.

The measured jsonmodem runtime is
[`9285795`](https://github.com/friel-openai/jsonmodem/commit/9285795ca2ca10570e47a48564d29e12160c2d4d).
The later closing-quote experiment was reverted. The final runtime sources
and rebuilt extension for this historical comparison match that measured revision.

## What changed

- Integer output uses CPython's overflow-reporting conversion instead of
  creating and discarding an exception for every integer above `2**63 - 1`.
  On 64-bit targets, unsigned conversion uses `PyLong_AsSize_t`. Other targets
  keep PyO3's `u64` conversion.
- The complete-document reader converts integer digits while checking their
  grammar. Fraction, exponent and oversized-integer digit runs are checked
  eight bytes at a time. Floating-point conversion still uses Rust's parser.
- Streaming number conversion no longer repeatedly imports Python types or
  parses integer tokens as floats first. Public CPython constructors create
  in-range numbers and propagate allocation failures. Larger streaming
  integers retain Python's exact integer conversion and digit limit.
- Dataclasses and callback results use one Rust output buffer. Owning
  snapshots still retain container entries before callbacks. Small field
  snapshots avoid a separate heap allocation, and a bounded cache retains
  live class dictionaries. Root NumPy output reuses its completed byte string
  when no trailing newline is requested.
- String decoding reuses an escape buffer, retaining at most 64 KiB between
  successful tokens. Cached keys own their text before that buffer is reused.
  Checked 32-byte classification compiles to SSE2 instructions on the tested
  x86_64 build. No global AVX2 flag or unchecked SIMD load is added. Long plain
  root strings are written directly into initialized Python bytes storage.

The 64 KiB limit bounds retained scratch, not the memory required by the
current string. It also does not constrain a caller-supplied buffer in the
public Rust `DocumentReader::string_with_buffer()` method.

## Measurement method

The machine is a shared AMD EPYC 7763 host. All timings use CPU 0, CPython
3.12.13, Rust 1.94.1, PyO3 0.25.1, orjson 3.11.9, NumPy 2.5.2 and jiter 0.16.0.
The benchmark environment also includes pyperf 2.10.0.
The release build uses thin LTO and one code-generation unit, with no native
CPU target flag. Builds, tests and profilers finish before timing starts.
These measurements describe this host and these inputs, not all machines or
Python versions.

Each complete-document case uses seven Python processes, with hash seeds 1729
through 1735. Each process checks results against orjson before timing, then
takes three measurements per library in alternating order. The reported time
is the median of those three measurements, followed by the median across the
seven processes. A measurement times many calls with garbage collection
disabled. Both libraries use the same call count, calibrated until the slower
library's batch takes at least 0.04 seconds. Input construction and process
startup are excluded.

Timing tables show microseconds, not ratios. Reference-library times come
from the same processes as the reported jsonmodem build. Bold marks the
lowest displayed value in each row; ties at the displayed precision are both
bold. Small differences do not establish a repeatable lead. All samples,
including outliers, earlier builds and control repeats, remain in the saved
results. No measurements were rerun for this presentation change.

`bench_output_buffers.py` and `bench_frontend.py` call both libraries through
the same keyword-argument wrapper. `bench_numbers.py` and `bench_strings.py`
call the functions directly. The wrapper matters for tiny inputs; do not
compare absolute times across those two methods.

## Streaming results

[bench_stream_numbers.py](bench_stream_numbers.py) sends 1,024 numbers in
chunks that end at complete tokens, targeting 512 bytes per chunk.

### Reading the value after every chunk

A snapshot is the complete Python value parsed so far. jsonmodem and jiter
produce a snapshot after every chunk. jiter's time includes building the
contiguous input that its API requires. Every snapshot is checked for equal
results before timing.

Time for the entire stream, in microseconds (lower is better):

| Number input | jsonmodem | jiter |
| --- | ---: | ---: |
| Small integers | 434.859 | **251.525** |
| Full-width signed integers | **1,853.584** | 3,304.966 |
| Upper-range unsigned integers | **2,111.035** | 3,843.946 |
| Floats | 1,273.699 | **1,140.936** |
| Mixed numeric types | **1,639.064** | 2,260.592 |
| 200-bit integers | **17,162.695** | 18,589.356 |

### Consuming number events

An event is a parser notification, such as an array starting or a number being
read. This benchmark consumes every event from `feed()` and `finish()`.
The byte-view option returns unescaped string fragments as memoryviews; these
number-only inputs measure its overhead without any string payloads.
Neither orjson nor jiter provides jsonmodem's event API.

Time for the entire stream, in microseconds (lower is better). Bold marks
the faster jsonmodem event mode for each input:

| Number input | Default events | Byte-view events |
| --- | ---: | ---: |
| Small integers | **288.955** | 345.570 |
| Full-width signed integers | **364.893** | 433.669 |
| Upper-range unsigned integers | **373.508** | 427.491 |
| Floats | **377.227** | 452.168 |
| Mixed numeric types | **387.289** | 452.645 |
| 200-bit integers | **670.353** | 718.737 |

### Consuming string events

[bench_buffer_inputs.py](bench_buffer_inputs.py) consumes all events from
1,024 strings. Short strings contain four bytes and use 512-byte chunks;
long strings contain 256 bytes and use 4,096-byte chunks. Each comparison
uses seven processes, with three measurements of 200 streams per process.
These event measurements do not set fixed Python hash seeds.

Default events return decoded strings; byte-view events return memoryviews
for unescaped fragments. The exporter is a Python `__buffer__` wrapper around
bytes. The columns compare these configurations, not different libraries.

Time for the entire stream, in microseconds (lower is better):

| Bytes per string | Default events | Byte-view events | Exporter with byte-view events |
| --- | ---: | ---: | ---: |
| 4 | **334.879** | 485.767 | 494.141 |
| 256 | **445.398** | 629.028 | 688.622 |

## Complete-document reference results

### Overall geometric mean

This summary includes all **171 cases** from the four primary benchmark
scripts: 28 output cases, 58 frontend cases, 25 number cases and 60 string
cases. Each case has equal weight. Input-type variants count separately, and
some payloads occur in more than one script. Control repeats, attribution
experiments, rejected candidates and streaming APIs are excluded.

For each case, use the saved median of paired jsonmodem/orjson timing ratios.
The overall score is `exp(mean(log(case_ratio)))`. This is a benchmark-case
average, not an estimate for a particular application's workload mix.
The [calculated scores](data/performance/geomean.json) retain the full precision
and name the input files.

Time relative to orjson (lower is better). **1.00x is orjson's time**;
1.34x means 34% more time. This is the only table using ratios:

| Cases | PR #1 | PR #2 | orjson |
| --- | ---: | ---: | ---: |
| All 171 cases | 1.76x | 1.34x | **1.00x** |
| Decoding: 106 cases | 1.43x | 1.26x | **1.00x** |
| Encoding: 65 cases | 2.48x | 1.48x | **1.00x** |

### Common inputs

These seven inputs come from [bench_orjson_compat.py](bench_orjson_compat.py).
The mixed input has 1,000 four-field records. Numeric arrays have 10,000
elements; the integer array contains -5,000 through 4,999, and each float is
its index divided by seven. The string and escaped-object arrays have 1,000
elements. The long string has 143,360 UTF-8 bytes. The decoding results below
use `bytes` input.

Decoding with `loads()`, in microseconds per document (lower is better):

| Input | jsonmodem | orjson |
| --- | ---: | ---: |
| Small object | 0.597 | **0.520** |
| Mixed records | 377.173 | **244.502** |
| Short integers | 284.240 | **187.325** |
| Floats | 548.779 | **280.214** |
| Plain strings | 48.719 | **36.906** |
| Escaped objects | 249.791 | **143.609** |
| Long plain string | **22.453** | 93.772 |

Encoding with `dumps()`, in microseconds per document (lower is better):

| Input | jsonmodem | orjson |
| --- | ---: | ---: |
| Small object | 0.397 | **0.269** |
| Mixed records | 162.829 | **88.832** |
| Short integers | 115.382 | **43.850** |
| Floats | 320.949 | **292.853** |
| Plain strings | 25.023 | **13.086** |
| Escaped objects | 87.958 | **40.956** |
| Long plain string | 12.241 | **10.333** |

Earlier runs in [PROFILE.md](PROFILE.md) observed substantially different
orjson long-string decoding times.

### Other output cases

The output cases below use [bench_output_buffers.py](bench_output_buffers.py).
Full-width arrays contain 10,000 seeded random integers. The unsigned array
uses only `2**63` through `2**64 - 1`. Dataclass batches contain 1,000 records.
The eight- and sixteen-field cases have that many declared integer fields per
record. NumPy arrays have 25,000 rows of four consecutive whole numbers.

Encoding with `dumps()`, in microseconds per document (lower is better):

| Output | jsonmodem | orjson |
| --- | ---: | ---: |
| Full-width signed integers | **265.508** | 354.849 |
| Upper-range unsigned integers | **277.512** | 331.948 |
| One integer | **0.161** | 0.166 |
| Five integers | 0.236 | **0.201** |
| Indented short integers | 146.953 | **83.246** |
| Strict short integers | 115.262 | **43.823** |
| Sorted mixed records | 260.091 | **130.867** |
| Integer dictionary keys | **35.067** | 35.205 |
| Dataclass batch | 205.194 | **81.802** |
| One dataclass | 0.930 | **0.263** |
| One slotted dataclass | 1.531 | **0.637** |
| Slotted dataclass batch | 772.375 | **406.752** |
| Nested dataclasses | 530.375 | **196.676** |
| Indented dataclasses | 223.854 | **105.693** |
| Dataclasses with sorted dictionaries | 580.630 | **227.892** |
| Dataclasses with default callbacks | 274.071 | **130.741** |
| NumPy int64 | **930.198** | 1,350.747 |
| NumPy float32 | **2,814.713** | 3,257.625 |
| Default callback after 100 strings | 9.865 | **2.976** |
| Dataclasses with eight fields | 410.918 | **177.188** |
| Dataclasses with sixteen fields | 723.466 | **305.942** |

The frontend comparison also covers bytearrays, bytes-backed memoryviews and
array-backed memoryviews. The raw results include Unicode, escaped keys,
the 255/256-byte output threshold, newline and indentation options.

Additional [numeric](data/performance/numbers.json) and
[string](data/performance/strings.json) results use direct calls. Their
fixtures differ from the seven common inputs. The result files retain all
cases and samples, and the scripts define the inputs and options.

### Unicode and float input

[bench_utf8_inputs.py](bench_utf8_inputs.py) compares bytes with warmed Python
`str` input, using a minimum batch duration of 0.06 seconds. The Unicode
string contains 43,690 copies of U+2603. The initial equality check warms
Python's cached UTF-8 representation. `str` avoids the reader's initial byte
validation, but it also changes ownership and alignment. This comparison
alone does not measure validation's exact cost. The final two rows use the
escaped-input cases from `bench_frontend.py`.

Decoding with `loads()`, in microseconds per document (lower is better):

| Input | jsonmodem | orjson |
| --- | ---: | ---: |
| Floats from bytes | 546.477 | **278.772** |
| Floats from warmed str | 538.843 | **278.000** |
| U+2603 string from bytes | 199.437 | **83.042** |
| U+2603 string from warmed str | 89.381 | **75.112** |
| Unicode-escape array from bytes | 165.088 | **46.246** |
| 600 unique escaped keys from bytes | 142.579 | **36.935** |

## Allocation measurements

Memray 1.20.0 records native and Python allocations separately from timing.
Inputs are built before tracking. Each complete-document run performs ten
warmup calls and thirty measured calls, with garbage collection disabled.
The tables below separate allocation counts, total allocated memory and peak
memory. Each row compares the same thirty calls in both libraries. KiB means
1,024 bytes; MiB means 1,048,576 bytes. None of these measures is process RSS.
The earlier [RSS comparison](MEMORY.md) is separate and was not rerun here.

### Allocation requests

Number of allocation requests across thirty calls (lower is better):

| Input per call | jsonmodem | orjson |
| --- | ---: | ---: |
| 1,000 dataclasses | 398 | **188** |
| Upper-range unsigned output | 368 | **278** |
| Escaped-object input | 146,316 | **85,446** |
| Large escaped first string | 7,494,578 | **7,492,388** |
| NumPy float32 output | **1,091** | 750,968 |

### Total allocated memory

Memory requested across all thirty calls, in MiB (lower is better). Memory
that is freed and allocated again counts each time:

| Input per call | jsonmodem | orjson |
| --- | ---: | ---: |
| 1,000 dataclasses | 2.93 | **1.85** |
| Upper-range unsigned output | 20.98 | **14.98** |
| Escaped-object input | **17.09** | 28.31 |
| Large escaped first string | **817.21** | 1,210.02 |
| NumPy float32 output | **93.64** | 221.43 |

### Peak memory

Most tracked memory held at once during the thirty calls, in KiB
(lower is better):

| Input per call | jsonmodem | orjson |
| --- | ---: | ---: |
| 1,000 dataclasses | 60.6 | **32.4** |
| Upper-range unsigned output | 460.6 | **256.3** |
| Escaped-object input | **321.7** | 980.7 |
| Large escaped first string | **10,836.1** | 41,302.4 |
| NumPy float32 output | **2,238.8** | 3,978.7 |

The large-first-string input contains a 1 MiB escaped string followed by
250,000 integers. The dataclass and unsigned-integer cases allocate more
bytes than orjson, while the escaped inputs and NumPy float32 output use
less total and peak tracked memory.

The string-event harness captures allocations separately over 100 streams
with garbage collection enabled. Short bytes input requests 2,921.46
allocations per stream. For long strings, byte-view events request 5,820.07;
the Python `__buffer__` exporter requests 6,600.07. These captures use a
different call count and garbage collection setting from the complete-document
tables, so their peaks are not directly comparable.

## What the profiles show

For 100 calls writing 1,000 dataclasses, cProfile records 102 calls in both
jsonmodem and orjson. Dataclass traversal runs in native code; cProfile does
not count every native function call.

Complete-document native samples use py-spy 0.4.2 at 49 samples per second,
outside benchmark timing. Profiles request eight seconds while the measured
loop runs for six.
Only samples inside that loop are counted. CPython symbols are partly
stripped, so attribution uses source-qualified Rust frames. Inclusive sample
counts include called functions and can overlap.

For the U+2603 byte input, initial Rust UTF-8 validation appears in 143 of 272
jsonmodem samples. Python string construction appears in 109. These sample
counts identify byte validation as a candidate for improvement but do not
measure its exact cost. Two attempts to profile warmed `str` input lost
most samples to unwinding errors and are excluded.

Float profiles include both `DocumentReader::number()` and Rust's decimal-to-
float conversion. The new reader also computes an integer prefix before
discarding it on finding a decimal point. That is extra executed work, but
these profiles do not establish its share of the total decoding time.

## Experiments removed

Collecting decoded array elements before creating a Python list initially
saved time, but raised peak allocation by 31.7% on the tested numeric array.
The fallible-allocation version lost that speed advantage. The original list
append implementation remains, along with new allocation-failure tests.

Root-list tuple snapshots were slower and failed a GC-mutation test on
CPython 3.9. Safe `i128` extraction slowed common integer output. A fully
unrolled integer scanner slowed mixed documents, so the retained scanner uses
a smaller bounded loop. Adding checked output growth to ordinary containers
also slowed integer output; callback serialization uses checked growth without
changing the callback-free encoder's existing allocation policy.

Returning an optional byte string from the callback traversal recovered NumPy
output-copy cost but slowed dataclass batches by 9.7-16.5% in two comparisons.
Keeping that byte string in an owning field restored the original traversal
return type and removed the dataclass regression. The tests do not establish
which compiler decision caused the slowdown.

The first owning-field version then slowed a five-integer list by 21.7% in
a direct comparison with the earlier build. Retaining `Bound<PyBytes>` instead
of `Py<PyBytes>` brought that comparison back to 1.4% slower. It keeps Python's
attachment in the field's type until the final return. The ordinary-list
serializer does not visit that field; changed code placement is a possible
explanation for its timing change, not an established cause.

The earlier staging-buffer and direct integer-formatting experiments remain
rejected; see [OUTPUT_BUFFERS.md](OUTPUT_BUFFERS.md). Number formatting still
uses `itoa` and `zmij`.

The `simdutf8` 0.1.5 validator was rejected before timing. A standalone Miri
check of its safe compatibility API found an AVX2 prefetch computing a pointer
192 bytes into a 128-byte allocation. Native execution succeeded, but that
does not make the Rust pointer arithmetic valid. Scalar and SSE4.2 Miri
controls passed. No dependency or validation workaround was added.

A streaming guard returned immediately when the scanner reached a closing
quote. Builds from separate checkouts initially saved about 9% on short
streams, but several complete-document controls were slower. Rebuilding both
revisions in the same checkout with identical settings reduced the short-stream
gain to 1.9% and 3.1% in two comparisons. Small-object output, escaped-object
output and direct five-integer output took 3.8-4.8% more time. The guard failed
the stated 5% improvement and 3% control limits and was reverted. The
[experiment results](data/performance/quote-guard/) retain both comparisons;
they do not establish which compiler or layout difference caused the changes.

## Safety and compatibility

Grammar, UTF-8, integer-range, depth and ownership checks remain in place.
The new code contains six explicit `unsafe` calls to public CPython APIs:
two integer conversions, three streaming number constructors and one final
callback-output bytes copy. Python stays attached, input owners remain alive,
and constructor results are immediately checked for allocation failure.
No new code reads Python object layouts or retains raw pointers after a call.
The scanners use checked Rust slices.

The [memory-safety test description](../../../docs/memory-safety-testing.md)
names the invariants and limitations. Miri excludes the Python binding.
AddressSanitizer instruments the extension, not CPython itself. Constructor
failure branches also received source review; tests do not inject failure into
every constructor. The new 32-bit conversion fallback and Windows execution
were not tested on this host. Passing these tests does not prove equivalence
for every Python object or input.

## Checks

- `.agent/check.sh`: formatting, builds, Rust tests, Clippy, documentation and
  workflow syntax checks passed.
- `.agent/check-py.sh`: 983 Python tests passed and Python documentation was
  generated. pdoc reported three existing type-stub warnings.
- `test_output_buffers.py`: all 71 benchmark-fixture tests passed.
- Public orjson 3.11.9 suite: 1,626 passed, six skipped, four package-identity
  assertions excluded by the release-check runner.
- Miri: 200 selected Rust tests passed, with four skipped. Targeted lifetime
  checks also passed under both Miri reference models with three execution
  seeds each.
- AddressSanitizer: Python 3.9 passed 519 tests and skipped 106; Python 3.13
  passed 524 and skipped 101. These smaller environments omit optional
  dependencies. Address-space-limit tests run outside AddressSanitizer.

After reverting the last experiment, the Python checks passed again and the
rebuilt extension's SHA-256 matched the measured build. No runtime source
change remains after that measurement.

## Reproduce

Build both revisions in release mode with the same compiler settings and
interpreter. Install their wheels in separate directories. `BASELINE` and
`CANDIDATE` below name the directories containing each `jsonmodem` package,
not the source checkouts. Use a Python environment with the reference-library
and profiler versions listed above. Run commands from the repository root.

```bash
taskset -c 0 python crates/jsonmodem-py/benchmarks/bench_output_buffers.py \
  --baseline-package "$BASELINE" --candidate-package "$CANDIDATE" \
  --pairs 7 --seconds 0.04 --output output.json
```

The same arguments work with `bench_frontend.py`, `bench_numbers.py`,
`bench_strings.py` and `bench_stream_numbers.py`. Use a different output
filename for each script. `bench_utf8_inputs.py` uses the same arguments and
was run with `--seconds 0.06`.

The string-event benchmark instead takes two Python executables with the
respective wheels installed:

```bash
taskset -c 0 python crates/jsonmodem-py/benchmarks/bench_buffer_inputs.py \
  --baseline-python "$BASELINE_PYTHON" --candidate-python "$CANDIDATE_PYTHON" \
  --cases bytes byte_views_bytes byte_views_exporter \
  --string-length 4 --chunk-size 512 > stream-strings.json
```

For long strings, use `--string-length 256 --chunk-size 4096`. The script
finishes its timing before capturing allocations. Stop other builds, tests
and profilers before running any timing comparison.

Capture complete-document allocations separately:

```bash
PYTHONPATH="$CANDIDATE" PYTHONHASHSEED=1729 \
  python crates/jsonmodem-py/benchmarks/profile_compat.py \
  --module jsonmodem --workload dataclasses_1000 \
  --mode memray --calls 30 --output dataclasses.bin
```

Repeat with `--module orjson` and a new output filename. The helper also
accepts `--mode cprofile`; use 100 calls to reproduce the dataclass call
counts. Its `--mode loop --seconds 6 --calls 100` command can run under
`py-spy record --native --rate 49 --duration 8`. Use `--text-input` to profile
warmed Python strings rather than bytes for the float and U+2603 fixtures.

[Saved results](data/performance/) include every process-pair measurement and
the allocation and profile summaries. The JSON files name the source commits
and extension hashes for timing. Raw profiler recordings are excluded because
they contain machine-specific paths; the summaries retain source filenames
without those paths.
