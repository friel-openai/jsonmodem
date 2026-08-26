# Compatibility and allocation evidence

Starting commit: b84ba61. Oracle: orjson 3.11.9 on CPython 3.12.13.

## First experiment

Question: What exact behavior does the oracle require for the user's named
differences, and which allocations can be removed without changing it?

Method: Run identical synthetic values through both modules, compare exact bytes,
types, and exceptions. Inspect the matching public release's tests and source.
Profile native and fallback operations with an allocation profiler, then repeat
CPU-pinned alternating timing batches. Retain changes only when compatibility
regressions pass, memory/stack limits remain effective, and measured allocation
or latency improves. Raw artifacts belong under /tmp/jsonmodem-compat-*.

Known baseline discrepancies: 2**64 decodes as int rather than float;
dumps(1e20) omits the plus sign; loads(None) raises TypeError rather than
JSONDecodeError; converted key collisions are rejected; Fragment validates and
rewrites placeholders; NumPy is converted with tolist/item. None of these are
accepted as completed compatibility work.

## Duplicate-check experiment (before changing the fallback)

The user requested measurements before deciding whether optional rejection is
worth supporting. Measure only the existing `_prepare` membership check with
two otherwise identical functions, using an AST transformation to remove that
one statement. Compare unique string keys, unique integer keys, and repeated
record dictionaries. Pin CPU 0, alternate 15 rounds of 500 calls, and use Memray
with Python allocator tracing for 100 calls per variant. This isolates the
current check; it does not predict the cost of a new standalone tracking set in
a serializer that no longer builds a prepared dictionary. Raw experiment:
/tmp/jsonmodem-compat-duplicate-cost.py and .json.

Result: duplicate checking added 9.94% for 1,000 string keys, 6.62% for 1,000
integer keys, and 2.02% for 1,000 two-field records. Memray allocation event
counts were identical or within 78 events over 100 calls (out of 0.5-4.5 million)
and bytes within 10 KiB. The existing prepared dictionary supplies the lookup;
there is no additional set allocation. This is preprocessing overhead, not
end-to-end dumps overhead. The user prefers no duplicate-rejection extension;
the replacement preserves duplicate output keys without a tracking set.

Baseline differential evidence: the targeted public release suite had 63 failures,
312 passes, 3 skips. Three failures concern this package's name/version rather
than serialization behavior. New local regressions had 24 failures and 18 passes.
Raw logs: /tmp/jsonmodem-compat-upstream-before.log and
/tmp/jsonmodem-compat-regressions-before.log.

## Native NumPy and direct fallback

The new formatter snapshots NumPy bytes and decodes checked byte chunks in Rust.
All 106 applicable NumPy release tests pass (one optional skip). Full upstream
testing excluding long-running memory and Faker tests produced 1,610 passes,
five skips, and eight failures: four package identity/version assertions and four
error details. The named numerical, Fragment, duplicate-key, datetime, subclass,
and dataclass behavior now passes. Local suite: 142 passed.

Independent design experiments found that tobytes() for a 25,000x4 float32 array
retains about 0.4 MB versus 4.8 MB for tolist(), but those are conversion-only
numbers. The next experiment measures complete serialization calls with
benchmarks/bench_allocations.py and Memray, against b84ba61 built in a separate
temporary worktree. Stream allocation records instead of retaining profiler
records as a list. Compare small/medium, sorted, Fragment, dataclass, and NumPy.

Candidate optimizations after measurement: borrow unescaped decoder cache keys
instead of allocating String; cache encoded-key output offsets instead of
allocating a Vec for every key; return root NumPy output without copying it into
a second bytearray. Each must retain parity and improve measured allocations.

The oracle also has process faults for some NumPy datetime descriptors and
overflowing calendar arithmetic. Do not reproduce process faults or integer
overflow; use checked arithmetic and report those cases explicitly. Rust never
borrows a NumPy data pointer. The NumPy snapshot assumes well-formed NumPy
storage, not arrays forged with unsafe foreign-memory interfaces.

## Primitive dictionary keys

Expanded timings found 1,000 unique integer keys at 908,339 ns (25.52x orjson),
slower than b84ba61's 514,058 ns. The direct Python serializer calls native dumps
for each key and value. Add primitive non-string key formatting to the native
writer without an intermediate Python string or duplicate tracking. Keep sorted
mixed-type keys in the existing fallback. Retain this change only if exact output
and strict-integer/key regressions pass and the same benchmark improves.

Dataclass profiling also shows 133,866 allocation events per call despite lower
peak memory. Try serializing each owning field snapshot in one native call,
instead of calling native dumps separately for every field key/value. Preserve
field order, nested dictionary sorting, parent indentation, and the remaining
depth budget. Native code must return without invoking callbacks for unsupported
field values, leaving the iterative Python serializer to handle those values.

