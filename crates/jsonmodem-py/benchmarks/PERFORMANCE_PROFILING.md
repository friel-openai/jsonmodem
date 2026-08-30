# What profiling found

Native `py-spy` recordings and LLVM disassembly guided the changes in
[jsonmodem b0f3190](https://github.com/friel-openai/jsonmodem/tree/b0f3190fb72af0396d9d25256f8d0174efd7ae23).
Separate CPU and allocation profiles check that final build's remaining
costs. Profiles identify work to investigate; the [unprofiled benchmarks](PERFORMANCE_36H.md)
measure speed.

## Changes guided by earlier profiles

Completed recordings and `llvm-objdump` output showed an empty-prefix copy
call and an unnecessary plain-text scan between consecutive JSON escapes.
`DocumentReader::string_escaped` now skips those operations when there is no
intervening text. It keeps the existing escape decoder and checked reads.

Most sampled Python date/time serialization stacks passed through the Python
`datetime_text` helper. This prompted a checked Rust formatter with an
initialized byte buffer for exact supported types, including built-in
fixed-offset timezones. Subclasses and custom timezones retain their existing
handling. The three original date recordings completed with 1, 1, and 11
sampling errors; the fixed-offset recording had none.

Successful lower-rate NumPy recordings identified repeated general-purpose
Rust formatting. A fixed byte buffer replaced that formatting. Subsequent
recordings still identified `two_digits` as substantial work, prompting the
checked digit-pair lookup. Calendar and range checks remain.

A completed recording of an unfinished string found the per-character error
position calculation in 647 of 997 operation samples. `Decoder::error` now
uses Rust's bulk character count on a checked prefix. It retains the old
calculation for offsets that split a character or exceed the input. Separate
Memray comparisons found no allocation reduction from this change.

## Final-build CPU profiles

The follow-up uses `py-spy` 0.4.2 with a requested rate of 19 samples per
second, CPython 3.12.13 and CPU 16. Each worker performs ten warmups, disables cyclic GC during a
32-second loop, and releases results inside that loop. It compares the final
build, orjson 3.11.9, and selected cases from the unchanged PR #3 rebuild.
The [profile data](data/final-profiles-2026-08-30/cpu.json) includes every
completed recording, sampling-error count and failed attempt.

A sample records the functions active at one instant. The counts below
describe samples containing a function or a function it called. Counts can
overlap; they are not separate function times or predicted speedups.

- **Object decoding:** `twitter` has 590 operation samples. `Decoder::key`
  appears in 111, PyO3 string construction in 105, and dictionary insertion
  in 88. Key lookup and Python object construction remain substantial work.
- **Object encoding:** `twitter` has 575 operation samples. The owning PyO3
  dictionary iterator appears in 135, `Encoder::key` in 94, and string
  scanning in 82. Avoiding iterator work must not weaken ownership or
  callback-mutation handling.
- **Number encoding:** `canada` has 670 operation samples. zmij's float
  formatter appears in 355; `Encoder::extend<false>` appears in 87.
  `zmij::Buffer` is already an inline 24-byte array. Moving it into an encoder
  field would not remove a heap allocation per number. Formatting and output
  appends are the observed costs, not evidence that another buffer will win.
- **Number decoding:** `canada` has 621 operation samples, with list append
  in 135, `parse_double` in 93, and number-token scanning in 45. This capture
  reports six sampling errors. Decimal conversion is not the only cost.
- **Early errors:** rejecting a syntax error at the start of a 1 MiB input
  has 606 operation samples. `json_decode_error` appears in 405, Python
  string construction in 399, and Rust UTF-8 validation in 191. The first
  two overlap in 397 samples. Constructing the exception's source string
  still processes a large input after the early syntax error is known.

Long plain-string decoding also samples string scanning, Python string
construction and UTF-8 validation in both the final and unchanged builds.
One recording per build does not explain the measured regression. Earlier
rebuilds already showed slower early-error rejection before the error-position
change. The [timing report](PERFORMANCE_36H.md) retains those losses; neither
profiling nor source inspection establishes their cause.

## Final-build allocation profiles

Memray 1.20.0 records native stacks for `citm_catalog`, `twitter` and `mesh`,
both loads and dumps. Each library uses three fresh processes per case,
one tracked complete call after ten warmups, with cyclic GC disabled and
Python allocator tracing enabled. All 36 captures complete. Their request,
requested-byte and tracked-peak totals match the corresponding published
memory medians exactly, but these diagnostic captures do not replace that
[memory comparison](data/final-2026-08-30/MEMORY_PUBLIC.md) or its separate RSS measurements.

**Allocation requests per complete call; lower is better.** Bold marks the
smaller value. Each count is the median of three native captures; all three
observations agree.

| Public document and operation | jsonmodem | orjson 3.11.9 |
| --- | ---: | ---: |
| `citm_catalog` loads | 51,213 | **49,014** |
| `citm_catalog` dumps | 26 | **18** |
| `twitter` loads | 11,551 | **9,237** |
| `twitter` dumps | 27 | **17** |
| `mesh` loads | 74,385 | **74,104** |
| `mesh` dumps | 25 | **19** |

For `mesh` decoding, stacks through PyO3's integer conversion account for
34,654 requests; float construction accounts for 32,300. List append accounts
for 3,877 requests and 5,306,528 requested bytes, including the full size of
each reallocation. These counts agree in all three captures. The decoder
allocates Python values and grows their lists; a number-scanning optimization
alone would not remove that work.

Encoding the same document makes only 25 requests, not one per number.
The stacks include output-vector growth and the final Python bytes allocation.
This supports investigating formatting and copying rather than assuming a
heap allocation for every temporary number buffer. The [allocation data](data/final-profiles-2026-08-30/native-allocations.json)
retains full stack groups and counts for both libraries. Individual function
counts overlap and must not be summed; each allocation belongs to one full
stack group.

## Further experiments

These are questions for another measured change, not additional retained code:

- Test whether the existing SIMD UTF-8 validator helps large ASCII inputs,
  while keeping small, non-ASCII and invalid-input controls. The current
  selection already uses SIMD for long inputs with early non-ASCII bytes.
- Separate dictionary iteration from escaping costs while preserving owned
  references and callback behavior. Earlier cache and borrowing prototypes
  remain [rejected](PERFORMANCE_EXPERIMENTS.md).
- Any new number-output design must address the measured formatting or append
  costs and beat the earlier [staging-buffer experiments](OUTPUT_BUFFERS.md).
  Reusing zmij's stack buffer is not an allocation reduction by itself.

The earlier NumPy recordings also suggest calendar conversion, repeated
helper imports and snapshot creation as targets. They predate the final
digit-pair change, so those costs need a fresh profile before another change.
Owning snapshots and calendar checks must remain.

## Limits

Eighteen of the twenty planned CPU recordings complete with independently
collected sampler and workload exit statuses of zero. Fifteen report no
sampling errors.
Final `citm_catalog` dumps reports two, final `canada` loads six, and orjson
`canada` dumps 160. The underlying sampling-error messages are unavailable.
The orjson `canada` dumps recording is unsuitable for comparing function costs.

The final late-error sampler saves data, then exits unsuccessfully with
`ECHILD`; its workload is independently collected with exit zero. The saved
data remains a failed diagnostic, and the planned orjson late-error recording
is not run. An earlier denied attachment and earlier NumPy/error-profile
failures are also retained, not counted as successful recordings.

The orjson wheel provides no C/Rust source attribution in the CPU samples.
Some CPython executable labels are implausible; precise claims above use
verifiable source-qualified callers instead. A successful sampler exit or
nonempty native stack does not prove that every frame is resolved correctly.

The first native-Memray attempt stops because its strict stderr check rejects
warnings about correcting malloc/free function addresses. That attempt remains
failed. A separate run accepts only the source-reviewed correction messages from
the pinned Memray build, retaining the raw warnings. All 36 captures emit that
pair; other diagnostics and nonzero exits remain errors. Hook correction is
not proof that every allocation or native frame was captured correctly.

CPU affinity was controlled, but the machine was not exclusive and CPU
frequency was not fixed. Hardware performance counters were unavailable.
ASLR and system-wide settings were not changed. Differences between unchanged
builds remain unexplained; neither compiler behavior nor shared-library file
identity was proved to cause them. Performance claims must use the separate
unprofiled comparisons.
