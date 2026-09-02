# Corrected runtime: performance and memory

Across 275 comparable `loads()` and `dumps()` cases, this build takes 3.4%
less time than PR #6 and 22.5% more time than orjson, using the geometric
mean. It wins 71 cases and loses 204 against orjson. **It does not surpass
orjson overall.** Long non-ASCII string encoding also takes about seven to
eight times as long as rebuilt PR #6.

These measurements use runtime revision
`96318df6102bf40e30383125f77fa300ca236047`, including the shared long-decimal
correction, checked local Unicode conversions, revised tuple setter, and
dedicated NumPy container writer. They do not reuse the earlier `7b7e21c`
timings. The reference is **orjson 3.11.9; version 3.12.0 was not measured**.

## Complete calls

Geometric-mean microseconds per complete call. **Lower is better.** Bold
marks the lowest unrounded result in each row.

| Cases | PR #6 | PR #6 rebuilt | Corrected | orjson 3.11.9 |
| --- | ---: | ---: | ---: | ---: |
| All 275 comparable cases | 44.521 | 44.775 | 43.020 | **35.111** |
| Encoding, 28 cases | 65.007 | 64.637 | 63.463 | **38.456** |
| Complete-call inputs, 58 cases | 19.527 | 19.559 | 20.900 | **19.271** |
| Numbers, 25 cases | 38.247 | 38.461 | 38.515 | **30.659** |
| Strings, 60 cases | 28.509 | 28.757 | 27.310 | **23.321** |
| Dates, 40 cases | 18.176 | 18.679 | 15.852 | **11.802** |
| NumPy dates, 28 cases | 21.042 | 21.073 | **17.475** | 22.946 |
| Public documents, 36 cases | 1,416.591 | 1,410.373 | 1,431.645 | **873.624** |

Each case has equal weight. These means are not the time required to run the
suite. PR #6 is the previously measured binary; its rebuilt column recompiles
the same runtime source. The corrected build takes 3.9% less time than that
rebuild across the comparable cases.

Each suite and build ran in five fresh Python processes, with three samples
per library in each process. jsonmodem cells use the median of five process
medians. The orjson cells pool twenty process medians collected alongside
four jsonmodem builds. Paired comparisons remain separate in the data.

The [full tables](data/safe-capabilities-corrected-2026-09-02/PERFORMANCE.md)
include the intermediate build and every regression. The
[data](data/safe-capabilities-corrected-2026-09-02/results.json) retain all
33,360 samples, measured identities and output checks. The three predeclared
unequal-output date cases remain in the data but enter no mean or win count:
`time_16`, `time_1024`, and `dates_under_dict`.

### Gains and losses

The `otfcc` document decodes in 796.748 ms, versus 992.763 ms for rebuilt
PR #6 and 892.332 ms for orjson. Encoding sixteen-field dataclasses takes
672.072 microseconds, versus 774.138 for the rebuild and 304.305 for orjson.

Long root-string encoding is the largest regression. The three non-ASCII
fixtures take 82.772, 93.220 and 83.231 microseconds respectively,
versus 11.752, 11.700 and 12.013 for the rebuild. orjson takes about
8.6 microseconds for each. Small-object decoding takes 0.646 microseconds,
versus 0.553 for the rebuild and 0.520 for orjson.

Thirty-five cases have a median paired slowdown above 3% against the rebuild
and exceed 3% in at least four of five matched processes. All remain in the
report. This is a descriptive rule, not a confidence interval. The comparison
measures whole revisions; it does not isolate the cost of each source change.
The UTF-8 checks remain enabled despite the encoding regressions.

## NumPy containers

The separate [64-case NumPy comparison](data/safe-capabilities-corrected-2026-09-02/NUMPY.md)
uses `7b7e21c` and its unchanged rebuild as controls, not PR #6. It includes
numeric scalars, lists, dictionaries and datetime arrays. These cases do not
enter the 275-case mean above.

Geometric-mean microseconds per complete `dumps()` call. **Lower is better.**
Each entry is the median of five process geometric means. The orjson column
uses the measurements paired with the corrected build. Bold marks the lowest
unrounded time in each row.

