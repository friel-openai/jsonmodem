# Public baseline data

These files support [the public baseline report](../../PUBLIC_BASELINE.md).
They compare unchanged jsonmodem at
`b7fe329765f3e90064cc38f127d3594165116c71` with orjson 3.11.9 on CPython 3.12.13.
The jsonmodem package version is `0.0.0-alpha.0`; the commit and installed-file
hashes identify this build more precisely.

The label `baseline` in `repeated.json` and `jsonmodem_baseline` in the other
files identify the same build. `orjson_3119` means orjson 3.11.9 throughout.
Interpreter and library file hashes match across all three measurements.

## Files and units

- [repeated.json](repeated.json): eight interpreter processes per library, each
  measuring 36 document/operation cases with three timing samples. All 1,728
  samples are retained, including elapsed nanoseconds and calls per sample.
  Each sample can contain more than one call. `summary` reports median latency,
  throughput, and equal-case geometric means.
- [fresh-reused.json](fresh-reused.json): 648 single-call measurements, covering
  18 documents, two libraries, two input conditions, and nine process repeats.
  Fresh and reused conditions have separate summaries and geometric means.
- [memory.json](memory.json): 216 Memray captures and 216 separate RSS workers,
  covering 36 document/operation cases, two libraries, and three process repeats.
  It retains all allocation metrics and intermediate RSS readings. Raw Memray
  traces are not included.

Latency is in nanoseconds per call; lower is better. Throughput is decimal MB/s,
where 1 MB = 1,000,000 bytes; higher is better. Memory sizes are bytes and
allocation requests are counts; lower is better within the same metric.
The report converts latency to milliseconds and memory to MiB for readability.
Each latency geometric mean weights each unique document/operation case
equally. Fresh/reused means weight documents equally within each condition.
There is no memory geometric mean.

All files include fixture hashes, source URLs, library/interpreter fingerprints,
runner/helper hashes, complete-output verification results, and method details.
They contain no fixture documents or local execution paths. See
[the corpus sources and data terms](../../PUBLIC_CORPUS.md#data-terms).

## Repeated-call selection

The original timing session measured four builds. This export keeps only the
unchanged jsonmodem build and orjson. It discards no samples for those two
libraries. It is not a separate two-library rerun.

`runs[].library_order` lists only the selected libraries. The added
`runs[].source_library_positions` preserves each selected library's original
position, counting from one. The two omitted builds ran between some of the
reported workers. Document order, hash seeds, iteration counts, and samples are
unchanged.

`publication_selection` records the original result's SHA-256, selected labels,
sample count, and export generator hash. The published ratio reference is
orjson only. [select_repeated.py](select_repeated.py) verifies the original hash,
retains the selected measurements, recomputes summaries with the recorded
benchmark helper, and checks exact equality with the original selected
summaries. It also checks all 1,728 samples and rejects retained names from an
omitted build. The script does not run benchmarks.

`fresh-reused.json` and `memory.json` are byte-for-byte copies of their original
two-library results. None of the authoritative originals was changed.

## Method limits

Repeated-call timing includes releasing each returned result. The one-call
fresh/reused measurement stops before releasing the returned bytes. It uses a
different process schedule and CPU: repeated calls used CPU 12, while fresh/
reused and memory used CPU 8. Do not merge these timing families or attribute
their differences solely to UTF-8 caches. The recorded metadata does not include
a CPU model or clock settings.

The initial memory capture permitted concurrent builds and correctness checks;
individual overlapping jobs were not logged. Repeat memory measurements without
competing heavy work before interpreting small differences, especially RSS.
The separate fresh/reused timing run paused other workers' heavy jobs, without
claiming exclusive control of all host background processes.

Memray 1.20.0 tracks one call after ten warmups. Its live-byte peak excludes
preexisting input and warmup allocations. RSS workers make ten calls without
Memray or preliminary warmups. Whole-process peak RSS includes imports, input
preparation, returned values, and retained allocator pages. For every `otfcc`
dumps worker, input preparation had already set the final RSS peak before the
first library call. Those RSS values do not measure serializer-only memory.
No starting-RSS subtraction can reset the process high-water mark.

## Artifact hashes

The original repeated-call result contained the two omitted builds, so its hash
differs from `repeated.json`. The other published artifact hashes are also their
original hashes. The JSON files retain the original measurement source hashes;
the selection metadata separately identifies the generator and summary helper.

<details>
<summary>SHA-256 values</summary>

```text
Original four-build repeated-call result
df9c917b8852d86f48aa17c197f16692c97673fe3e3e85be45a26343988fa644
Published repeated.json
6174d1e24eed3fb2ebe7bd774fcebf88a4a9f8b5c874c21aa2d2ff7bf7f6afe8
Original and published fresh-reused.json
e0e2a5a7242e497378399411aa6d53cc507a61baf806d48b11e4627974911ff8
Original and published memory.json
801dd9c76c66add5f7107f4c9f5df783d91cbc8861d6766fd17a8c27b64ef60a
select_repeated.py
1447cb9815aee374ade1f1344d1720dfa852b2eab63784d609414091d73b8bb2
```

</details>
