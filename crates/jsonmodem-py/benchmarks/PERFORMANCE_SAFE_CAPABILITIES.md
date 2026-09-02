# Safer storage, optional event paths, and performance

The measured `7b7e21c` build takes 6.6% less time than the PR #6 baseline
across 275 comparable complete-call cases, using the geometric mean.
It still takes 19.2% more time than orjson 3.11.9. It wins 69 cases and loses
206. These changes do not surpass orjson across the suite.

This report measures runtime revision
`7b7e21c3bd49d22c0964c4a30be16b5367160caf`. It predates the shared long-decimal
correction, checked local Unicode conversions, revised tuple setter, and
dedicated NumPy container writer. Its timings, memory measurements, and
validation counts do not describe those later changes.
The reference is **orjson 3.11.9; version 3.12.0 was not measured**.

## Complete calls

Geometric-mean microseconds per `loads()` or `dumps()` call. **Lower is better.**
Bold marks the best result in the row.

| Cases | PR #6 | PR #6 rebuilt | Selected | orjson 3.11.9 |
| --- | ---: | ---: | ---: | ---: |
| All 275 comparable cases | 44.793 | 44.642 | 41.840 | **35.099** |
| Encoding, 28 cases | 65.563 | 64.496 | 62.498 | **38.734** |
| Complete-call inputs, 58 cases | 19.452 | 19.524 | **18.900** | 19.286 |
| Numbers, 25 cases | 38.624 | 38.735 | 38.633 | **30.824** |
| Strings, 60 cases | 28.639 | 28.690 | 26.949 | **23.371** |
| Dates, 40 cases | 18.665 | 18.359 | 16.167 | **11.865** |
| NumPy dates, 28 cases | 21.125 | 21.002 | **17.523** | 23.009 |
| Public documents, 36 cases | 1,415.423 | 1,413.933 | 1,372.104 | **852.163** |

PR #6 is the previously measured build. Its rebuilt column uses the same
runtime source compiled again. Some measurements differ between these two
controls, so both remain in the report. Each case has equal weight in the overall
mean; a suite with more cases contributes more weight. The mean is not the
time required to run the benchmark suite.

Each suite and build ran in five fresh Python processes, with three samples
per library in each process. jsonmodem cells use the median of five process
medians. The orjson cells pool twenty process medians, five collected alongside
each of four jsonmodem builds. Comparisons paired within each process are
retained separately in the data; they need not equal ratios of these cells.

The [complete tables](data/safe-capabilities-2026-09-02/PERFORMANCE.md) include
the intermediate build and every regression. Their
[data](data/safe-capabilities-2026-09-02/results.json) retain all 33,360 samples,
source and binary identities, input hashes, and output comparisons. The three
predeclared unequal-output date cases remain in the data but are excluded from
all means and win counts: `time_16`, `time_1024`, and `dates_under_dict`.

### Remaining losses

Small-object decoding takes 0.623 microseconds, versus 0.568 for rebuilt PR #6
and 0.522 for orjson. Sixteen-field dataclass output improves from 766.004 to
663.441 microseconds against the rebuild, but orjson takes 305.737.
Sorted-record output takes 309.220 microseconds, versus 295.899 for the rebuild
and 132.888 for orjson. These cases remain in the overall mean.

The regression tables identify a repeated loss when the median paired time
ratio exceeds 1.03 and at least four of five process pairs exceed 1.03.
The selected build has 26 such losses against rebuilt PR #6. This rule
describes repeated observations; it is not a confidence interval.

## Streaming and optional paths

The [streaming tables](data/safe-capabilities-2026-09-02/STREAMING.md) compare
the same API, fragment boundaries, and result retention. They cover Rust
events, buffers and values, Python events, and cumulative value prefixes.
[Streaming data](data/safe-capabilities-2026-09-02/streaming.json) preserve the
observations and exact input descriptions.

`JsonModemEvents()` omits event paths. Callers enable them with
`JsonModemEvents(track_paths=True)`. Existing `JsonModem()` behavior is
unchanged. This choice belongs to each parser instance, so enabling paths
in one client does not impose path tracking on another client through Cargo
feature unification. Omitting paths does not disable JSON validation.

