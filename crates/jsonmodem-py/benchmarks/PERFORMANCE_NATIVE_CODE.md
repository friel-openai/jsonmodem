# Native-code checks for two regressions

The final build is slower on long plain-string decoding and syntax errors at
the start of large inputs. Comparing the saved binaries rules out two simple
explanations: these cases do not select a different UTF-8 validator, and an
error at byte zero does not run the new character-count loop. The validator's
instructions moved within the binary. Whether that placement affects speed
remains untested.

This comparison uses the measured final build, `b0f3190`, and the unchanged
PR #3 rebuild, `b7fe329`. The [binary evidence](data/final-profiles-2026-08-30/native-code.json)
records their full revisions, native-file hashes, instruction ranges and call
targets. LLVM 21.1.8 supplied disassembly and ELF metadata. No library was
executed or modified for this analysis. The [timing results](PERFORMANCE_36H.md)
are unchanged.

## The same scanning instructions

For the all-ASCII inputs, `decode_bytes` selects Rust's `from_utf8` in both
builds. Its test of the first 32 bytes is unchanged. The complete 503-byte
validator differs only in an instruction's address operand; the referenced
256-byte UTF-8 width table is identical.

The validator's ASCII loop contains 23 bytes of identical machine code and
reads 16 input bytes per iteration. In the rebuild it starts at `0x982c0`,
within one 64-byte block. In the final build it starts at `0x99c70` and crosses
the next 64-byte boundary. These are addresses within the shared library,
not addresses collected from a running process.

The separate JSON string scanner also retains its instructions. Its 134-byte
loop reads 32 input bytes at a time with two 128-bit SIMD loads. The quote,
backslash and control-byte constants match. The checked string-construction
code calls `PyUnicode_FromStringAndSize` in both builds. The sampled
`PyString::new` frame is an inlined wrapper, not an extra function call.

Two earlier normal builds from the same `75a445d` source provide another
observation. Before the error-position change, the 1 MiB early-error case
took 107.609 microseconds in the original build and 126.988 in its rebuild.
The rebuild was slower in all eight process pairs. Their identical ASCII
loops start at offsets 32 and 48 within a 64-byte block, respectively; only
the slower build's loop crosses the boundary. Other code, data placement and
process state were not held equal. This repeats an association, not a test
that isolates loop placement.

## An early error does not count the whole document

The new [`Decoder::error`](../src/compat.rs#L81) checks the error offset before
counting characters. At offset zero, the compiled branch sets the position
to zero and skips both counting loops. The older function examines the first
character and stops. The new function has a different prologue and is larger,
but it does not add a scan of the document in this case.

The 1,397-byte [`json_decode_error`](../src/lib.rs#L53) function differs only
in 41 checked address operands. The imported Python function names and their
call offsets match, including construction of the message, document string
and position, followed by `PyObject_Vectorcall`. Both builds still validate
the full input before parsing and create the exception's full document string
afterward. Those costs remain even when the first byte is invalid JSON.

## What the identical-file control establishes

An earlier control found different small-dictionary encoding times between
two byte-identical native files. Swapping which file each fixed pathname
referred to, then restoring the names, kept the advantage with the original
file in all 18 process pairs. Different on-disk instructions or loop offsets
cannot explain that particular discrepancy. The cause is unknown.

A later control that reused one fixed file did not reproduce the persistent
difference. Neither control used the long-string or early-error input above.
They do not explain those regressions or justify discarding them.

## Tests that would distinguish the explanations

These tests have not been run:

1. Compare the same long ASCII document as `bytes` and `str`, alternating the
   two builds in fresh processes. Exact Python `str` input skips this Rust
   UTF-8 validator. A regression for `str` would identify a difference that
   does not require this validator. The two entry routes can have different
   causes, so that result alone would not explain or rule out the `bytes` gap.
2. Compare builds with only the validator's placement changed. Verify its
   instructions, constants and surrounding hot code, rather than assuming a
   compiler flag changes nothing else. If the timing gap does not follow
   placement, or persists after matching placement, placement is not a
   sufficient explanation. Moving the earlier loop to the crossing position
   provides the reverse test.
3. Repeat the byte-identical-file comparison with these exact inputs. A
   repeatable gap would show that differing on-disk loop offsets cannot explain
   all variation for these inputs. It would still leave the runtime cause open.

The binary checks cover the named functions and instruction ranges, not their
entire call graph. ELF imports identify requested symbols, not live resolved
pointers. No hardware counters, input addresses or runtime mappings were
collected. The existing CPU samples identify work to investigate; they do not
measure separate function times or establish the cause of either regression.