Boundary testing found another reference defect: 254 nested lists around a
dataclass with a dict field succeeds, while 253 lists around the same dataclass
fails. The release serializer increments an eight-bit recursion field before
checking ordinary containers, and dataclasses check before incrementing. Keep
the valid dataclass leaf at depth 255, but reject mixed nesting that would wrap
the reference counter. Do not recreate the bypass in the heap-based serializer.

## Allocation results

CPython 3.12.13, NumPy 2.5.2, Memray 1.20.0, CPU 0. Each process warms ten
calls, then profiles 30 complete calls with Python allocator tracing enabled.
Inputs are created before profiling; results are discarded. Counts include
benchmark-loop overhead. Peak means simultaneously live tracked allocations,
not process RSS. Timing runs do not enable Memray.

Baseline b84ba61 was built separately and imported from an extracted wheel,
without replacing the current editable install. Raw profiles and JSON summaries:
/tmp/jsonmodem-compat-alloc-{baseline,v1,v2,v3,inline,orjson}.*. The checked-in
bench_allocations.py reproduces the workloads and collection procedure.
The table includes inline stacks; the subsequent unused-output release is
measured separately below.

| Workload | Baseline events/call | Current events/call | orjson events/call | Baseline peak bytes | Current peak bytes | orjson peak bytes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| loads medium | 4,532.1 | 4,528.1 | 4,498.1 | 289,927 | 289,852 | 928,870 |
| dumps small | 5.2 | 4.2 | 3.2 | 552 | 388 | 1,129 |
| dumps medium | 17.2 | 13.2 | 9.2 | 119,248 | 119,199 | 65,641 |
| sorted medium | 64,098.6 | 1,015.2 | 1,011.2 | 303,022 | 122,823 | 69,305 |
| 1,000 Fragments | 49,992.7 | 10.2 | 7.2 | 483,537 | 30,458 | 16,489 |
| 1,000 dataclasses | 93,095.6 | 47,867.3 | 8.2 | 364,116 | 63,261 | 32,873 |
| NumPy float32 25,000x4 | 1,852,898.5 | 52.3 | 25,034.2 | 7,224,208 | 2,292,773 | 4,073,865 |

Borrowed decoder cache keys and encoder output ranges remove three allocations
per medium call. Returning root NumPy bytes directly removes eight allocation
events per call and about 1.68 MB of cumulative allocated bytes. Dataclass field
snapshots reduce allocation events from the first direct-writer version's
133,866/call to 48,868/call, with a small increase in peak memory (59.9 to 62.4 KB).
These changes are retained. Dataclasses still allocate far more often than orjson.

## Validation

The local suite passes 223 tests, including independent NumPy metadata checks,
10,000 random float bit patterns, mixed-object options, snapshot depth/cycles,
and the existing generated-input, memory-limit, and small-stack regressions.
The public orjson 3.11.9 suite passes 1,626 tests, with six optional skips and
four package-name/version assertions deselected. No behavioral tests are hidden
by the package identity filter. The checked-in check_orjson_release.py validates
the release commit before running the external tests. Their original licenses
and files remain in the separate reference checkout.

The memory tests initially failed because psutil could not find the sandbox's
PID; they passed outside the sandbox. NumPy emits two deprecation warnings for
the upstream generic-NaT tests. Core checks and binding checks pass locally;
pdoc retains three pre-existing hash-stub warnings. Publication and implementation
CI completed successfully; see Publication below.

The final ordinary benchmark found a small-dumps regression to 2.17x after native
field snapshots. Before accepting it, avoid the PyO3 Fragment type lookup for
ordinary containers in Encoder::scalar and inline primitive key dispatch. These
changes retain all validation and remove work that a known list/dict cannot need.
Rerun the same CPU-pinned small/medium batches; acceptance still requires <=2x.

Fragments are immutable PyO3 classes. Their writer currently checks the class,
then repeats the check while acquiring a dynamic PyRef borrow. Use the frozen
class's checked downcast and immutable get() instead, and rerun the Fragment
workload (2.08x before). This does not borrow an external buffer or add unsafe code.

## Final ordinary timings

Release build, CPython 3.12.13, orjson 3.11.9, AMD EPYC 7763, CPU 0.
Eleven alternating rounds with calibrated 0.1-second batches. Reported ratios
are medians of paired samples, not ratios of the two marginal medians.
Raw data: /tmp/jsonmodem-compat-timings-inline.json. All output bytes matched.
Earlier runs, including the rejected 2.17x small-dumps regression, remain in
/tmp/jsonmodem-compat-timings-{v2,final,v5}.json.

