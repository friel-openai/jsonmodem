# First serialization and reused inputs

`bench_public_fresh_dumps.py` compares a single `dumps()` call on newly prepared
Python values with a call on values the library has already serialized. Both
conditions use a warmed library and the same document. This is a separate
complete-document measurement; it does not change the
[repeated-call benchmark](PUBLIC_CORPUS.md) or measure incremental parsing.

CPython can store a UTF-8 representation inside a Unicode object for later use.
Repeated calls on the same strings can therefore avoid work required on first
use. See the [CPython Unicode C API](https://docs.python.org/3.12/c-api/unicode.html#c.PyUnicode_AsUTF8AndSize).
This benchmark measures the difference between newly prepared and reused
objects. It does not isolate UTF-8 caching: allocator state, processor caches,
and interpreter-shared objects can also affect the result. Fresh means another
standard-library parse, not a guarantee that every object or cache is new.

## What each process does

Each library, document, condition, and repeat runs in a fresh interpreter
process. Workers require CPython because the protocol uses reference counting
to release the warmup input before preparing a replacement. Each worker reads
and verifies the original document bytes, then uses standard-library `json.loads`
to prepare Python values independently of the measured library.

The two conditions are:

1. **Fresh input:** prepare a value and serialize it ten times without timing.
   Release each returned value before the next call. Release the prepared input
   before parsing the document again. Time the replacement input's first
   serialization.
2. **Reused input:** prepare a value and serialize it ten times without timing.
   Release each returned value before the next call. Time one more serialization
   of that same input.

Only one parsed copy of the document exists when the stopwatch starts. The
worker retains the original bytes for preparation, but no reference Python
value or reference encoded output. It does not copy a warmed value, inherit
prepared values from a fork, run a calibration loop, or call `dumps()` on the
fresh timed input before the stopwatch starts.

The timed call retains its returned bytes until the clock stops. The worker then
checks their exact length and SHA-256 against the separate correctness check,
and releases them. **Returned-byte destruction is excluded.** The repeated-call
benchmark includes destruction, so its results and geometric means are not
interchangeable with this measurement.

Cyclic garbage collection runs once after the initial input preparation and is
disabled before warmups. There is no collection between warmups and the timed
call. The worker restores the previous GC state afterward. Reference-counted
destruction still releases warmup inputs and outputs outside timing.

`--warmups` changes the number of untimed calls; the default is ten. With zero
warmups, neither condition prepares a throwaway input. Both prepare once and
time the first call. This provides a control for the two procedures.

## Run a comparison

Use the same verified fixture directory and local library configuration as
[the public-corpus runner](PUBLIC_CORPUS.md#run-a-comparison). No new dependency
or native code is required. Run from the repository root with CPython 3.9 or
newer and the configured libraries installed.

Start with a numeric document and two documents containing non-ASCII strings:

```bash
python crates/jsonmodem-py/benchmarks/bench_public_fresh_dumps.py run \
  --directory /tmp/jsonmodem-public-corpus --libraries libraries.json \
  --reference orjson_3120 --reference orjson_3119 \
  --cases numbers poet twitterescaped --cpu 0 \
  --repeats 3 --warmups 10 --output fresh-dumps-check.json
```

Reference labels must match builds in `libraries.json`; use only the versions
actually installed. Each reference version receives a separate comparison.
Omit `--cases` and use `--repeats 9` for all 18 selected documents. With two
libraries and both conditions, that full run uses 648 timed worker processes,
plus separate correctness processes. `--conditions fresh` or
`--conditions reused` selects just one condition.

Choose an available CPU. `--cpu` requires OS affinity support and can be omitted
elsewhere. Stop competing heavy work for final measurements; CPU affinity alone
does not isolate memory bandwidth, processor caches, or power limits.
`--timeout` limits each worker and defaults to 600 seconds. No downloads, disk
reads, input preparation, hashes, warmups, or output verification are timed.

Before measurement, every build must pass the existing complete-value checks:
exact types, float bits including signed zero, dictionary order, unchanged
input, and identical encoded outputs. The timed workers check the actual timed
output afterward; checking it before the call would warm the fresh input.
The runner rejects changed fixture bytes, runner code, imported library files,
versions, or interpreter fingerprints. A failed run does not replace an
existing output file.

Library order rotates across repeats. Condition order reverses after each group
of N repeats, where N is the number of libraries. With two libraries, fresh runs
first for two repeats, then reused runs first for two repeats. This prevents
library and condition order from always reversing together. Document order is
shuffled deterministically.
Every worker within a repeat uses the same Python hash seed. All orders and
hash seeds are recorded.

## Read the results

**Latency: lower is better.**
`summary.cases["dumps:poet"].conditions.fresh.measurements["jsonmodem"].latency_ns`
is the median of the single-call process latencies. The corresponding `reused`
entry measures the reused-input control. Every process latency and its minimum
and maximum remain in the JSON. These ranges are not confidence intervals.
Python call and stopwatch overhead are included; clock implementation and
resolution are recorded. One short call per process can be noisy, so inspect
the repeated values before interpreting small differences.

**Throughput: higher is better.** `throughput_MB_s` uses encoded output bytes and
decimal megabytes: 1 MB = 1,000,000 bytes. It does not use the size of the original
indented document. Input/output sizes and hashes accompany each case.

**Geometric-mean latency ratio: lower is better.** For each condition, divide
the library's median latency for each document by the reference's median.
Take the geometric mean with one equal weight per unique document. A ratio of
1 means equal latency. `summary.geomeans.fresh` and
`summary.geomeans.reused` are separate, as are different reference libraries.
There is no combined-condition score. Do not mix these values into the existing
loads/dumps or synthetic-suite aggregates.

Identical encoded outputs are deduplicated after full correctness checks.
`duplicate_cases` lists omitted copies. The JSON contains measurements, output
checks, source and build hashes, clock information, and portable environment
metadata. It does not contain fixture contents or local interpreter/package
paths. Input preparation counts, warmup counts, the one timed call, and the
exclusion of returned-byte destruction are explicit in each worker result.

These results are not memory measurements. Use the separate
[Memray and RSS runner](PUBLIC_MEMORY.md) for allocation and process-memory
comparisons.

## Tests

The offline tests use pytest and generated local adapters. They do not download
corpus data or require jsonmodem or orjson:

```bash
python -m pytest -q crates/jsonmodem-py/tests/test_public_fresh_dumps.py
```

Tests observe input destruction before replacement, one live input at the
stopwatch, the exact call counts, output survival until verification, GC state
on success and failure, and identical procedures with zero warmups. They also
check independent order rotation, output and fingerprint mismatches, duplicate
weighting, separate condition summaries, and portable subprocess results.
