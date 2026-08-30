# What profiling changed

Native `py-spy` recordings and LLVM disassembly guided the changes below.
The retained changes are in [jsonmodem b0f3190](https://github.com/friel-openai/jsonmodem/tree/b0f3190fb72af0396d9d25256f8d0174efd7ae23).
These recordings predate that combined build. They explain the changes;
they are not measurements of that build's speed.

## Changes informed by profiles

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

## Remaining costs

Earlier decoder recordings identified Python string construction,
dictionary-key lookup, and list insertion. Cache and batching prototypes
regressed other cases and were not retained. These costs warrant another
profile of the final build, not an assumption that more caching will help.

After the NumPy byte-buffer change, large-array profiles still showed calendar
conversion and per-timestamp appends. The final Python bytes allocation and
copy appeared in only 1-2% of operation samples. Small arrays instead showed
repeated helper imports, metadata checks, and snapshot creation. These
observations precede the digit-pair change; a follow-up must recheck the costs
and preserve owning snapshots and validation.

The error-position follow-up suggests that `JSONDecodeError.__init__`,
including its newline count, is worth investigating. However, that sampler
wrote its recording and then exited with `ECHILD`: it could not collect a
successful child-process exit status. This is diagnostic evidence, not a
successful profiling run or proof of the final build's bottleneck. An earlier
failed attempt produced no recording. Neither failure counts as a passing run.

Final timing also found slower early-error and large-depth rejection. A
separate non-PGO rebuild of the preceding combined source had already shown
the same slower pattern, before the error-position change. These inputs never
reach the changed escape decoder, and their error positions are zero or
1,024. Full-input UTF-8 validation in `decode_bytes` and Python source-string
creation in `json_decode_error` are useful profiling targets. Neither is an
established cause of the regression; source inspection adds no new full-input
operation on those cases. The final report retains the losses.

## Limits

Samples were recorded in Speedscope format. Counts describe overlapping
stacks, not additive function times or throughput. Some native symbols were
unresolved. Higher-rate NumPy recordings had lag or shutdown failures; the
successful 19 Hz recordings support the attribution above instead.

CPU affinity was controlled, but the machine was not exclusive and CPU
frequency was not fixed. Hardware performance counters were unavailable.
ASLR and system-wide settings were not changed. Differences between unchanged
builds remain unexplained; neither compiler behavior nor shared-library file
identity was proved to cause them. Performance claims must use the separate
unprofiled comparisons.
