# Python acceleration evidence

The implementation starts from jsonmodem commit
`70638485a81064da41167163681c5fcde265f4bc`. Retain the refined fixed-timezone
cache with default-enabled, optional execution. Native tests, six actual-cache
Miri configurations, timings, streaming controls and memory measurements are
complete. Publication and final-commit CI remain outstanding.

## Implementation

`compat/fixed_offsets.rs` contains only safe Rust and owns at most eight
timezone references per encoding call. It admits exact built-in timezones,
`timedelta` offsets and string names. Custom callbacks and string finalizers
keep their existing behavior. The refinement skips root datetimes, stops after
sixteen consecutive misses, and avoids rebuilding unused portable key helpers.

The default-enabled `python-acceleration` Cargo feature controls this additional
work. `jsonmodem.portable.dumps` disables it for one call even when the feature
is compiled in. Existing Rust parser, input validation and output ownership
implementations are unchanged. No handwritten unsafe operation was added.

## Native validation

Tests use CPython 3.12.13 and Rust 1.94.1. Pinned formatting, whitespace checks,
the standard core checks, all four core feature combinations and fuzz-target
compilation pass. The unchanged base passed 15,945 Python tests and six subtests.

| Refined-cache check | Result |
| --- | --- |
| Default build | 16,043 tests and six subtests passed |
| Forced-portable calls | 16,043 tests and six subtests passed |
| Feature-disabled build | 16,043 tests and six subtests passed |
| Debug allocator | 300 tests passed |
| AddressSanitizer | 16,040 tests and six subtests passed; three skipped |
| Portable AddressSanitizer subset | 812 tests passed |

The ASan symbol check and deliberate invalid-read control both passed. The
three skipped address-space-limit tests passed without ASan; ASan needs a large
shadow-memory mapping. Other existing low-memory fixtures adjust their limits
or sizes under ASan. Leak detection was disabled, and CPython itself was not
rebuilt with ASan. Debug allocator checks are not a debug-interpreter build.

The initial cache's eight tests and the rejected buffer's twelve tests passed
under both Miri borrow models with three execution seeds each. Reused build
metadata initially made the buffer run zero tests. The count check rejected
that attempt, and a fresh target directory ran all twelve tests. The refinement
also passed all eleven tests in each of the six configurations. Miri checks the
actual extracted Rust components, not PyO3 or CPython FFI.

## Performance decision

The [complete report](../../crates/jsonmodem-py/benchmarks/PYTHON_ACCELERATION.md)
contains absolute times, every case, paired controls, allocation counts and RSS.
The selected cache takes 75.151 us across 275 comparable cases, versus
76.275 us for PR #7 and 54.897 us for orjson 3.11.9. This is a 1.5% improvement
over PR #7, with a 36.9% remaining time gap against orjson.

Retain it for its repeated-timezone benefit: 1,024 dates with one owner take
96.322 us instead of 135.731 us. Root datetime time is 1.072 us versus 1.056 us.
The miss limit reduces the initial cache's longer-list regressions, but sixteen
dates with 64 owners still take 4.492 us versus 3.517 us. Portable calls avoid
caching, without promising identical machine code or timing to PR #7.

The wider regressions remain visible. `otfcc` encoding takes 12.5% longer and
loses in all three process orders; its cause is unresolved. Unicode-escape
decoding and sixteen-field dataclass encoding also regress. The 45-case
incremental mean is effectively unchanged at 604.744 us versus 605.306 us;
individual cases lose up to 8.2%. No Rust-parser speedup is claimed.

All seven Memray fixtures have the same allocation counts and byte totals as
PR #7 in both selected and portable modes. Root datetime allocations return to
157 across thirty calls, down from the initial cache's 217. orjson has lower
process RSS in all seven separately measured fixtures. These observations,
bounded ownership, repeated-date gains and explicit per-call opt-out justify
retaining the cache; they do not establish a universal performance improvement.

## Rejected buffer experiment

Microseconds per call, lower is better. This is the equal-case geometric mean
of per-case medians across three process orders and 275 comparable cases.
Three unequal-output date cases are excluded and preserved separately. These
are initial-candidate results, not measurements of the refined cache.

| Unchanged base | Initial cache | Inline buffer | orjson 3.11.9 |
| ---: | ---: | ---: | ---: |
| 75.505 | 74.001 | 78.644 | **54.698** |

Reject the inline buffer: it takes 4.2% longer overall and also loses on the
tiny-call and larger-output groups. Its losses remain above 2% in all three
orders after comparing each run with its paired orjson control. Some output
sizes improve, but they do not satisfy the experiment's acceptance rule.

The inline buffer reduces allocation requests for some outputs but fails its
performance acceptance rule. It is not part of the implementation.
orjson 3.12.0 is unmeasured.