| Operation | Workload | jsonmodem ns | orjson ns | Ratio |
| --- | --- | ---: | ---: | ---: |
| loads | small | 513 | 458 | 1.18x |
| dumps | small | 295 | 164 | 1.80x |
| loads | medium | 418,304 | 243,891 | 1.72x |
| dumps | medium | 168,371 | 89,127 | 1.89x |
| loads | integers | 303,705 | 184,935 | 1.64x |
| dumps | integers | 120,203 | 43,528 | 2.76x |
| loads | floats | 522,303 | 278,856 | 1.87x |
| dumps | floats | 316,959 | 298,521 | 1.06x |
| loads | strings | 49,823 | 36,470 | 1.36x |
| dumps | strings | 23,401 | 12,817 | 1.81x |
| loads | escaped | 284,754 | 143,093 | 1.99x |
| dumps | escaped | 104,186 | 40,535 | 2.57x |
| loads | long string | 23,521 | 49,443 | 0.47x |
| dumps | long string | 21,234 | 10,043 | 2.16x |

The original small/medium target is retained. Integer-array and string-heavy
serialization still exceed 2x; these results do not establish universal parity
in throughput. The float formatter change improves both compatibility and time.

## Final object and option timings

Same timing procedure; NumPy arrays contain 100,000 elements shaped 25,000x4.
All output bytes match the reference. Raw data:
/tmp/jsonmodem-compat-objects-{baseline,v2,v3,final,inline}.json. The table uses
the inline-stack build, including release of unused output before callbacks.

| Workload | jsonmodem ns | orjson ns | Ratio |
| --- | ---: | ---: | ---: |
| sorted medium | 257,487 | 109,199 | 2.36x |
| 1,000 dataclasses | 1,702,193 | 80,428 | 21.20x |
| 1,000 integer keys | 42,005 | 35,367 | 1.19x |
| NumPy int64 | 1,686,517 | 1,340,332 | 1.26x |
| NumPy float32 | 3,838,705 | 3,249,504 | 1.18x |
| NumPy float64 | 4,258,296 | 3,823,572 | 1.11x |
| 1,000 Fragments | 14,593 | 10,456 | 1.40x |

Primitive key formatting improved from 25.52x to 1.12x without duplicate
tracking. The frozen Fragment accessor improved its workload from 2.08x to
1.43x. Dataclass field snapshots roughly halved time versus the first direct
serializer (43.40x), but Python object handling remains expensive. No claim is
made that all supported types meet 2x.

The inline-stack build improves the original small workload but sorted medium
regresses from the previous run's 1.94x to 2.36x. Keep the allocation reduction
and the original small/medium target; report sorted output as remaining work.

Final ownership review added a GC traversal hook for Fragment's retained Python
object. This lets Python collect cycles through an invalid Fragment payload;
the immutable object itself needs no mutable clear operation. The regression
uses a weak reference to observe collection. Ordinary serialization is unchanged.

## Shallow container stack experiment

Published implementation cfc5da5 repeats at 1.26x/2.01x for small loads/dumps and
1.69x/1.79x for medium loads/dumps. The small serializer has insufficient margin
despite the previous 1.90x result. Raw data:
/tmp/jsonmodem-compat-cfc5da5-confirmation.json. Do not discard this repeat.

Replace the per-call container Vec allocation with SmallVec holding at most two
inline frames, then spilling to the heap. SmallVec 1.15.1 is already in Cargo.lock
through the benchmark dependency jiter. This is bounded native stack storage,
not recursive parsing. Rerun timings and allocation counts and retain it only
if small/medium improve or remain within 2x, with 64 KiB thread tests passing.

The fallback call also retains Encoder.output even after native serialization
returns unsupported. Measure a late default callback after 5,000 4 KiB strings
with bench_allocations.py --workload late_default --calls 3. Then drop Encoder
before entering Python. The decision metric is peak live bytes; no allocation
count reduction is expected. Callback ownership and output tests must still pass.

Retained both changes. Inline storage removes one allocation per shallow native
call and brings small dumps to 1.80x; all 223 binding tests, including the 64 KiB
stack tests, pass. The late-default peak drops from 76,243,699 to 42,672,883 bytes
(44.0%) with exactly the same 254,786 events and 1,116,881,443 allocated bytes
over three calls. Artifacts: /tmp/jsonmodem-compat-late-{before,after}.json.

A separate 15-round confirmation on published b145ac3 returns small loads/dumps
1.24x/1.77x and medium loads/dumps 1.76x/1.88x. Raw samples:
/tmp/jsonmodem-compat-b145ac3-confirmation.json. This confirms margin below 2x
on the original workloads rather than selecting the earlier favorable run.

## Publication

Implementation: cfc5da5; inline stacks and unused-output release: b145ac3. Both
are pushed to friel-openai/jsonmodem PR #1, which remains ready for review.
The PR body describes current timings and remaining limits. On 2026-08-26,
GitHub's check-runs API reports all 21 checks successful on
[b145ac3](https://github.com/friel-openai/jsonmodem/commit/b145ac342810707dd6827707ae93089a74143c38).
This includes Python 3.9/3.13, Miri, fuzzing, flamegraph, and all six benchmark
jobs. Final local .agent/check.sh and .agent/check-py.sh also pass on b145ac3.

The completion commit changes only this evidence and plan.md. Its checks are
verified separately before completing the goal; no further source changes or
optional tests are needed unless final validation finds a defect.
