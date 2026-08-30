# Rejected performance experiments

These experiments are not in the final combined build. Some improved their
intended inputs but repeatedly slowed other inputs. The measurements below
come from those separate experimental builds, not the final benchmark run.

All observations use CPython 3.12.13 and orjson 3.11.9 on Linux x86-64.
jsonmodem was built with Rust 1.94.1; this does not identify the compiler of
the installed orjson wheel. Each experiment keeps its own control and orjson
observations. Do not combine these rows into a suite average.

## Cases that ruled out a change

Microseconds per complete call; **lower is better**. Bold marks the smallest
unrounded comparable median. The control for each experiment is described
below the table.

| Workload and experiment | Control | Experiment | orjson 3.11.9 |
| --- | ---: | ---: | ---: |
| One-key object: direct-mapped decoded-key cache | **0.64181** | 1.13216 | 0.82491 |
| Surrogate pairs: decode four Unicode escapes together | 108.319 | 148.936 | **63.420** |
| Reject 1 MiB unfinished string: profile-guided compilation | 1,498.756 | 2,114.709 | **771.617** |
| Short integer list: numeric-list specialization | 0.140693 | 0.159776 | **0.114441** |
| 1,000 sixteen-field dataclasses: numeric-list specialization | 719.275 | 809.183 | **305.415** |
| Serialize 256-character string: borrowed entry arguments | **0.160891** | 0.182051 | 0.220015 |
| Decode short memoryview: borrowed entry arguments | 0.139583 | 0.152523 | **0.137886** |
| CPython-cached integers: first integer-reuse cache | 9,769.718 | 10,255.777 | **5,165.110** |

The decoded-key cache lost on one-key, threshold and deliberately colliding-
key cases against both unchanged builds. Its table row uses the starting
build. The Unicode experiment compares against the earlier adjacent-escape
decoder: surrogate-pair latency increased about 38% against both controls.
None of its nine cases met the intended repeatable 5% improvement.

The profile-guided build compares against the same combined source without
profile guidance. Twelve malformed-input medians were 27-43% slower than a
fresh normal build and 48-85% slower than the earlier normal build. Improved
valid-input averages did not justify those losses.

Numeric-list specialization reduced ordinary integer serialization time by
about 1% and float serialization time by about 3%. However, its short integer
list took 14% more time than the starting build and 11% more than the unchanged
rebuild. Dataclass serialization took 12.5% and 11.1% more time, respectively.
Both cases were slower in all eight process comparisons against each control.
The table shows the starting-build comparison.

Borrowing Python entry arguments reduced geometric-mean latency across 171
complete-document cases by only 0.54% against the starting build and 0.24%
against the unchanged rebuild. It repeatedly slowed escaped-input decoding,
short memoryviews and root-string serialization. The table's root string took
13.15% more time than the rebuild; the short memoryview took 9.27% more time.
Both were slower in all seven process comparisons. Streaming longer strings
from bytes took 424.219 microseconds versus the rebuild's 404.982: 4.75% more
time, with six of seven comparisons slower. The public-document comparison
and both maintained-suite comparisons finished before rejection.

For integers CPython already caches, the first integer-reuse cache took
4.98% more time than the unchanged rebuild in one comparison and 4.60% more
in a separate comparison. It was slower in all eight and all ten process
comparisons, respectively. The table shows the first comparison. Its prepared
full-suite run was not executed; no full-suite result is claimed.

## Key-cache memory cost

Current RSS with the result alive, in MiB; **lower is better**. This is not
peak RSS. One MiB is 1,048,576 bytes.

| Workload | Starting build | Unchanged rebuild | Key cache | orjson 3.11.9 |
| --- | ---: | ---: | ---: | ---: |
| 32,768 one-key objects with deliberate Unicode-key collisions | 30.023 | 30.012 | 33.586 | **29.500** |

The two unchanged builds and orjson retained 32 key objects; the experimental
cache retained 32,768. Its bounded internal table did not bound the number of
keys in returned objects. These are deliberate collision diagnostics, not
an estimate of average application memory. The separate Memray comparison
stopped after its first worker and remains incomplete.

## Revised integer cache

The revised cache also included the integers CPython already reuses, `-5`
through `256`. Both cache versions were rejected. The revision completed
the seven-case comparison below but did not advance to broader comparisons
or memory measurements.

Each case used ten new Python processes per library. Timings include releasing
the returned list. "Starting" and "Rebuilt" are the two unchanged builds;
"First cache" excludes CPython's reused integers, and "Revised cache"
includes them.

Microseconds per complete `loads` call; **lower is better**. Bold marks the
smallest unrounded median in each row.

| Integer-array workload | Starting | Rebuilt | First cache | Revised cache | orjson |
| --- | ---: | ---: | ---: | ---: | ---: |
| 262,144 copies of 1000 | 11,219.291 | 11,240.634 | 5,402.702 | **5,293.507** | 8,814.587 |
| 262,144 copies of -1000 | 11,116.562 | 11,090.059 | 5,392.981 | **5,278.807** | 8,765.113 |
| 262,144 values cycling through 257 to 1023 | 11,184.834 | 10,968.735 | 5,277.924 | **5,162.692** | 8,561.324 |
| 262,144 distinct large integers | 11,572.948 | 11,695.584 | 12,088.454 | 11,842.907 | **9,201.392** |
| 262,144 values: cache-eligible integers once, then distinct large integers | 11,571.457 | 11,780.683 | 11,842.655 | 11,933.658 | **9,004.191** |
| 524,288 values cycling through -5 to 256 | 9,894.937 | 9,922.102 | 10,319.855 | 10,104.626 | **5,211.726** |
| 128 copies of 1000, cache inactive | 4.345 | 4.290 | 4.317 | 4.405 | **2.597** |

The three repeated-value arrays kept their gains: the revised cache took
52-54% less time than the starting build, 52-53% less than the rebuild and
about 40% less than orjson. All ten process comparisons were faster against
each of those three libraries.

Before timing, acceptance required the CPython-cached case to recover its
loss against both unchanged builds. Other cases could not be more than 2%
slower with at least eight of ten comparisons slower. The revision missed
those requirements: CPython-cached integers remained 2.12% slower than the
starting build and 1.84% slower than the rebuild. Distinct large integers
were 2.33% slower than the starting build in all ten comparisons. The inactive
small input was 2.70% slower than the rebuild in eight of ten.

These targeted cases have no combined score. Their repeated-value wins are
real measurements, but they are not improvements supplied by the final build.
