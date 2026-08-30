# Final benchmark data

Start with the [performance report](../../PERFORMANCE_36H.md). The
[summary tables](PERFORMANCE_FINAL.md) link every measured case, including
regressions and the three date cases with unequal output bytes.

## Libraries

- **Original:** the existing PR #3 build at `b7fe329`.
- **Rebuilt:** a second compilation of that unchanged source.
- **Final:** the measured implementation at `b0f3190`.
- **orjson:** version 3.11.9.

The main report calls Rebuilt "Before" and Final "After". The two unchanged
builds remain separate controls because their timings differ. Full revisions,
native-extension hashes, wheel hashes, interpreter identity and package
versions are in [data.json](data.json). An unknown reference wheel or source
identity is left null rather than inferred from its version.

## Reading the numbers

Tables state their units and whether lower is better. Each workload occupies
one row, with libraries in separate columns. Bold uses the smallest unrounded
value among equivalent outputs, including exact ties. Rounding can make two
displayed numbers look equal when their unrounded values differ. Bold is not
a statistical significance test.

Complete-call timings include disposal of the returned value. Preparation,
file reads, correctness checks and hashing are excluded. Each process times
three batches of calls. The case median is the median of those process
medians, not the median of all individual calls. Public and focused date/time
runs use eight processes per build; maintained runs use seven.

The geometric mean is `exp(mean(log(case_latency)))`, with equal case
weights. For comparisons with orjson, first divide each case latency by its
corresponding orjson latency, then take the geometric mean. A ratio of 2
means twice the time. Paired runners measure orjson in both control and Final
processes; those reference observations stay separate. Do not pool the
different suites, controls, incremental APIs or malformed inputs into one
score.

## Memory measurements

Memray tracks one call after ten warmups, with Python allocator tracing
enabled. The public, date/time and malformed-input workers use a fresh
process for each workload and library. Maintained synthetic allocation
workers measure several workloads in sequence; their process history and
enabled cyclic garbage collector differ from the other memory suites.

- Allocation requests count allocating calls, including zero-byte requests.
  Deallocations do not count.
- Total allocated bytes sum requested sizes, including each realloc's full
  new size. They are not simultaneously live memory.
- Peak live bytes are Memray's reported capture high-water mark. They exclude
  preparation and warmups and are not process RSS.

RSS is measured separately without Memray, using ten calls without serializer
warmup. The headline is Linux's final `VmHWM`, including preparation, imports
and retained allocator pages. `ru_maxrss` remains a separate recorded value.
Do not subtract high-water marks to infer memory used only by serialization.

Public and date/time workers record startup, preparation, first result alive,
first result released, and completion. Date/time workers construct their
suite's fixtures and release the unselected values before measuring calls;
that preparation can set the RSS peak. Synthetic workers instead record
startup, preparation, first call completed, and completion. Their first-call
snapshot is after releasing the result, not while it is alive.

Every memory table uses the median of three observations. Three repetitions
do not fully balance four library positions. There is no memory geometric
mean. Incremental string-buffer allocations are separate reported values:
their runner deletes its captures, so those counts were not independently
recounted and do not describe RSS.

## Retained observations

`data.json` contains case medians, geometric means and the observations used
to calculate them. It retains 51,576 timing sample values, 168 incremental
buffer process medians, 3,288 memory observations and 6,756 RSS snapshots.
These counts are not counts of independent processes: several cases share
one process in the public, paired and synthetic runners.

Timing samples are batch elapsed time divided by call count, in nanoseconds
per call. Available iteration counts, repeat numbers, hash seeds and execution
positions remain in the data. The incremental buffer runner did not save its
batch samples or call counts; none are invented. Each memory observation
retains the measured counters and available RSS snapshots.

The JSON includes hashes of the reviewed input records. It does not include
corpus contents, capture binaries or profiler logs. The public corpus's
[pinned download manifest and runners](../../PUBLIC_CORPUS.md#run-a-comparison)
support new comparisons. The [validation report](../../PERFORMANCE_VALIDATION.md)
describes the tested packages and coverage limits.
