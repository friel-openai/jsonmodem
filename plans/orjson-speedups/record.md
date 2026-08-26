# Speedup experiment record

## Baseline and method

The starting version was commit 6bb32dda06a93b4a1241293a16e6a75969e6407b,
which contains the same library code as b145ac3. Tests used CPython 3.12.13,
orjson 3.11.9, and NumPy 2.5.2. The optimized code is in commit 4516f73.

For each input, the benchmark took 11 timing measurements of each library.
Each measurement timed many calls on identical data. Both libraries used the
same number of calls. The benchmark increased that count until a batch for the
slower library took at least 0.1 seconds, then divided elapsed time by call count.
It alternated which library ran first and restricted execution to one CPU core.
No other benchmark was run at the same time. Output bytes were checked before
timing and matched exactly.

For each pair of measurements, the benchmark divided jsonmodem's time per call
by orjson's. The tables report the median ratio: the middle value after sorting
the ratios. Below 1.0 means jsonmodem was faster; 2.0 means it took twice as long.
The separate repeat used 15 measurements per library. Exploratory experiments
used seven measurements and a shorter minimum batch time, as noted below.

## Experiment 1: NumPy inner loops

The question was whether NumPy serialization could beat orjson by doing less
work for each number. The old `item()` checked the number type and byte size
for every element. `_numpy_dumps` also updated its position within the array
for every element. The proposed change chose the number formatter once and
processed each row together.

The writer already used an immutable copy of the array's bytes instead of
creating a Python object for every number. It also already returned a top-level
NumPy result without copying it into a Python bytearray. There was no extra
copy to remove there.

The first baseline repeats NumPy int64/float32/float64 at 1.27x/1.18x/1.11x
orjson time. Before rebuilding, the benchmarks added one-dimensional arrays
of 100,000 elements and arrays with 1,000 rows of 100. The existing arrays had
25,000 rows of four. All used the same values and element count. This checked
whether a change helped only one array layout.

Acceptance required repeated speed improvements and passing tests that compare
output bytes with orjson. Tests also covered number types, empty dimensions,
indentation, nesting, and checks that the copied bytes match the declared array
size. Unchecked pointer reads and special cases for benchmark inputs were excluded.

## Experiment 2: output writing

This experiment examined how the output buffer grows while writing strings.
The earlier long-string decode advantage was recorded separately; it was not
a result of this change.

`Encoder::string` appends an opening quote, the string contents, and a closing
quote separately. Its output buffer starts with room for 256 bytes. A long
string can fill the enlarged buffer, forcing it to grow again just for the
closing quote. The proposed change reserved room for the string's UTF-8 bytes
and both quotes before writing. Escapes can still require more room.
The existing seven benchmarks and Memray allocation measurements were used to
check the change. A slowdown on small or medium documents would require revision.

Before the changes, seven measurements per library, with batches taking at least
0.05 seconds for the slower library, showed
flat NumPy int64/float32/float64 at 4.44x/1.66x/1.50x and 1,000x100 at
4.26x/1.62x/1.48x. These slower results are included. The original 25,000x4
workloads are 1.24x/1.19x/1.11x in that run. Artifact:
/tmp/jsonmodem-speedups-numpy-base.json.

Processing whole rows returned 1.09x/1.07x/1.04x for the existing NumPy arrays;
data: /tmp/jsonmodem-speedups-numpy-rows.json. Choosing the formatter once per
array then returned 0.68x/0.87x/0.86x for the same int64/float32/float64 arrays.
One-dimensional arrays and arrays with 100 elements per row remained slower
(int64 3.07x/2.92x, float32 1.12x/1.11x, float64 1.07x/1.06x).
Data: /tmp/jsonmodem-speedups-numpy-typed.json. These initial results used seven
measurements per library. The longer experiments below checked whether the
improvements repeated.

All 91 NumPy tests passed after both changes. The added
30 parametrized cases exercise varying row lengths and nested placement,
non-finite floats, negative zero, indentation, and trailing newline. A first
build failed because the float-formatting buffer would be freed before its
contents were used. Keeping that buffer in a local variable fixed the error
without unsafe code.

