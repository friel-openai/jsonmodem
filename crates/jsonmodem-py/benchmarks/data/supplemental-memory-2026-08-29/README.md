# Additional memory data

These files support [the additional memory report](../../PUBLIC_SUPPLEMENTAL_MEMORY.md).
They compare unchanged jsonmodem at
`b7fe329765f3e90064cc38f127d3594165116c71` with orjson 3.11.9. Measurements used
CPython 3.12.13, Memray 1.20.0, and NumPy 2.5.2 on Linux x86_64.

All eleven JSON files are byte-for-byte copies of the recorded portable
artifacts. No samples or fingerprints were removed, and no authoritative
original was changed. [SHA256SUMS](SHA256SUMS) lists their original and copied
SHA-256 values. No trace binaries, fixture documents, or actual local execution
locations are included.

## Files

- [supplemental-memory-summary.json](supplemental-memory-summary.json) contains
  normalized medians and all synthetic process samples, capture hashes,
  library/interpreter/dependency fingerprints, source hashes, and the separate
  zero/ten-warmup public comparison. Sizes are bytes and requests are counts.
  Both synthetic and public measurements use the labels `jsonmodem_baseline`
  and `orjson_3119` here.
- `jsonmodem-1.json`, `jsonmodem-2.json`, and `jsonmodem-3.json` are the original
  allocation-driver results for the three jsonmodem processes. The matching
  `orjson-1.json`, `orjson-2.json`, and `orjson-3.json` files contain orjson's
  results. Each process captured all fourteen workloads once. The original
  `allocation_events` field counts allocation requests; `allocated_bytes` is
  cumulative requested bytes and `peak_live_bytes` is the tracked live peak.
- [rss.json](rss.json) retains all 42 RSS worker records, including startup,
  prepared-input, first-call, and final readings. These original fields use KiB,
  as their names state. The normalized summary converts them to bytes without
  losing any reading.
- [memory-first-use.json](memory-first-use.json) is the public-document runner's
  complete output for 18 zero-warmup captures: three documents, two libraries,
  and three fresh-process repeats. It includes every capture's metrics and
  hash, fixture fingerprints, source URLs, and correctness results.
- [preflight-before.json](preflight-before.json) and
  [preflight-after.json](preflight-after.json) record complete-output checks
  and fingerprints before and after the measurement command. Their data agree
  apart from completion timestamps.

The preflights reuse the actual synthetic workload constructors with checked
library calls. They skip allocation warmups and replace tracking because they
check correctness only; `measurements_collected` is false. None of their
placeholder memory values enters the results. Real captures run the unchanged
drivers in separate processes. Dumps outputs matched orjson byte-for-byte;
loads matched standard-library values, types, float bits, and dictionary order.
All 102 saved allocation traces were later recomputed with the shared
allocation-kind filter and matched the recorded metrics and hashes.

The earlier warmed public comparison is already available in
[the baseline memory data](../public-baseline-2026-08-29/memory.json), SHA-256
`801dd9c76c66add5f7107f4c9f5df783d91cbc8861d6766fd17a8c27b64ef60a`.
The `ten_warmups` entries in the supplemental summary preserve its matching
three-process metrics; the full original result is not duplicated here.

## Measurement limits

Synthetic allocations use three fresh processes per library. Each process
prepares all fourteen workloads, then captures them sequentially. Each capture
tracks one call after ten warmups, with cyclic GC collected after warmups and
left enabled. Result release is included; input preparation and preexisting
allocations are not. Python allocator tracing is enabled, native stacks are
disabled, and all captures use the full allocation format.

RSS uses 42 separate workers, each making ten calls without Memray or preliminary
warmups. GC is collected after preparation and remains enabled. Results are
released before readings. The process high-water mark includes imports, input
preparation, calls, and allocator retention. Preparation set the final peak for
both libraries' fragment and dataclass workers and for orjson's medium dumps.

The first-use public captures use zero warmups and one tracked call. They disable
cyclic GC after input preparation and release the output within the capture.
They can include first-call library initialization and string allocations; they
do not isolate UTF-8 caches. The earlier ten-warmup comparison permitted
concurrent builds and correctness checks. In this supplemental capture, other
workers' heavy jobs were paused. That coordination does not guarantee an idle
host or remove the different process histories.

There is no combined memory score. Compare the same metric, library version,
and workload, retaining these method differences. The report gives commands for
the existing drivers; no new measurement framework is required.
