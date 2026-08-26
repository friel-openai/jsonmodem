# Python performance results

This report compares the changes on top of [PR #1](https://github.com/friel-openai/jsonmodem/pull/1)
with PR #1 and orjson. Streaming measurements compare jsonmodem with its earlier
build and, for matching partial-document operations, jiter. orjson does not
provide an incremental parser; its results below are for complete documents.

The reference build is
[`d98fbe0`](https://github.com/friel-openai/jsonmodem/commit/d98fbe09bcd21a156fac0f8a60e8fe1119c79c4b).
The new runtime is
[`9285795`](https://github.com/friel-openai/jsonmodem/commit/9285795ca2ca10570e47a48564d29e12160c2d4d).
The later closing-quote experiment was reverted. The final runtime sources
and rebuilt extension match this measured revision exactly.

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

Each complete-document comparison starts seven pairs of processes, alternating
which build runs first. Each pair shares a Python hash seed; the seeds are
1729 through 1735. Each process checks results against orjson before timing,
then takes three measurements per library in alternating order. A measurement
times many calls with garbage collection disabled. Both libraries use the same
call count, calibrated until the slower library's batch takes at least 0.04
seconds. Input construction and process startup are excluded.

Tables report medians of the seven paired time ratios. A new/PR1 ratio of
0.75 means 25% less time; 1.10 means 10% more time. New/orjson ratios use
orjson measured in the same process. A ratio of 2 means twice orjson's time.
Ranges are observed minimum and maximum ratios, not confidence intervals.
All samples, including outliers and regressions, are retained in the result
files.

`bench_output_buffers.py` and `bench_frontend.py` call both libraries through
the same keyword-argument wrapper. `bench_numbers.py` and `bench_strings.py`
call the functions directly. The wrapper matters for tiny inputs; do not
compare absolute times across those two methods.

## Streaming results

[bench_stream_numbers.py](bench_stream_numbers.py) sends 1,024 numbers in
chunks that end at complete tokens, targeting 512 bytes per chunk. It consumes
every event or materializes every cumulative value snapshot. jiter receives
the same cumulative prefixes; its measurement includes building the contiguous
prefix that its API requires. Each snapshot's JSON representation is checked
before timing. Event results are compared only with PR #1 because jiter does
not produce jsonmodem's events.

| Number input | Events new/PR1 | Byte-view events new/PR1 | Snapshots new/PR1 | Snapshots new/jiter |
| --- | ---: | ---: | ---: | ---: |
| Small integers | 0.379 | 0.435 | 0.177 | 1.721 |
| Full-width signed integers | 0.417 | 0.473 | 0.163 | 0.559 |
| Upper-range unsigned integers | 0.434 | 0.478 | 0.184 | 0.549 |
| Floats | 0.356 | 0.421 | 0.107 | 1.109 |
| Mixed numeric types | 0.395 | 0.446 | 0.141 | 0.724 |
| 200-bit integers | 0.610 | 0.644 | 0.426 | 0.922 |

Unsigned snapshots take 2.111 ms per stream, versus jiter's 3.844 ms.
Small-integer snapshots still take 0.435 ms versus jiter's 0.252 ms.

[bench_buffer_inputs.py](bench_buffer_inputs.py) consumes all events from
1,024 strings. Short strings contain four bytes and use 512-byte chunks;
long strings contain 256 bytes and use 4,096-byte chunks. Each comparison
uses seven alternating process pairs, with three measurements of 200 streams
per process. These event comparisons do not set paired Python hash seeds.

| Event input | Short strings new/PR1 | Long strings new/PR1 |
| --- | ---: | ---: |
| Bytes | 1.110 | 0.930 |
| Bytes, byte-view events | 1.027 | 0.882 |
| Python `__buffer__` exporter, byte-view events | 1.013 | 0.894 |

The short-string bytes regression repeated at 1.093 times PR #1, with identical
allocation counts and event counts. The report retains both runs. Native
profiles did not identify a source change that explains the full regression;
the scanner and its search function account for about 4% of samples in both
builds. Long-string streaming improved, but short-string streaming did not.
These stream profiles use py-spy at 99 samples per second, requesting twelve
seconds while the workload loops run for ten. They contain 1,023 and 981
workload samples, with zero and one sampling errors respectively.

## Complete-document reference results

These seven inputs come from [bench_orjson_compat.py](bench_orjson_compat.py).
The mixed input has 1,000 four-field records. Numeric arrays have 10,000
elements; the integer array contains -5,000 through 4,999, and each float is
its index divided by seven. The string and escaped-object arrays have 1,000
elements. The long string has 143,360 UTF-8 bytes. Decoding uses `bytes` input
in this table.

| Input | Loads new/PR1 | Loads new/orjson | Dumps new/PR1 | Dumps new/orjson |
| --- | ---: | ---: | ---: | ---: |
| Small object | 0.961 | 1.144 | 0.991 | 1.488 |
| Mixed records | 0.908 | 1.538 | 0.977 | 1.840 |
| Short integers | 0.956 | 1.511 | 0.964 | 2.625 |
| Floats | 1.061 | 1.967 | 1.007 | 1.093 |
| Plain strings | 0.943 | 1.316 | 1.034 | 1.917 |
| Escaped objects | 0.880 | 1.734 | 0.861 | 2.153 |
| Long plain string | 0.968 | 0.243 | 0.648 | 1.184 |

Long-string decoding already beat orjson in PR #1. Here it takes 22.5
microseconds, versus PR #1's 23.2 and orjson's 93.8. Earlier runs in
[PROFILE.md](PROFILE.md) observed substantially different orjson long-string
times.

The output cases below use [bench_output_buffers.py](bench_output_buffers.py).
Full-width arrays contain 10,000 seeded random integers. The unsigned array
uses only `2**63` through `2**64 - 1`. Dataclass batches contain 1,000 records.
The eight- and sixteen-field cases have that many declared integer fields per
record. NumPy arrays have 25,000 rows of four consecutive whole numbers.

| Output | New/PR1 | New/orjson |
| --- | ---: | ---: |
| Full-width signed integers | 1.026 | 0.748 |
| Upper-range unsigned integers | 0.173 | 0.831 |
| One integer | 0.991 | 0.966 |
| Five integers | 1.000 | 1.171 |
| Indented short integers | 1.018 | 1.748 |
| Strict short integers | 0.950 | 2.607 |
| Sorted mixed records | 0.847 | 1.997 |
| Integer dictionary keys | 0.842 | 0.985 |
| Dataclass batch | 0.119 | 2.612 |
| One dataclass | 0.388 | 3.537 |
| One slotted dataclass | 0.554 | 2.401 |
| Slotted dataclass batch | 0.365 | 1.888 |
| Nested dataclasses | 0.060 | 2.671 |
| Indented dataclasses | 0.119 | 2.117 |
| Dataclasses with sorted dictionaries | 0.063 | 2.540 |
| Dataclasses with default callbacks | 0.059 | 2.104 |
| NumPy int64 | 0.996 | 0.691 |
| NumPy float32 | 0.998 | 0.858 |
| Default callback after 100 strings | 0.140 | 3.292 |
| Dataclasses with eight fields | 0.156 | 2.318 |
| Dataclasses with sixteen fields | 0.190 | 2.376 |

Upper-range unsigned output takes 0.278 ms, versus PR #1's 1.606 ms and
orjson's 0.332 ms. Dataclass output takes 0.205 ms, versus 1.737 ms and
0.082 ms. Several inputs still take more than twice orjson's time.
The signed-integer and NumPy advantages
over orjson already existed in PR #1.

The frontend comparison also covers bytearrays, bytes-backed memoryviews and
array-backed memoryviews. Small-object views take 0.803-0.807 times PR #1's
time. The raw results include Unicode, escaped keys, the 255/256-byte output
threshold, newline and indentation options. In particular, Unicode-escape
array decoding still takes 3.526 times orjson, and 600 unique escaped keys
take 3.861 times orjson.

Additional [numeric](data/performance/numbers.json) and
[string](data/performance/strings.json) results use direct calls. Integer
decoding takes 0.552 times PR #1 for upper-range unsigned values and 0.724
times for mixed integer widths. Escaped-string array decoding takes 0.700
times PR #1. These fixtures differ from the seven complete-document inputs;
their result files retain all cases and samples, and the scripts define the
inputs and options.

## Slower cases

Longer repeats use seven process pairs and a minimum batch duration of 0.06
seconds. Float decoding remains 5-7% slower than PR #1. A root string made
of 43,690 copies of U+2603 takes 14% more time from bytes. Plain-string array
output takes about 5% more time. Direct output calls also show increases of
about 4% for small objects, 5% for randomly distributed small integers and
6% for five-integer lists. The keyword-wrapper result for five integers is
unchanged; wrapper and direct-call measurements should not be combined.

[bench_utf8_inputs.py](bench_utf8_inputs.py) compares bytes with warmed Python
`str` input. The U+2603 fixture takes 1.138 times PR #1 from bytes and 0.963
times from `str`; float input takes 1.057 and 1.056 times respectively. The
initial equality check warms Python's cached UTF-8 representation. `str`
avoids the reader's initial byte validation, but it also changes ownership
and alignment. This comparison alone does not measure validation's exact cost.

## Allocation measurements

Memray 1.20.0 records native and Python allocations separately from timing.
Inputs are built before tracking. Each complete-document run performs ten
warmup calls and thirty measured calls, with garbage collection disabled.
Allocation events count allocation requests; allocated bytes count the total
requested across the run; peak live bytes count the most tracked memory held
at once. None of these measures is process RSS. The earlier
[RSS comparison](MEMORY.md) is separate and was not rerun here.

| Thirty calls | Library | Allocation requests | Total allocated bytes | Peak live bytes |
| --- | --- | ---: | ---: | ---: |
| 1,000 dataclasses | PR #1 | 1,435,961 | 82,287,958 | 64,085 |
| 1,000 dataclasses | New | 398 | 3,068,992 | 62,054 |
| 1,000 dataclasses | orjson | 188 | 1,941,892 | 33,137 |
| Upper-range unsigned output | PR #1 | 600,368 | 72,998,578 | 471,691 |
| Upper-range unsigned output | New | 368 | 21,998,578 | 471,691 |
| Upper-range unsigned output | orjson | 278 | 15,707,398 | 262,489 |
| Escaped-object input | PR #1 | 176,286 | 19,837,814 | 329,423 |
| Escaped-object input | New | 146,316 | 17,919,734 | 329,457 |
| Escaped-object input | orjson | 85,446 | 29,689,784 | 1,004,240 |
| Large escaped first string | PR #1 | 7,494,638 | 919,819,132 | 11,096,186 |
| Large escaped first string | New | 7,494,578 | 856,902,772 | 11,096,186 |
| Large escaped first string | orjson | 7,492,388 | 1,268,800,612 | 42,293,670 |
| NumPy float32 output | PR #1 | 1,512 | 98,214,220 | 2,293,685 |
| NumPy float32 output | New | 1,091 | 98,183,428 | 2,292,581 |
| NumPy float32 output | orjson | 750,968 | 232,185,802 | 4,074,161 |

The large-first-string input contains a 1 MiB escaped string followed by
250,000 integers. Its peak allocation is unchanged from PR #1, even though
the new decoder allocates fewer bytes across all calls. The dataclass and
unsigned-integer cases still allocate more bytes than orjson.

The string-event harness captures allocations separately over 100 streams
with garbage collection enabled. Short bytes input requests 2,921.46
allocations per stream in both builds. For long strings, byte-view events
request 5,820.07 versus PR #1's 5,885.07; the Python `__buffer__` exporter
requests 6,600.07 versus 6,730.07. These captures use a different call count
and garbage collection setting from the complete-document table, so their
peaks are not directly comparable.

## What the profiles show

For 100 calls writing 1,000 dataclasses, cProfile records 1,902,002 calls in
PR #1 and 102 in both the new build and orjson. Native traversal removes the
Python helper calls; cProfile does not count every native function call.

Complete-document native samples use py-spy 0.4.2 at 49 samples per second,
outside benchmark timing. Profiles request eight seconds while the measured
loop runs for six.
Only samples inside that loop are counted. CPython symbols are partly
stripped, so attribution uses source-qualified Rust frames. Inclusive sample
counts include called functions and can overlap.

For the U+2603 byte input, initial Rust UTF-8 validation appears in 143 of 272
new-build samples and 138 of 309 PR #1 samples. Python string construction
appears in 109 and 149 respectively. This identifies byte validation as a
candidate for improvement; the different sample shares are not direct timing
comparisons. Two attempts to profile warmed `str` input in the new build lost
most samples to unwinding errors and are excluded.

Float profiles include both `DocumentReader::number()` and Rust's decimal-to-
float conversion. The new reader also computes an integer prefix before
discarding it on finding a decimal point. That is extra executed work, but
these profiles do not establish how much of the float regression it explains.

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