For nested strings, consuming minimal events takes about 1.14 milliseconds,
versus 7.45 milliseconds through the legacy API with paths. Those APIs do
different work. Within the same minimal-event API, the selected build takes
6.5% longer than the intermediate build for each retention policy, using a
geometric mean across inputs.
Rust events take 6.7% longer than rebuilt PR #6, while Rust buffers take 4.1%
longer. The report retains these regressions. Whole-document orjson timing
does not measure equivalent incremental work.

For these percentages, first compare the times from each matched pair of
processes, take the median ratio for each input, then take their geometric
mean. These percentages are not ratios of the displayed table medians.

## Memory

The [memory report](data/safe-capabilities-2026-09-02/MEMORY.md) separates
allocation counts, total requested bytes, peak live allocations, and process
RSS. [Exact counters](data/safe-capabilities-2026-09-02/memory.json) accompany
the tables. These measures are not interchangeable.

jsonmodem has lower peak tracked live memory than orjson in nine of fourteen
Memray cases, but lower peak RSS in only one of seven process-memory cases.
Decoding 100,000 records peaks at 57.531 MiB RSS, versus orjson's 75.555 MiB.
The other six measured peak-RSS cases are higher than orjson.

Large callback output has a higher allocation total and a lower live peak in
this build. Across thirty calls, requested memory rises from 2,508.822 to
3,469.526 MiB against PR #6. Peak tracked live memory falls from 52,810.304
to 32,834.860 KiB.
orjson requests 1,918.175 MiB and peaks at 32,771.751 KiB. Requested memory
includes the full size of reallocations; it does not measure bytes copied.

Memray used one capture per workload and library after warmup. RSS used three
fresh processes without Memray and reports their median. Results were discarded
inside the captures; there is no result-retained RSS reading. MiB means
1,048,576 bytes and KiB means 1,024 bytes.

## Safety and validation

In the measured build, the Rust scanner uses safe ownership and checked string
boundaries. This does not cover all Python Unicode conversions. Buffer exports
retain stable owners until release. The tuple helper prepares elements before
allocating the tuple, and fallible numeric constructors preserve Python
allocation errors.

`PythonOutput` keeps writable storage private, checks capacity, and advances
its length only after bytes are initialized. It uses Python-owned storage only
on the supported GIL-enabled, full-API CPython 3.12 and 3.13 builds. Other
builds keep Rust-owned storage. The
[safety documentation](../../../docs/memory-safety-testing.md) explains these
conditions and the corresponding tests.

The default `cached-zipper` feature retains three unsafe pointer dereferences.
Its private interface ties returned references to the owning zipper and removes
descendant pointers before parent storage can move. Disabling default features
selects safe tree traversal and forbids unsafe code in the core crate. This does
not cover dependencies or the Python extension. Another dependency can enable
the feature again; inspect the resolved features with
`cargo tree -e features -i jsonmodem`.

The selected source passed the following checks. These counts are not additional
distinct tests when the same tests run on another interpreter.

| Configuration | Passed tests | Passed subtests | Skips |
| --- | ---: | ---: | ---: |
| CPython 3.12.13 release | 15,483 | 6 | 0 |
| CPython 3.13.14 | 15,483 | 6 | 0 |
| Debug CPython 3.12.13 | 15,483 | 6 | 0 |
| AddressSanitizer with CPython 3.12.13 | 15,480 | 6 | 3 |
| CPython 3.9.25 | 11,517 | Not separately reported | 1,488 |

Python 3.9 lacked reference dependencies and some interpreter features; its
skips include twelve module-collection skips. It does not establish full
compatibility there. ASan skipped three address-space-limit cases, detected an
intentional heap-buffer-overflow, and passed 400 allocation-failure and recovery
iterations. ASan instrumented the extension, not CPython or most dependencies,
and leak checking was disabled.

Miri passed 258 workspace tests with four existing debug helpers skipped.
Targeted zipper tests passed under Stacked Borrows and Tree Borrows with three
seeds per model. Both models also passed safe-zipper tests. All three SIMD
configurations passed 41 tests each. The four core feature combinations each
passed 228 ordinary tests with six existing ignores. The selected release
passed 78 native binding tests and the separately enabled combined NumPy/date
allocation-failure test.

Miri does not execute live CPython. These checks do not prove memory safety for
all inputs, full orjson equivalence, or that jsonmodem is safer than orjson.
Valid native buffer storage and the GIL remain requirements. Malformed C
extensions and unsynchronized native writes are outside those guarantees.
