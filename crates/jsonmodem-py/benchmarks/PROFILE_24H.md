# CPU profiles: remaining parsing and encoding costs

Dictionary work, Python object construction and output copying remain costs
after these optimizations. The profiles identify code worth investigating;
they do not show that removing one function would deliver a particular speedup.
Use the [separate timing measurements](PERFORMANCE_24H.md) for speed comparisons.

## Method and coverage

These ten recordings use the measured Final binary at `b889f4c` and the
orjson 3.11.9 wheel on CPython 3.12.13. orjson 3.12.0 was not measured.
Build hashes and the full counts are in
[profile-summary.json](data/profiles-2026-08-31/profile-summary.json).

Each recording requests native stacks from py-spy 0.4.2 at 19 samples per
second. After ten warmup calls, one worker repeatedly performs its operation
for 32 seconds, one complete call per batch, with automatic GC disabled.
Preparing inputs and checking results happen outside that loop. The sampler
observes the worker and its supervisor; the analysis counts operation samples
only from the worker's designated operation function. Setup samples and
supervisor samples remain counted separately.

The recordings ran sequentially on logical CPU 16 after all timing and memory
measurements. No builds or tests ran alongside them. The host was not exclusive.
Profiler overhead and completed-call counts are not benchmark results.

All ten workers and samplers exited successfully. Seven recordings have no
sampling errors. None reports sampling lag. Operation-sample counts are:

- Decode `otfcc`: 597 for Final and 598 for orjson. Final reports one sampling error.
- Encode `otfcc`: 614 for Final and 598 for orjson, with no sampling errors.
- Decode `canada`: 613 for Final, with three sampling errors.
- Encode `citm_catalog`: 600 for Final, with no sampling errors.
- Decode `long_plain`: 576 for Final and 579 for orjson, with no sampling errors.
- Reject `syntax_late`: 445 for Final and 598 for orjson. Final reports 130 sampling errors; orjson reports none.

These are profiler diagnostics, not JSON test failures. In particular, the
late-error recording cannot support a reliable comparison of function
proportions. The failed samples are not discarded or replaced by a rerun.

Inclusive counts mean a function appeared somewhere on a sampled stack,
including while a child function ran. Caller and child counts overlap and
must not be added. Leaf counts identify the innermost reported frame, not
necessarily an independently measured function. Inlining and symbolization
limit interpretation. An inlined PyO3 frame is not evidence that its wrapper
alone consumed the sample.

Some native addresses have no source attribution. Some CPython symbol names
are implausible and were not used to identify functions. The JSON retains
these unresolved and suspect counts rather than assigning them to guessed
functions. The orjson wheel does not provide comparable source attribution
for its native work.

## Large documents

Selected inclusive samples from Final. **These are diagnostic counts, not
latency measurements or faster/slower rankings.** Each denominator is the
operation-sample count for that recording.

| Operation | Function on sampled stack | Samples |
| --- | --- | ---: |
| Decode `otfcc` | PyO3 dictionary `set_item` | 123 of 597 |
| Decode `otfcc` | `Decoder::key` | 78 of 597 |
| Encode `otfcc` | `DictScalarCursor::next` | 226 of 614 |
| Encode `otfcc` | PyO3 `PyBytes::new` | 107 of 614 |
| Encode `citm_catalog` | `DictScalarCursor::next` | 208 of 600 |
| Encode `citm_catalog` | `Encoder::extend` | 105 of 600 |
| Decode `canada` | `owned_list::append` | 100 of 613 |
| Decode `canada` | `parse_double` | 75 of 613 |
| Decode `canada` | PyO3 float construction | 74 of 613 |

The ordinary encoder still creates its final Python bytes from its completed
Rust buffer. The `PyBytes::new` samples include allocation and copying; they
do not isolate copying from allocation. The general container-output copy
is not removed by this PR.

`DictScalarCursor::next` includes primitive formatting and key handling, not
just iteration. Its 226 `otfcc` samples overlap 162 in `try_write_entry` and
53 in `lookup_entry`. A further change must reduce actual entry handling,
not merely rename or inline the same work.

Canada also spends samples creating empty lists and growing them. The new
spare-capacity append does not eliminate CPython growth or Python float
objects. Faster digit conversion alone would leave those operations intact.

## Long plain strings

The input is a 147,458-byte JSON string from the maintained string suite.
Final has 576 operation samples: 201 leaf samples in Rust's UTF-8 validation,
265 inclusive samples in `string_prefix`, and 97 in `new_ascii_string`.
The ASCII-classification shortcut removes a redundant check during Python
string construction; it does not remove JSON scanning or UTF-8 validation.

Separate uninstrumented timings, **microseconds per complete call; lower is
better**. The reference observations belong to each named comparison.

| Comparison | Previous jsonmodem | Final | orjson measured with Final |
| --- | ---: | ---: | ---: |
| Original binary | 22.111 | **17.105** | 96.005 |
| Unchanged-source rebuild | 22.329 | **17.090** | 94.827 |

This case was already faster than orjson. It is not evidence of an overall
lead, nor does one profile establish why earlier byte-identical files gave
different timings.

## Late syntax errors

The Final recording contains 445 operation samples and reports 130 sampling
errors. The errors make function proportions unreliable. Among the recorded
stacks, 218 include `Decoder::validate_without_values`, 127 include the
scanner's `peek`, and 63 include `json_decode_error`. These observations
confirm that validation and exception construction run; they do not quantify
their shares of the full operation or explain the speedup by themselves.

The allocation measurements independently show the effect of not constructing
Python values for the invalid document: 29 allocation requests instead of
262,083 for the 1 MiB case. orjson records 28. Those counts are allocations,
not sampled stacks, and come from separate Memray runs.

## Remaining questions

The largest maintained relative gap is decoding unique escaped keys. It
still takes 143.339 us versus orjson's 36.870 us in the Original comparison.
The large-document profiles show key and dictionary work, but do not by
themselves establish which change would fix this separate fixture. Any new
key-cache experiment must include unique keys, changing documents and RSS,
not just repeated-key examples.

Depth-limit rejection also remains slow: 30.864 us versus 3.912 us for 1,025
nested arrays. This fixture was not CPU-profiled here. Source inspection
shows the decoder constructs the permitted outer lists before rejecting
the next opening bracket. A future shortcut would need to preserve UTF-8
error precedence and the exact depth boundary. Test depths 1,023, 1,024 and
1,025, whitespace variants, malformed endings and the complete valid-input
suites before accepting it. A smaller allocation count alone would not
establish a speedup.

Earlier unchanged builds and byte-identical extension copies produced
repeatable timing differences with no established cause. These profiles do
not resolve that observation. A causal claim would need controlled changes
to one suspected cost and repeatable improvements against both controls;
compiler or file identity alone is not an explanation.