Reserving space for every string reduces the long-string workload from 21.57
to 18.37 microseconds (still 1.85x orjson), removes one event per call, and
reduces Memray peak from 430,157 to 286,797 bytes. Total allocated bytes over
30 calls fall from 17,214,268 to 8,612,638. However small/medium dumps regress
from 1.80x/1.85x to 1.90x/1.93x. The next change reserved space only for strings
at least as large as the initial 256-byte output capacity. Data:
/tmp/jsonmodem-speedups-{base,reserve}.json and long-{before,reserve}.json.

## Correctness validation

The final code passed 281 Python binding tests, including the existing streaming
and security tests. `cargo clippy` passed for the Python crate with warnings
treated as errors. `.agent/check.sh` passed the core tests, documentation build,
formatting, actionlint, and Clippy. Miri ran in CI rather than locally.

The public orjson 3.11.9 suite first returned 1,615 passes and eleven psutil
failures because psutil could not inspect the test process inside the sandbox.
The same command outside the sandbox passed all 1,626 selected tests. Six
optional tests were skipped, and four assertions about the package's name or
version were excluded. No behavior test was disabled to obtain this result.

## Full timing runs

Reserving space only for long strings restored small/medium dumps to 1.73x/1.85x
and reduced long-string dumps from 21.57 to 18.77 microseconds (1.86x orjson).
The complete ordinary suite is /tmp/jsonmodem-speedups-final.json.

The first full experiment, with 11 measurements per library, confirmed the 25,000x4 NumPy
int64/float32/float64 workloads at 0.69x/0.86x/0.86x orjson time. All output
bytes matched. Data: /tmp/jsonmodem-speedups-objects-final.json. A separate
experiment took 15 measurements per library and included one-dimensional and
1,000x100 arrays using `bench_compat_objects.py --numpy-shapes`. It kept all
the original object benchmarks. Its results follow.

## Confirmed results

The repeat experiment confirmed all three NumPy improvements. Each input
contained the numbers 0 through 99,999 in 25,000 rows of four, created with
`numpy.arange`. The ratios use the method explained above. The range shows
the smallest and largest ratio among the repeat experiment's 15 measurements.
It describes those observations, not the uncertainty in future results.
Time columns show each library's median nanoseconds per call; one nanosecond
is one billionth of a second. Dividing these columns can differ from the median
ratio because each median is calculated separately.

| Workload | Before changes | First experiment (11 measurements) | Repeat (15 measurements) | Range in repeat | jsonmodem ns/call | orjson ns/call |
| --- | ---: | ---: | ---: | --- | ---: | ---: |
| NumPy int64 | 1.27x | 0.69x | 0.69x | 0.67-0.70x | 927,922 | 1,347,541 |
| NumPy float32 | 1.18x | 0.86x | 0.86x | 0.85-0.89x | 2,812,011 | 3,267,951 |
| NumPy float64 | 1.11x | 0.86x | 0.86x | 0.85-0.86x | 3,298,697 | 3,839,946 |

jsonmodem beat orjson in every one of the 15 comparisons for each array type.
The writer chooses the formatter once per array and tracks its position in the
outer array once per row. It still checks that the declared array size matches
the copied bytes, checks each byte access, and checks date arithmetic. It reads
an immutable copy of the array data. Streaming code and public APIs are
unchanged. No new unsafe code or dependency was added.

The repeat experiment also included all original object cases and six additional
array layouts. A flat array here is one-dimensional with 100,000 elements;
1,000x100 means 1,000 rows of 100 elements.

| Workload | jsonmodem / orjson time |
| --- | ---: |
| sorted medium | 2.00x |
| 1,000 dataclasses | 21.49x |
| 1,000 integer keys | 1.17x |
| 1,000 Fragments | 1.34x |
| flat int64 | 1.60x |
| 1,000x100 int64 | 1.48x |
| flat float32 | 1.12x |
| 1,000x100 float32 | 1.10x |
| flat float64 | 1.08x |
| 1,000x100 float64 | 1.07x |

These additional cases did not beat orjson. The initial standalone flat-int64 run
was 3.07x, versus 1.60x in the full object suite. The cause of this difference
was not isolated; the runs use different setup and workload order. Neither run
showed jsonmodem beating orjson on flat int64 arrays. For sorted medium output,
individual time ratios ranged from 1.83 to 2.14. A ratio below 2.0 was not
consistent. Dataclasses remained much slower.

