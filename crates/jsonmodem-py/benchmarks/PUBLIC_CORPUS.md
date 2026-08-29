# Public JSON corpus benchmarks

`bench_public_corpus.py` compares complete Python `loads()` and `dumps()` on
18 documents already published in JSON parser benchmark collections. It checks
correctness before timing and records absolute latency, throughput, repeated
measurements, and geometric means. It does not measure incremental parsing.

## Documents and sources

The selection was fixed before comparing jsonmodem with orjson. It includes
the Canada, CITM, and Twitter documents used by
[nativejson-benchmark](https://github.com/miloyip/nativejson-benchmark/blob/478d5727c2a4048e835a29c65adecc7d795360d5/README.md),
[serde-rs/json-benchmark](https://github.com/serde-rs/json-benchmark/blob/17b13dd2d7a5e5fdd5594e847077932f955b5e2b/README.md),
and [orjson](https://github.com/ijl/orjson/blob/705515d77b28429d0b7c30c3d781abe52e8a1e5a/README.md#performance).
Copies in different repositories can differ; the manifest pins the exact bytes.

Thirteen selected documents appear in
[Boost.JSON's comparison with RapidJSON and nlohmann/json](https://github.com/boostorg/json/blob/e0e74f634194855b4daea49ed4016ef67aa38bff/doc/pages/benchmarks.adoc).
Three more come from
[simdjson's data collection](https://github.com/simdjson/simdjson-data/blob/4197c425e857f0ec38e89822fdd0bd9ea21f4daf/README.md).
Two come from
[yyjson_benchmark](https://github.com/ibireme/yyjson_benchmark/blob/aeefe6a44f37fccf1f9d730766abab9ffea43c6b/README.md).
These add different string lengths, Unicode, numeric arrays, nesting, and file
sizes. The corpus is a set of useful comparisons, not a measured distribution
of application traffic. JSONTestSuite belongs in correctness testing, not this
throughput aggregate.

File sizes below are decimal: 1 KB = 1,000 bytes; 1 MB = 1,000,000 bytes.
Exact byte counts and SHA-256 hashes are in
[`public_corpus_manifest.json`](public_corpus_manifest.json).

| Document | Size | Contents |
| --- | ---: | --- |
| `apache_builds` | 127 KB | Build metadata |
| `canada` | 2.25 MB | Floating-point coordinate pairs |
| `citm_catalog` | 1.73 MB | Indented catalog with repeated keys |
| `github_events` | 65 KB | Nested API event records |
| `google_maps_api_response` | 26 KB | Smaller API response |
| `gsoc-2018` | 3.33 MB | Project metadata and longer ASCII strings |
| `instruments` | 220 KB | Large objects |
| `marine_ik` | 2.98 MB | Model metadata and numeric arrays |
| `mesh` | 724 KB | Compact 3D mesh data |
| `numbers` | 150 KB | Floating-point array |
| `random` | 510 KB | Mixed values and Cyrillic text |
| `semanticscholar-corpus` | 8.59 MB | Academic metadata records |
| `tree-pretty` | 35 KB | Indented object tree |
| `twitter` | 632 KB | API records with CJK text |
| `twitterescaped` | 562 KB | API records with Unicode escapes |
| `update-center` | 533 KB | Software update metadata |
| `poet` | 3.51 MB | Chinese author biographies |
| `otfcc` | 66.41 MB | Noto font data |

The full download is 92,389,797 bytes. `otfcc` needs enough RAM for the
materialized input and the result being checked. `mesh.pretty.json` is omitted
because `mesh.json` already represents those values. The pinned `twitter` and
`twitterescaped` files have different decoded values, so both are retained.
The runner checks actual hashes rather than assuming similarly named files
are duplicates.

### Data terms

**No third-party JSON documents are committed here.** Downloads go into a
directory chosen by the person running the benchmark. The manifest records
source URLs and terms; downloading a file does not grant redistribution rights.

Original data terms remain unresolved for the simdjson files. Its README names
benchmarking as an intended use but asks readers to check individual files.
Do not assume that a parser repository's software license covers copied API
responses or other third-party data. Publish measurements and metadata without
republishing those documents.

`poet` comes from the Chinese-poetry data project, which
[declares MIT terms](https://github.com/chinese-poetry/chinese-poetry/blob/b8594f81a89752241442f2ce267d6f66f96704ee/LICENSE).
That declaration is not an independent audit of every biography's origin.
`otfcc` embeds a SIL Open Font License 1.1 notice for Noto Sans JP Regular 1.004.
The manifest links the evidence and the
[OFL text](https://openfontlicense.org/open-font-license-official-text/).
The yyjson game-data dump is not included.

## Run a comparison

Run these commands from the repository root. The runner needs Python 3.9 or
newer and the measured libraries; it adds no Python package dependency.

List or fetch the documents:

```bash
python crates/jsonmodem-py/benchmarks/bench_public_corpus.py list
python crates/jsonmodem-py/benchmarks/bench_public_corpus.py fetch \
  --directory /tmp/jsonmodem-public-corpus
```

Every download is checked against its pinned size and SHA-256 before installation.
Cached files are checked again. A mismatch fails without overwriting the file.
No download or corpus content is executed.

A local library configuration names each build's interpreter and expected
version. For example, `libraries.json` can keep two orjson versions separate:

```json
{
  "libraries": [
    {
      "name": "jsonmodem",
      "module": "jsonmodem",
      "python": "/path/to/jsonmodem-env/bin/python",
      "expected_version": "0.0.0-alpha.0"
    },
    {
      "name": "orjson_3120",
      "module": "orjson",
      "python": "/path/to/orjson-3120-env/bin/python",
      "expected_version": "3.12.0"
    },
    {
      "name": "orjson_3119",
      "module": "orjson",
      "python": "/path/to/orjson-3119-env/bin/python",
      "expected_version": "3.11.9"
    }
  ]
}
```

Use the same interpreter version and build for a library-only comparison.
Different interpreters are supported, but that measures a configuration change
as well as a library change. A version mismatch fails rather than silently
substituting another release.

For unpacked builds, add `"pythonpath": ["/path/to/package-root"]` to a library.
The runner checks that the imported module came from a configured directory.
Optional `revision` and `wheel_sha256` fields record supplied build identifiers;
they are labeled `declared_...` in results. The runner independently hashes the
imported Python/native files and the interpreter executable. Local interpreter and package
paths are not written to result JSON.

Check correctness without measuring:

```bash
python crates/jsonmodem-py/benchmarks/bench_public_corpus.py verify \
  --directory /tmp/jsonmodem-public-corpus --libraries libraries.json \
  --reference orjson_3120 --reference orjson_3119 \
  --output corpus-verified.json
```

Run both operations with seven independent processes per library and three
timing samples per case in each process:

```bash
python crates/jsonmodem-py/benchmarks/bench_public_corpus.py run \
  --directory /tmp/jsonmodem-public-corpus --libraries libraries.json \
  --reference orjson_3120 --reference orjson_3119 \
  --cpu 0 --repeats 7 --samples 3 --seconds 0.05 \
  --output corpus-timings.json
```

Choose an available CPU; `--cpu` requires OS affinity support. Omit it on systems
without that support. Stop competing heavy work before taking final measurements;
CPU affinity alone does not isolate memory bandwidth, caches, or power limits.
Add `--cases canada citm_catalog twitter` for an exact subset, or
`--operations loads` / `--operations dumps` for one operation. Unknown case names
fail. `--timeout` limits one child process and defaults to 600 seconds.

## What the numbers mean

`loads` receives the unchanged downloaded UTF-8 bytes and returns fully
materialized Python values. `dumps` receives values prepared by the standard
library's `json.loads`, independently of the measured library. Default options
are used. Downloads, reads, hashing, preparation, and correctness checks are
outside timing. Returned-value destruction is included. Cyclic garbage
collection is disabled during timing, but ordinary reference-counted destruction
is not. Inputs are reused across calls, so this measures repeated warm calls,
not startup or cold-cache latency.

Before any timing, every build must match complete values, exact Python types,
float bits including signed zero, dictionary order, and encoded bytes for the
requested operations. Each timed worker repeats its correctness checks and
verifies that the imported files, version, and recorded environment metadata
did not change. A changed runner or helper file also makes workers fail.
Python materialization is part of the measured work; these results are not
directly comparable to published C++ DOM-only or partial-field measurements.

Library order alternates for two builds. With more builds, it rotates and
reverses to balance positions. Document order is shuffled deterministically for
each process repeat and shared across builds. Hash seeds and both orders are
recorded. Calibration chooses an iteration count near `--seconds` for each
sample; the actual counts and durations are retained.

**Latency: lower is better.** `summary.cases.*.measurements.*.latency_ns` is the
median of the process medians, in nanoseconds per call. Each process median is
the median of its timing samples. Minimum/maximum process values and every
sample remain in the JSON; they are not confidence intervals.

**Throughput: higher is better.** `throughput_MB_s` uses decimal megabytes.
For `loads`, bytes mean original input bytes. For `dumps`, bytes mean encoded
output bytes, not the size of the original indented fixture.

**Geometric mean: lower is better.** For each unique case, divide the library's
median latency by the reference's median latency. Take the geometric mean of
those ratios, giving each case one equal weight. A value of `1.20` means a
geometric-mean latency ratio of 1.20 times the reference, not 20% more total time
for every possible workload. `loads`, `dumps`, and combined means are separate;
each reference version also gets its own comparison.

Only the first copy of identical document bytes is timed for `loads`. After
correctness checks, only the first copy of identical encoded outputs is timed
for `dumps`.
`duplicate_cases` names omitted copies. Different-sized documents do not get
extra weight. Keep these corpus aggregates separate from synthetic benchmark
aggregates unless a report explicitly defines a combined weighting.

The result JSON contains metadata and measurements, not fixture contents or local
build paths. It is written atomically only after the requested run succeeds.

For allocation counts and fresh-process peak RSS on the same documents, use the
separate [public-corpus memory runner](PUBLIC_MEMORY.md). The timing worker keeps
a reference tree for correctness checks, so its process RSS is not a suitable
decode-memory comparison.

## Runner tests

The offline tests need pytest but do not download fixtures or require either
native library. They run with the normal Python test suite:

```bash
python -m pytest -q crates/jsonmodem-py/tests/test_public_corpus.py
```

They check download integrity, bad caches, exact typed-value comparisons,
version/build selection, subprocess failure handling, duplicate weighting,
geometric means, and the result format. Their small adapter modules are test
fixtures, not performance substitutes for orjson.
