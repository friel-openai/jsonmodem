# Speedup experiment record

## Baseline and method

Starting commit: 6bb32dda06a93b4a1241293a16e6a75969e6407b. Runtime source is
the prior b145ac3 implementation. CPython 3.12.13, orjson 3.11.9, NumPy 2.5.2.
Run existing benchmark scripts with eleven alternating rounds and 0.1-second
calibrated batches, pinned to one CPU. Do not run competing benchmarks together.
Exact output equality is required. Keep raw JSON in /tmp and report all cases.

## Experiment 1: NumPy inner loops

Question: can moving dtype dispatch and dimension bookkeeping outside the
innermost scalar loop bring the existing NumPy workloads below orjson time?
The current item() checks kind and byte size on each scalar, and _numpy_dumps
updates a dimension Vec on each scalar. Immutable input bytes already eliminate
one Python object per numeric element. Top-level results already avoid a Python
bytearray copy, so that is not an available optimization.

The first baseline repeats NumPy int64/float32/float64 at 1.27x/1.18x/1.11x
orjson time. Add flat 100,000-element and 1,000x100 variants alongside the
existing 25,000x4 arrays before rebuilding, to test whether a row optimization
generalizes across dimension lengths. These all use the same element counts
and dtype values as the existing public suite.

Measure the existing object suite before and after. Retain an implementation
only if exact-byte differential tests and snapshot validation pass and gains
repeat. Inspect all supported numeric widths, zero-size axes, indentation, and
depth. Reject unchecked pointer reads and metadata-specific benchmark shortcuts.

## Experiment 2: output writing

Inspect allocation growth and string escaping before proposing a change. Record
the concrete hypothesis here before editing it. Preserve existing long-string
decode results as a baseline, not as a newly achieved win.

Encoder::string appends an opening quote, a potentially long prefix, and a
closing quote separately. With a 256-byte initial Vec, a long unescaped prefix
can grow exactly to its needed length, followed by another growth for the last
quote. Reserve the known minimum UTF-8 length plus both quotes before writing.
This is a lower bound for escaped output, not a second grammar scan. Measure
the unchanged seven-workload suite and Memray long-string allocations before
and after; reject a material small/medium regression.

Baseline shape controls (seven rounds, 0.05-second exploratory batches) show
flat NumPy int64/float32/float64 at 4.44x/1.66x/1.50x and 1,000x100 at
4.26x/1.62x/1.48x. Keep these unfavorable controls. The original 25,000x4
workloads are 1.24x/1.19x/1.11x in that run. Artifact:
/tmp/jsonmodem-speedups-numpy-base.json.

Row batching alone returns 1.09x/1.07x/1.04x for the existing NumPy arrays;
artifact /tmp/jsonmodem-speedups-numpy-rows.json. Selecting a const-sized
numeric closure once per snapshot then returns 0.68x/0.87x/0.86x on those
same int64/float32/float64 arrays, while flat/wide controls remain slower
(int64 3.07x/2.92x, float32 1.12x/1.11x, float64 1.07x/1.06x).
Artifact /tmp/jsonmodem-speedups-numpy-typed.json. These are exploratory
seven-round measurements; full confirmation is still required.

All 91 NumPy tests pass with both row batching and typed dispatch. The added
30 parametrized cases exercise varying row lengths and nested placement,
non-finite floats, negative zero, indentation, and trailing newline. A first
typed-dispatch build exposed a temporary float-buffer lifetime error; a local
buffer binding fixes it without unsafe code.

Reserving space for every string reduces the long-string workload from 21.57
to 18.37 microseconds (still 1.85x orjson), removes one event per call, and
reduces Memray peak from 430,157 to 286,797 bytes. Total allocated bytes over
30 calls fall from 17,214,268 to 8,612,638. However small/medium dumps regress
from 1.80x/1.85x to 1.90x/1.93x. Restrict the reservation to strings at least
as large as the initial 256-byte output capacity, then repeat. Artifacts:
/tmp/jsonmodem-speedups-{base,reserve}.json and long-{before,reserve}.json.

## Correctness validation

The final candidate passes 279 binding tests, including the original streaming
and security regressions, and cargo clippy for the Python crate with warnings
denied. .agent/check.sh passes core tests, docs, formatting, actionlint, and
Clippy; actual Miri execution is deferred to CI as in the prior work.

