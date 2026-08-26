# Complete-document buffer comparisons

`loads()` accepts C-contiguous memoryviews from native providers. It copies
their bytes before decoding, so releasing or changing the view during later
Python allocations cannot invalidate the parser's input. The provider must
keep the original storage valid until copying finishes.

These measurements compare complete-document decoding with orjson. They do
not measure jsonmodem's incremental parsing. The tested implementation is
[`dcf9bc1`](https://github.com/friel-openai/jsonmodem/commit/dcf9bc1eddb13adc4de7b8136aef96a7d926e893),
built in release mode. Tests ran on 2026-08-26 with CPython 3.12.13,
orjson 3.11.9, Memray 1.20.0, and an AMD EPYC 7763, using CPU 0.

## Time

The benchmark constructs each input before timing. Both libraries receive the
same input and call count. It increases the call count until the slower
library's batch takes at least 0.1 seconds. Each measurement times a batch,
then divides by the number of calls. The libraries alternate running first.
Garbage collection is disabled during timing, and allocation profiling runs
separately. Decoded values must match before timing starts.

Each table entry is jsonmodem's time divided by orjson's time: 1.65 means
jsonmodem took 65% longer; 0.58 means it took 42% less time. Each run reports
the median of its measurement ratios. The first run measured each library
11 times; the next two measured each 15 times. The first run preceded the
decode-diagnostic changes in `dcf9bc1`; all runs include the memoryview fix.

| Input | Storage | First run | Second run | Third run |
| --- | --- | ---: | ---: | ---: |
| small | bytes | 1.19 | 1.18 | 1.17 |
| small | bytearray | 1.22 | 1.22 | 1.23 |
| small | bytes-backed memoryview | 1.62 | 1.66 | 1.63 |
| small | array-backed memoryview | 1.61 | 1.57 | 1.65 |
| medium | bytes | 1.71 | 1.60 | 1.75 |
| medium | bytearray | 1.73 | 1.60 | 1.70 |
| medium | bytes-backed memoryview | 1.69 | 1.61 | 1.72 |
| medium | array-backed memoryview | 1.71 | 1.86 | 1.78 |
| long string | bytes | 0.51 | 0.25 | 0.24 |
| long string | bytearray | 0.58 | 0.57 | 0.56 |
| long string | bytes-backed memoryview | 0.58 | 0.31 | 0.30 |
| long string | array-backed memoryview | 0.60 | 0.58 | 0.58 |

The small input is a 59-byte object. The medium input contains 1,000 objects
with `id`, `score`, `active`, and `name` fields, totaling 68,160 bytes. The long
string contains repeated ASCII text and occupies 143,362 bytes including quotes.
Array-backed views use `array.array("B", document)`.

Absolute timings varied between runs. In the third run, long-string bytes
took 22,901 ns for jsonmodem and 93,650 ns for orjson; orjson took 46,076 ns
in the first run. The third run was added to check this variation. All three
runs are retained above, and the cause was not established. Do not interpret
the lowest ratios as a new optimization or a general speed guarantee.

For array-backed views, the third run measured 739 ns versus 450 ns on the
small input and 499,176 ns versus 245,393 ns on the medium input. Individual
median times need not divide to the reported median ratio, because the ratio
is calculated within each pair before taking the median.

A separate check of the original small/medium workloads, with 15 measurements
per library, found these ratios:

| Input | loads from bytes | dumps |
| --- | ---: | ---: |
| small | 1.17 | 1.85 |
| medium | 1.69 | 1.89 |

These results stay below twice orjson's time. Other workloads remain slower;
see the [earlier results](../../../plans/orjson-speedups/record.md).

Run from the repository root after building the extension in release mode:

```sh
python crates/jsonmodem-py/benchmarks/bench_orjson_compat.py \
  --workloads small medium long_string --operations loads \
  --loads-inputs bytes bytearray memoryview array_view \
  --rounds 15 --seconds 0.1 --output /tmp/buffer-times.json
python crates/jsonmodem-py/benchmarks/bench_orjson_compat.py \
  --workloads small medium --rounds 15 --seconds 0.1 \
  --output /tmp/ordinary-times.json
```

## Allocations and peak memory

Memray tracked 30 calls after ten unmeasured calls. Inputs were constructed
before tracking, and outputs were discarded. An event is a request for memory.
Total bytes adds all those requests; peak bytes is the most tracked memory
held at once. Counts include allocations by the benchmark loop. These are not
whole-process RSS measurements.

Each cell below lists **jsonmodem / orjson**. The medium allocation workload
omits `active`, preserving the existing allocation benchmark: 53,494 input
bytes rather than the timing benchmark's 68,160. Each library receives the
same input within a comparison.

| Input | Events over 30 calls | Total bytes over 30 calls | Peak bytes |
| --- | ---: | ---: | ---: |
| small bytes | 247 / 247 | 9,988 / 131,128 | 330 / 4,336 |
| small array view | 337 / 247 | 15,778 / 131,128 | 2,508 / 4,336 |
| medium bytes | 135,842 / 134,943 | 10,014,842 / 27,372,062 | 289,852 / 928,870 |
| medium array view | 135,932 / 134,943 | 11,623,682 / 27,372,062 | 345,508 / 928,870 |
| long-string bytes | 97 / 127 | 4,304,278 / 56,036,758 | 143,473 / 1,867,857 |
| long-string array view | 187 / 127 | 8,609,158 / 56,036,758 | 289,813 / 1,867,857 |

Accepting native views is not free: jsonmodem makes three more allocation
requests per call than it does for bytes, including a copy of the input.
Its peak remains below orjson's for these cases, but it makes more allocation
requests for every array-view case. Neither result establishes lower memory
use for every workload. See [MEMORY.md](MEMORY.md) for other workloads and
separately labeled earlier RSS results.

Repeat each workload with both modules, using a new output filename each time:

```sh
python crates/jsonmodem-py/benchmarks/bench_allocations.py \
  --module jsonmodem --calls 30 --workload loads_medium_array_view \
  --output /tmp/jsonmodem-medium-view.json
python crates/jsonmodem-py/benchmarks/bench_allocations.py \
  --module orjson --calls 30 --workload loads_medium_array_view \
  --output /tmp/orjson-medium-view.json
```

The other names are `loads_small`, `loads_medium`, `loads_long_string`,
`loads_small_array_view`, and `loads_long_string_array_view`.