The ordinary JSON experiment took 11 measurements per library for each of the
seven original inputs. The columns divide jsonmodem's time by orjson's:

| Workload | loads ratio | dumps ratio |
| --- | ---: | ---: |
| small | 1.18x | 1.73x |
| medium | 1.70x | 1.85x |
| integers | 1.58x | 2.77x |
| floats | 1.83x | 1.07x |
| strings | 1.35x | 1.81x |
| escaped | 1.94x | 2.49x |
| long string | 0.49x | 1.86x |

A separate experiment with 15 measurements per library returned 1.17x/1.74x for
small loads/dumps and 1.67x/1.88x for medium loads/dumps. Long-string dumps
repeated at 2.02x, so they do not consistently meet 2x despite reduced
allocations. The long-string decode win
already existed before this pass and is not a new optimization claim.

Artifacts: /tmp/jsonmodem-speedups-objects-{base,final,confirm}.json,
/tmp/jsonmodem-speedups-{base,final,confirm}.json. Repeat the array-layout tests with:

    python crates/jsonmodem-py/benchmarks/bench_compat_objects.py --rounds 15 --seconds 0.1 --numpy-shapes rows4 flat rows100 --output /tmp/objects.json

## Allocation confirmation

Memray 1.20.0 tracked Python memory allocations with
`trace_python_allocators=True`. Each operation ran ten times before tracking
started, then 30 calls were measured. Inputs were built beforehand and each
result was discarded. An event is an allocation request; the counts also
include requests made by the benchmark loop and call machinery.

Peak bytes means the largest amount of tracked memory held at once. It is not
the sum of all allocation requests or the whole process's resident memory
(RSS). Timing measurements were taken separately, without Memray.

| Workload | jsonmodem events/call | orjson events/call | jsonmodem peak bytes | orjson peak bytes |
| --- | ---: | ---: | ---: | ---: |
| loads medium | 4,528.1 | 4,498.1 | 289,852 | 928,870 |
| dumps small | 4.2 | 3.2 | 388 | 1,129 |
| dumps medium | 13.2 | 9.2 | 119,199 | 65,641 |
| long string | 5.2 | 4.2 | 286,797 | 2,097,257 |
| sorted medium | 1,015.2 | 1,011.2 | 122,823 | 69,305 |
| 1,000 Fragments | 10.2 | 7.2 | 30,458 | 16,489 |
| 1,000 dataclasses | 47,867.3 | 8.2 | 63,005 | 32,873 |
| NumPy float32 | 52.3 | 25,034.2 | 2,293,525 | 4,073,865 |
| late default callback | 79,925.3 | 16.2 | 42,675,995 | 33,558,273 |

Long-string reservation reduces its peak 33.3% from the pre-change 430,157 bytes
and removes one event per call. It also removes one growth per large string in
the callback serializer; the late-default case still allocates far more often
than orjson. NumPy's allocation count and total allocated bytes are unchanged
from the previous implementation. Its peak differs by 752 bytes (less than
0.04%). The faster formatting therefore had almost no effect on these memory
measurements.

Artifacts: /tmp/jsonmodem-speedups-alloc-{final,orjson}.json. Reproduce with
bench_allocations.py --calls 30 --module jsonmodem, then --module orjson, using
distinct --output names. The previous RSS report remains historical; RSS was
not remeasured for this pass.

## Publication

The measurements in this record describe the code in
[4516f73](https://github.com/friel-openai/jsonmodem/commit/4516f73221ef8b5fbf806f5241576eb4a2b76ba6).
The PR description reports the NumPy improvements, the slower cases,
and current Memray comparisons. Historical RSS measurements remain explicitly
labeled as measurements of the previous implementation.

All 21 CI checks passed on that commit and on documentation commit `456eec5`.
They include Python 3.9/3.13 tests, Miri, fuzzing, a flamegraph build, and all
six benchmarks. Local `.agent/check.sh`, `.agent/check-py.sh`, Python-crate
Clippy with warnings treated as errors, and `git diff --check` also passed.
The pdoc build still reported its existing `__hash__` type-stub warnings.
