# Public-corpus memory comparisons

`bench_public_memory.py` measures complete Python `loads()` and `dumps()` on the
same pinned documents as the [public-corpus timing runner](PUBLIC_CORPUS.md).
These are complete-document reference measurements, not incremental parsing
benchmarks.

Two separate measurements answer different questions:

- **Memray:** how many allocation requests and bytes are recorded during the
  selected calls, and what is the peak live size of those tracked allocations?
- **RSS:** how much resident memory does a fresh process use, including its
  interpreter, imports, prepared input, results, and retained allocator pages?

**Lower is better for each reported memory metric.** Do not compare tracked
peak bytes to peak RSS as if they measured the same quantity. Memray explains
why [heap allocations and RSS differ](https://bloomberg.github.io/memray/memory.html).

## Run a comparison

Fetch the documents and create `libraries.json` as described in
[PUBLIC_CORPUS.md](PUBLIC_CORPUS.md). The same file selects interpreter builds,
package directories, exact expected library versions, and reference labels.
Memray must be installed in each configured interpreter used for allocation
measurements. All workers must use the same Memray version; the runner rejects
version differences. `--memray-version` can require a specific version.

Start with a small subset:

```bash
python crates/jsonmodem-py/benchmarks/bench_public_memory.py run \
  --directory /tmp/jsonmodem-public-corpus --libraries libraries.json \
  --reference orjson_3120 --reference orjson_3119 \
  --cases github_events numbers twitter --cpu 0 \
  --profiles /tmp/jsonmodem-memory-captures --output corpus-memory.json
```

Choose an available CPU. Omit `--cpu` if affinity is unavailable. Stop competing
heavy work before recording results; affinity alone does not isolate memory
bandwidth or the allocator from other work. `--operations loads` or
`--operations dumps` selects one operation. Omit `--cases` to use all documents.

Defaults are three fresh-process repeats, ten Memray warmup calls followed by
one tracked call, and ten RSS calls with no warmup. The one-call Memray default
keeps full captures manageable for the 66 MB font document. Capture storage can
be much larger than the input JSON. For thirty tracked calls on smaller cases:

```bash
python crates/jsonmodem-py/benchmarks/bench_public_memory.py run \
  --directory /tmp/jsonmodem-public-corpus --libraries libraries.json \
  --reference orjson_3120 --cases github_events numbers \
  --calls 30 --warmups 10 --rss-calls 10 --repeats 3 \
  --profiles /tmp/jsonmodem-memory-captures --output corpus-memory-30-calls.json
```

Use `--metrics rss` for RSS only, without Memray or `--profiles`. RSS requires
Linux `/proc/self/status`. Use `--metrics memray` for allocation tracking only.
`--warmups 0` tracks the first library call after import and input preparation;
it does not promise a cold interpreter or cold OS caches. `--rss-calls` is
independent of `--calls`. `--timeout` limits one worker to 600 seconds by default.

## What is measured

Each library, document, operation, metric, and repeat gets a fresh worker
process. Correctness is checked first, in separate processes. The checks compare
complete values, exact Python types, float bits including signed zero, dictionary
order, and encoded bytes. No reference output remains in the memory worker.

For `loads`, the worker retains only the verified original bytes. For `dumps`,
the worker prepares one Python input with the standard-library JSON decoder and
releases the original bytes. It imports only the library being measured.
Module and interpreter fingerprints are computed after the memory readings,
then compared with fingerprints from the correctness checks. File hashing cannot
raise the reported RSS peak.

The worker collects cyclic garbage and disables cyclic GC before its calls.
Memray warmups happen after that collection, with no second collection that
would clear warmed Python free lists. Every returned value is explicitly
released before the next call. For RSS, the first result is held only long
enough to record its resident-memory reading. GC's previous state is restored
afterward. Reference-counted result destruction is part of both measurements.

### Tracked allocations

Memray uses `trace_python_allocators=True`, `native_traces=False`, and
`ALL_ALLOCATIONS`. Python allocator tracing records small Python allocations
even when Python has already reserved enough memory to satisfy them.
[Memray documents this distinction](https://bloomberg.github.io/memray/python_allocators.html).

The result contains three absolute metrics:

- `allocation_requests`: the number of recorded allocation-kind requests,
  including zero-byte requests. Deallocation records do not count.
- `total_allocated_bytes`: the sum of those requests' sizes. A reallocation
  counts its full requested new size, not just its growth. This is cumulative
  requested storage, not the amount retained at the end.
- `peak_live_bytes`: the largest total size of tracked allocations still live
  at any one point during recording. Do not divide this peak by the call count.

Imports, input preparation, warmups, and capture analysis are outside recording.
Allocations already live when recording starts are not in the trace unless a
new allocation or reallocation is recorded for them. The benchmark loop, calls,
and returned-value destruction are inside recording. Request counts are not
counts of distinct Python objects or resident pages.

Use full captures: aggregated captures retain information about peaks and leaks,
but cannot recover every allocation request or total allocated byte.
[Memray's API documentation](https://bloomberg.github.io/memray/api.html)
describes the difference. The shared `allocation_stats.py` helper rejects
aggregated captures and unknown allocator kinds rather than guessing.

### Process RSS

An RSS worker never imports Memray and makes no warmup calls. It records:

1. Startup, before importing the measured library.
2. Prepared input, just before the first call.
3. The first returned value while still alive.
4. After releasing that first result.
5. After all remaining calls and result destruction.

Each reading contains current `VmRSS`, peak `VmHWM`, and
`getrusage(RUSAGE_SELF).ru_maxrss`, all converted from Linux KiB to bytes.
The headline `peak_rss_bytes` is the final `VmHWM`. `prepared_rss_bytes` and
`first_result_rss_bytes` expose two current-RSS readings; all readings remain in
the result JSON. Fingerprinting and result formatting happen after the final
reading. The small cost of taking the readings is included.

RSS includes input preparation. In particular, standard-library preparation for
`dumps` can set the highest reading before the serializer is called. Releasing
the original bytes does not reset a high-water mark or necessarily return pages
to the OS. Neither `VmHWM` nor `ru_maxrss` is an operation-only peak. Subtracting
a pre-call reading does not change that. A flat peak does not mean a call
allocated nothing.

## Results and saved captures

`summary.cases.<case>.memray.measurements.<library>` contains medians for the
three allocation metrics. The corresponding `rss` entry contains median peak
RSS, prepared-input RSS, and first-result RSS. Every process value is retained
in `process_samples`, with full capture metadata and RSS readings in `runs`.
Per-reference ratios are secondary fields: each library's median divided by
the labeled reference's median. A zero reference produces `null`, not infinity.
There is no overall memory geometric mean or instrumented latency.

The runner alternates or rotates library order and shuffles document order
deterministically between repeats. It records those orders and Python hash
seeds. Duplicate document and encoding-output rules are the same as for timing.
Build versions, imported-file hashes, interpreter hashes, capture flags, and
the Memray version identify each configuration.

Result JSON contains metadata and measurements, not fixture contents or local
build paths. It is written atomically only after every requested worker succeeds.
Raw captures are kept in a new subdirectory under `--profiles`; the directory
is printed to stderr. Each result names and hashes its capture. Raw Memray
captures can contain local file paths and profiler metadata. Do not publish
them with the portable comparison JSON.

### Older allocation reports

`bench_allocations.py`, `bench_numbers.py`, `profile_compat.py`, and
`bench_sorted_storage.py` now use `allocation_stats.py` for counts. They retain
their existing output names, `allocation_events` and `allocated_bytes`.
Earlier versions counted every positive-size record, which could include
`MUNMAP` deallocations and omit zero-byte allocation requests. Their old reports
have not been rewritten. Recompute from a retained full capture before claiming
that any historical result was affected.

## Tests

```bash
python -m pytest -q crates/jsonmodem-py/tests/test_public_corpus.py \
  crates/jsonmodem-py/tests/test_public_memory.py \
  crates/jsonmodem-py/tests/test_allocation_stats.py
```

Tests use local generated fixtures, not downloads. They check source verification,
input preparation, result destruction, GC restoration, capture boundaries,
profiler-version checks, allocator classifications, byte units, duplicate cases,
and portable results. The RSS integration test runs without importing Memray.
When Memray is installed, a small native `mmap` capture also checks deallocation
filtering and agreement between its peak metadata and high-watermark records.
