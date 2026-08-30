# Complete-load error handling

`bench_rejections.py` compares the time and allocations required to reject
bytes passed to `loads()`. Catching and releasing each `JSONDecodeError` is
included. Use these results separately from the [valid-document benchmarks](PUBLIC_CORPUS.md).
This document describes the method; it does not report measured results.

The intended control is orjson 3.11.9. Each configured library must reject every
selected input before measurement starts. An accepted input, another exception
type, a changed fingerprint, or a worker timeout fails the comparison.

## Inputs

The inputs are generic examples constructed from [RFC 8259](https://www.rfc-editor.org/info/rfc8259/).
Sections 2 and 7 define the single-value and string syntax; section 8.1 describes
UTF-8 encoding. Sections 6 and 9 allow number-range and nesting limits.
Numeric overflow and excessive nesting are therefore listed separately from
syntax errors. No corpus download is needed.

| Family | Input and reason for rejection |
|---|---|
| `syntax_early` | An array of repeated `{"k":0}` objects, with its initial `[` replaced by `!`. |
| `syntax_late` | The same array, with its final `]` replaced by `}`. |
| `unfinished_string` | An opening quote and ASCII `a` bytes, without a closing quote. |
| `unfinished_escape` | An opening quote, ASCII `a` bytes, and a backslash at the end of the input. |
| `unfinished_unicode_escape` | An opening quote, ASCII `a` bytes, and an incomplete `\u12` escape. |
| `utf8_early` | A quoted string with an invalid `0xff` byte immediately after the opening quote. |
| `utf8_late` | The same valid string contents, with the invalid byte before the closing quote. |
| `number_overflow` | Repeated `9` digits followed by `e400`: valid syntax outside finite binary64 range. |
| `trailing_input` | A valid object array followed by another root value, `0`, at the final byte. |
| `depth_limit` | An array nested beyond the libraries' accepted depth limit. |

The first nine families use inputs of 64 bytes, 4 KiB, 64 KiB, and 1 MiB.
Arrays are padded with trailing spaces to reach the exact size. The UTF-8
cases use valid three-byte snowman characters and ASCII padding around the
single invalid byte.

The depth cases have 1,025, 8,192, and 524,288 arrays around `0`. Their input
sizes are 2,051 bytes, 16,385 bytes, and 1,048,577 bytes. There are **39 default
cases**. Configurable byte sizes are limited to 64 through 1,048,576; depths are
limited to 1,025 through 524,288. The maximum input is about 1 MiB.

These cases test error position and size-dependent cost. They do not estimate
how often an application encounters each error, and they are not a security
proof. A parser can scan or copy more of an input than its error position
suggests, for example while validating UTF-8 or constructing an exception.

## What is measured

Both metrics call the same wrapper. It calls `loads()`, catches only the
library's `JSONDecodeError`, and returns `None`. No exception is retained
between calls. Catching and releasing the exception includes its traceback
and any source string owned by the exception. The wrapper does not inspect
the error message, source string, or position during measurement.

Correctness checks run in separate processes before any measurement. Each
measurement then uses a fresh interpreter for one library, input, metric,
and repeat. Inputs are generated and SHA-256 checked outside measurement.
Each worker retains only its selected byte input, with no reference object
tree. Libraries alternate order across repeats; input order is shuffled with
a recorded deterministic seed. Python hash seeds match within each repeat.

**Lower is better** for each reported metric. Do not compare different metrics
to one another:

- **Latency:** nanoseconds per rejected call, including exception handling.
  The existing `bench_public_corpus.measure` helper uses three warmup calls,
  calibration, and three timed samples per process. Each sample targets 30 ms.
  Warmups and calibration are excluded. Memray is not imported in these workers.
- **Allocation requests:** allocation-kind records counted by the existing
  `bench_public_memory.measure_memray` and `allocation_stats` helpers.
  Zero-byte allocation requests count; deallocation records do not.
- **Total allocated bytes:** the sum of requested allocation sizes. A
  reallocation counts its full requested new size.
- **Peak live bytes:** Memray's maximum tracked live allocation size. This is
  not whole-process RSS, and the peak is not divided by the number of calls.

The allocation defaults are Memray 1.20.0, ten untracked warmup calls, and one
tracked call. Python allocator tracing is enabled; native stacks are disabled.
Input preparation, imports, warmups, and capture analysis are excluded.
Preexisting live allocations are not counted. This is a warmed measurement,
not a first-use allocation result.

Both helpers collect and disable cyclic GC before warmups and restore its
previous state afterward. CPython releases these exceptions through reference
counting. The test for exception release runs with cyclic GC disabled; delayed
collection of reference cycles is outside this measurement.

The output preserves every timed sample, call count, allocation result, and
process repeat. Summaries are per-input medians across processes; latency uses
the median of each process's sample median. There is **no geomean or parsed-byte
throughput** for this suite: early rejection need not parse the whole input.
Keep these results out of valid-document aggregate scores.

## Run

Use the same library configuration format as the [public corpus runner](PUBLIC_CORPUS.md).
For an environment containing both packages, a minimal `libraries.json` is:

```json
{
  "libraries": [
    {
      "name": "jsonmodem_baseline",
      "module": "jsonmodem",
      "expected_version": "0.0.0-alpha.0"
    },
    {
      "name": "orjson_3119",
      "module": "orjson",
      "expected_version": "3.11.9"
    }
  ]
}
```

Optional `python` and `pythonpath` fields select other prepared builds. A
relative filename is resolved against the configuration file's directory.
The version is checked, and the result records interpreter and imported
library file hashes. An optional `revision` must be a full Git commit ID.

From the repository root, first run a smaller comparison of all ten families:

```bash
BENCH_ARTIFACTS=$(mktemp -d)
python crates/jsonmodem-py/benchmarks/bench_rejections.py run \
  --libraries libraries.json --cpu 8 \
  --sizes 64 --depths 1025 --repeats 1 \
  --profiles "$BENCH_ARTIFACTS/profiles" \
  --output "$BENCH_ARTIFACTS/small.json"
```

The smaller run uses 40 measurement processes and two correctness processes
for two libraries. Select an available CPU on the machine being measured.
Omit `--cpu` if the operating system does not support CPU affinity.

For all 39 cases with three process repeats:

```bash
python crates/jsonmodem-py/benchmarks/bench_rejections.py run \
  --libraries libraries.json --cpu 8 \
  --profiles "$BENCH_ARTIFACTS/profiles" \
  --output "$BENCH_ARTIFACTS/full.json"
```

The default two-library run uses 468 measurement processes and two correctness
processes, producing 234 Memray captures. Keep other CPU-heavy jobs paused
during comparison. Use `--cases` to select families, `--sizes` for non-depth
inputs, and `--depths` for the depth family. `--metrics latency` avoids Memray
entirely and does not require `--profiles`.

`--latency-warmups`, `--samples`, and `--seconds` configure latency.
`--memray-warmups`, `--memray-calls`, and `--memray-version` configure allocations.
The default timeout is 120 seconds per worker; `--timeout` changes it. A failed
worker stops the run without writing a result document. Existing output files
are not replaced.

The result includes input, driver, helper, interpreter, library, and Memray
package hashes. The Memray version and files are checked in preflight as well.
Worker source and library fingerprints must match before and after measurement.
Local build directories do not enter result JSON. Capture filenames, sizes,
and hashes are retained, but raw Memray captures can contain local filenames;
keep them outside the checkout and do not publish them with result data.

The focused checks are:

```bash
python -m pytest crates/jsonmodem-py/tests/test_rejections.py
```

They cover input definitions and bounds, rejection by installed libraries,
exception release, unexpected acceptance or exceptions, helper reuse, process
ordering, changed fingerprints, and portable result data.