The public orjson 3.11.9 suite first returned 1,615 passes and eleven psutil
failures caused by sandbox PID visibility. The identical command with approved
escalation passes all 1,626 selected tests, with six optional skips and four
package-identity deselections. No test was disabled to obtain this result.

## Full timing runs

The final guarded string reservation restores small/medium dumps to 1.73x/1.85x
and reduces long-string dumps from 21.57 to 18.77 microseconds (1.86x orjson).
The complete ordinary suite is /tmp/jsonmodem-speedups-final.json.

The first full eleven-round object run confirms the existing 25,000x4 NumPy
int64/float32/float64 workloads at 0.69x/0.86x/0.86x orjson time. All output
bytes match. Artifact: /tmp/jsonmodem-speedups-objects-final.json. A separate
fifteen-round run adds flat and 1,000x100 controls using the committed
bench_compat_objects.py --numpy-shapes argument, without removing the original
object benchmarks. Its result will be recorded before publishing claims.

## Confirmed results

The independent 15-round run confirms all three existing NumPy wins. Inputs
contain 100,000 values from numpy.arange, shaped 25,000x4. Ratios are paired
medians; the range is the smallest and largest paired ratio in the confirmation.
This is observed variation, not a confidence interval.

| Workload | Baseline ratio | First 11-round ratio | 15-round ratio | Paired range | jsonmodem ns | orjson ns |
| --- | ---: | ---: | ---: | --- | ---: | ---: |
| NumPy int64 | 1.27x | 0.69x | 0.69x | 0.67-0.70x | 927,922 | 1,347,541 |
| NumPy float32 | 1.18x | 0.86x | 0.86x | 0.85-0.89x | 2,812,011 | 3,267,951 |
| NumPy float64 | 1.11x | 0.86x | 0.86x | 0.85-0.86x | 3,298,697 | 3,839,946 |

Each of the fifteen paired samples beats orjson for each workload. The change
removes repeated work rather than validation: dtype dispatch occurs once per
snapshot, and dimension-stack updates occur per row. Byte-length products,
checked chunk reads, immutable snapshot ownership, and calendar checks remain.
Streaming implementation and public APIs are unchanged. No unsafe code or
dependency was added.

The same confirmation retains all original object cases and six shape controls:

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

These controls do not beat orjson. The exploratory standalone flat-int64 run
was 3.07x, versus 1.60x in the full object suite. The cause of this difference
was not isolated; the runs use different setup and workload order. Neither run
supports a flat-int64 win. Sorted medium varies
across the 2x boundary (1.83-2.14x paired range), so do not claim a consistent
sorted-output 2x bound. Dataclasses remain much slower.

The ordinary eleven-round suite keeps all seven original workloads:

| Workload | loads ratio | dumps ratio |
| --- | ---: | ---: |
| small | 1.18x | 1.73x |
| medium | 1.70x | 1.85x |
| integers | 1.58x | 2.77x |
| floats | 1.83x | 1.07x |
| strings | 1.35x | 1.81x |
| escaped | 1.94x | 2.49x |
| long string | 0.49x | 1.86x |

A separate fifteen-round small/medium confirmation returns 1.17x/1.74x and
1.67x/1.88x for loads/dumps. Long-string dumps repeat at 2.02x, so they do not
consistently meet 2x despite reduced allocations. The long-string decode win
already existed before this pass and is not a new optimization claim.

Artifacts: /tmp/jsonmodem-speedups-objects-{base,final,confirm}.json,
/tmp/jsonmodem-speedups-{base,final,confirm}.json. Reproduce the controls with:

    python crates/jsonmodem-py/benchmarks/bench_compat_objects.py --rounds 15 --seconds 0.1 --numpy-shapes rows4 flat rows100 --output /tmp/objects.json

## Allocation confirmation

Memray 1.20.0, trace_python_allocators=True, ten warmups and thirty measured
calls for every row. Inputs are built before tracking and outputs discarded.
Events include call/loop overhead; peak bytes are simultaneous tracked live
allocations, not RSS. No timing claim uses these profiler runs.

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
than orjson. NumPy event count and total allocated bytes are unchanged from the
prior implementation; peak differs by 752 bytes (less than 0.04%). The speedup
does not trade substantially larger allocations for time.

Artifacts: /tmp/jsonmodem-speedups-alloc-{final,orjson}.json. Reproduce with
bench_allocations.py --calls 30 --module jsonmodem, then --module orjson, using
distinct --output names. The previous RSS report remains historical; RSS was
not remeasured for this pass.