| Cases | Earlier build | Earlier build rebuilt | Corrected | Paired orjson |
| --- | ---: | ---: | ---: | ---: |
| All 64 | 16.011 | 16.191 | 12.334 | **7.783** |
| 12 numeric lists | 149.055 | 149.487 | 75.252 | **28.758** |

The twelve list cases use about 50% less time than either control in the
paired comparisons. All five process groups improve, but the corrected build
still loses to orjson. Smaller datetime and scalar slowdowns remain in the
[data](data/safe-capabilities-corrected-2026-09-02/numpy.json).

Each list repeats one scalar object 1,024 times; each dictionary repeats one
scalar for 128 distinct keys. The measurements do not isolate the writer from
the other corrections. The parent process also reaped one additional
successful child whose executable and lifetime were not recorded. Whether
that child overlapped measurement is unknown. The memory costs are below.

## Streaming

The [streaming tables](data/safe-capabilities-corrected-2026-09-02/STREAMING.md)
and [data](data/safe-capabilities-corrected-2026-09-02/streaming.json) compare
the same APIs, fragment boundaries and result retention. Whole-document
orjson timing is shown separately because it does different work.

All nine Rust core cases are slower than PR #6. With 5,000 requested chunks,
event processing takes 181.895 microseconds versus 142.372. Across the three
chunk settings, paired geometric means use 17.8% more time for events, 7.9%
for buffers and 6.4% for values.

`JsonModemEvents()` omits paths; callers enable them per instance with
`track_paths=True`. This does not depend on Cargo features or disable JSON
validation. For nested strings, consuming events without paths takes
1.097 ms versus 7.265 ms with paths. Those modes perform different work.
Within the same pathless API, the corrected build takes 4.0% more time for
consumed results and 4.6% more for retained results than the first combination.
Tracked retained events improve by 7.0% against that combination.

These percentages use the geometric mean of case median ratios from matched
processes, not ratios of the displayed table medians.

## Memory

The [memory report](data/safe-capabilities-corrected-2026-09-02/MEMORY.md)
separates allocation requests, total requested bytes, peak tracked live
memory and whole-process RSS. Its
[data](data/safe-capabilities-corrected-2026-09-02/memory.json) preserve exact
counters and all RSS samples. These measures answer different questions.

The corrected build has lower peak tracked live memory than orjson in nine
of fourteen main cases. Decoding 100,000 records peaks at 57.629 MiB RSS,
versus 72.887 for orjson. Large callback output peaks at 56.371 MiB RSS,
versus orjson's 40.238. The float32-array peak is 37.711 versus 37.758 MiB;
that small difference does not establish a general RSS advantage.

Across thirty large callback-output calls, jsonmodem requests 3,469.526 MiB
versus 2,508.822 for PR #6 and 1,918.175 for orjson. Peak tracked live memory
is 32,834.860 KiB, versus 52,810.304 for PR #6 and 32,771.751 for orjson.
Requested bytes include full realloc sizes; they do not measure bytes copied.

The separate NumPy-container memory comparison uses `7b7e21c`, not PR #6,
as its control. All four corrected cases request more bytes and have higher
tracked peaks than that control. Each container repeats one scalar object;
these are not measurements of distinct scalar values. Its RSS workers also
construct all 64 factory inputs before retaining one, so process peaks include
that setup. The full report preserves those costs and limitations.

Memray used one capture per case and library after ten warmup calls. Separate
RSS checks used three fresh processes making ten calls without warmup or
Memray. Results were discarded; there is no result-retained RSS measurement.

## Safety and compatibility

The [validation report](data/safe-capabilities-corrected-2026-09-02/VALIDATION.md)
distinguishes full suites, focused test repairs, skips and coverage gaps.
The [safety documentation](../../../docs/memory-safety-testing.md) states the
ownership, initialized-storage and GIL requirements behind the unsafe helpers.

The default `cached-zipper` feature retains three private pointer dereferences.
Disabling it selects safe tree traversal and forbids unsafe code in the core
crate. Another dependency can enable it again through Cargo feature unification;
this does not affect the per-instance choice to omit event paths.

Local Unicode conversions check UTF-8, but unchecked conversions remain in
PyO3-generated argument handling and error formatting. Overflow error offsets
can differ from orjson, and the three unequal-output date cases remain excluded
from timing comparisons. Valid native storage and the GIL remain requirements.
Passing tests is not a proof of memory safety or complete orjson equivalence.
