# Python performance on public documents and date/time values

The largest improvements are date/time serialization and decoding strings
with many escapes. On the public documents and existing 171-case suite, the
combined geometric-mean latencies change by less than 1% against both
unchanged builds. These changes do not make jsonmodem a generally faster
replacement for orjson.

The comparison uses **orjson 3.11.9**, CPython 3.12.13 and NumPy 2.5.2 on
Linux x86-64. orjson 3.12.0 was not measured.

## Suite results

**Before** is an unchanged rebuild of [PR #3](https://github.com/friel-openai/jsonmodem/pull/3),
commit `b7fe329`. **After** is the tested build at `b0f3190`. A second control
uses the original PR #3 build; its results are retained in the
[complete tables](data/final-2026-08-30/PERFORMANCE_FINAL.md).

Geometric-mean latency in **microseconds per complete call; lower is better**.
Bold marks the smallest value in each row. The orjson column uses observations
collected alongside After; the appendices retain each control's own orjson
observations too.

| Suite | Before | After | orjson |
| --- | ---: | ---: | ---: |
| Public documents: 18 loads cases | 2,327.939 | 2,352.351 | **1,621.712** |
| Public documents: 18 dumps cases | 1,050.490 | 1,051.258 | **478.329** |
| Public documents: all 36 cases | 1,563.802 | 1,572.554 | **880.745** |
| Maintained synthetic suite: 171 cases | 32.297 | 32.339 | **24.756** |
| Python date/time and controls: 40 equal-output cases | 237.959 | 21.162 | **11.742** |
| NumPy datetime64: 28 cases | 70.511 | **21.101** | 22.960 |

A geometric mean gives each case equal weight. It combines the case
latencies, rather than adding the time to run the suite. Large files do not
receive extra weight. These suites describe different inputs and are not
pooled into one score or treated as an application traffic distribution.

Relative to orjson, the After means are **1.785 times the latency** on public
documents, **1.306** on the maintained suite, **1.802** on the date/time suite,
and **0.919** on NumPy datetime64. A value below 1 means less time than orjson.
The corresponding Before values are 1.776, 1.305, 20.153 and 3.068. Each
comparison divides a case's latency by its own orjson reference before taking
the equally weighted geometric mean.

## Gains and regressions

Selected examples in **microseconds per complete call; lower is better**.
They illustrate the changes, not a separately scored suite. All cases remain
in the appendices, including slower cases.

| Workload | Before | After | orjson |
| --- | ---: | ---: | ---: |
| Serialize 1,024 UTC datetimes | 2,729.748 | **65.922** | 100.799 |
| Serialize 4,096 NumPy microsecond timestamps | 831.836 | **113.538** | 297.897 |
| Decode densely escaped strings | 266.226 | **119.510** | 128.204 |
| Decode public `twitterescaped` document | 2,001.617 | 1,871.264 | **1,108.162** |
| Decode a long plain string from bytes | **19.534** | 22.203 | 94.942 |
| Serialize 1,024 two-field dataclasses | 215.796 | 225.104 | **84.166** |

The UTC and NumPy examples improve in all eight process comparisons against
each unchanged build. The dense-escape example improves in all seven. The
public `twitterescaped` load improves 6.5-7.2% against the two controls, in
all eight comparisons, but remains slower than orjson.

The losses also repeat. Thirty-one of the 171 maintained cases take over 3%
more time than both unchanged controls. Long plain-string loads take about
13-15% more time in several maintained cases. The date suite's dictionary
and dataclass controls take about 4-7% more time. These are recorded losses,
not discarded outliers. No measured numeric or string incremental-API
latency median worsens by more than 3% against either control.

On public documents, After has a lower median than orjson in only two of 36
cases; both wins already existed before these changes. Fourteen cases still
take more than twice orjson's time. On the focused suites, After beats orjson
in nine of 40 equal-output date/time cases and 15 of 28 NumPy datetime64 cases.

## Malformed inputs

Long unfinished strings become cheaper to reject, but several early errors
get slower. These are **microseconds per rejected call; lower is better**.
Timing includes catching and releasing the exception. Rejection results do
not enter the successful-parsing geometric means.

| Invalid input | Before | After | orjson |
| --- | ---: | ---: | ---: |
| 1 MiB unfinished string | 1,481.575 | **566.211** | 765.547 |
| 1 MiB unfinished escape | 2,395.064 | 1,463.228 | **771.197** |
| Syntax error at start of 1 MiB input | 108.088 | 127.006 | **85.929** |
| Excessive nesting: 524,288 arrays | 140.231 | 156.886 | **90.816** |
| Syntax error at end of 1 MiB input | 25,898.513 | 25,967.754 | **1,877.266** |

Four of the 39 cases exceed a 3% loss against both unchanged builds: early
syntax errors in 4 KiB, 64 KiB and 1 MiB inputs, and the largest nesting
case. The last two take about 17.5% and 11.9% more time, respectively,
with every process comparison exceeding 3% against both controls.

The late-error case remains much slower than orjson. jsonmodem constructs
Python values before discovering that late syntax error; orjson checks its
yyjson document before creating those Python values. Both still allocate
memory. For that case, jsonmodem still makes 262,083 allocation requests
versus orjson's 28, and peaks at 25.075 MiB of tracked live memory versus
12.004 MiB. These jsonmodem counters are unchanged from both controls.
The [complete rejection tables](data/final-2026-08-30/MALFORMED.md)
include every case and its separate allocation measurements.

## Memory

Serializing **1,024 UTC datetimes**, one tracked call after ten warmups.
**Lower is better in every row.** One KiB is 1,024 bytes. These are Memray
counters, not process RSS.

| Metric | Before | After | orjson |
| --- | ---: | ---: | ---: |
| Allocation requests | 62,489 | **22** | 1,041 |
| Total requested memory (KiB) | 3,415.322 | **171.660** | 200.054 |
| Peak live tracked memory (KiB) | 99.840 | 99.611 | **64.681** |

The formatter removes allocation traffic, but its peak tracked memory is
still higher than orjson's. In the separate RSS measurement, Before peaks at
24.352 MiB, After at 24.426 MiB and orjson at 23.730 MiB. Preparation sets
the peak before serialization in all three processes for each library.

The 4,096-element NumPy timestamp example keeps
the same jsonmodem allocation counts and tracked-byte measurements. Six NumPy
scalar cases remove one request each. Public-document and maintained
synthetic allocation medians are unchanged from both controls.

For the largest public document, `otfcc`, the RSS comparison depends on
which point is measured. **MiB; lower is better.** One MiB is 1,048,576 bytes.

| `otfcc` loads: whole-process memory | After | orjson |
| --- | ---: | ---: |
| Peak RSS, including preparation | **707.645** | 871.758 |
| RSS with the first returned result alive | 707.621 | **582.477** |

The lower peak already existed in the unchanged jsonmodem builds. The
returned-result snapshot favors orjson. Neither observation supports a
claim that jsonmodem always uses less memory. RSS includes interpreter,
input preparation and allocator retention; Memray instead tracks allocations
during the selected call. The complete report separates requests, requested
bytes, tracked peak bytes and RSS for every measured workload.

## What changed

- The complete-document string decoder skips empty copies and redundant
  scans between adjacent escapes.
- Exact supported Python date/time objects use a checked Rust formatter and
  initialized byte buffer. Subclasses and custom timezones retain their
  existing handling.
- NumPy datetime64 formatting uses an initialized byte buffer and checked
  digit-pair lookup instead of general-purpose formatting.
- Error-position calculation counts characters in a checked prefix in bulk,
  with the previous calculation retained for invalid byte boundaries.

[Profiling notes](PERFORMANCE_PROFILING.md) explain the evidence and remaining
costs. [Rejected experiments](PERFORMANCE_EXPERIMENTS.md) include integer and
key caches, numeric-list specialization, grouped Unicode decoding, borrowed
entry arguments and profile-guided compilation. Selected wins from those
experiments are not presented as gains supplied by this build.

## Method and limits

The [public corpus](PUBLIC_CORPUS.md) contains 18 documents from benchmark
collections used by simdjson and yyjson. Selection and exclusions preceded
relative timing. Downloads have pinned revisions and hashes; the repository
does not redistribute the documents. The [initial baseline](PUBLIC_BASELINE.md)
also includes separate first-use serialization measurements. Those earlier
measurements are not combined with these final repeated-call results.

Each complete-call case median comes from new interpreter processes: eight
per build for public documents and date/time, seven for the maintained suite.
Each process uses three timed batches of calls. Preparation and correctness
checks are outside timing; releasing the returned value is included. Build order rotates.
Final timing and memory commands ran one at a time, without competing builds
or tests from this investigation. The host was not exclusive.

The machine is an AMD EPYC 7763 with AVX2, running Ubuntu 24.04.4. Final
measurements used CPU 12. jsonmodem used Rust 1.94.1, thin LTO, one codegen
unit and line-table debug information, without profile-guided compilation or
`target-cpu=native`. These compiler details do not describe the orjson wheel.
CPU frequency was not fixed. Differences between unchanged builds remain
unexplained; both controls are retained rather than attributing small changes
to source alone.

Three date fixtures have different output bytes: `time_16`, `time_1024` and
`dates_under_dict`. orjson 3.11.9 omits a leading zero in some time fractions;
jsonmodem retains six fractional digits. This preexisting difference is
tested explicitly. Those rows remain visible but do not enter the 40-case
equal-output date mean or receive cross-library winner highlighting.

Public and date/time memory measurements use three fresh processes per case
and library. Synthetic allocation cases share a worker's earlier case history.
Three repetitions do not fully balance four library positions. Allocation
requests and requested bytes were recounted from Memray captures; tracked
peaks use Memray's reported high-water mark, not an independent reconstruction.
Some successful-worker stderr is not retained by the public runner. The appendices state the
different preparation and process-history rules for each memory suite.

These changes add no local `unsafe` Rust blocks. Existing bindings and native
dependencies still contain unsafe code. See the [implementation and safety
comparison](IMPLEMENTATION_SAFETY.md) and [validation results](PERFORMANCE_VALIDATION.md)
for ownership rules, coverage and limits. Neither tests nor benchmarks prove
equivalence for every Python object or establish that one library is more
secure overall.
