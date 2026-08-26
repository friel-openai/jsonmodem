# Memory-safety test evidence


This record supports `plan.md`. Rust Miri checks passed, and the Python tests
found two callback-related input ownership defects. Both fixes have regression
tests and native sanitizer validation. The sections below retain the initial
questions, failed attempts, and final evidence.

## Baseline and independence


On 2026-08-26, fetching `upstream/main` selected
`47a542760f84dd402cecda6476b56dc92dae54e5`, titled
`[codex] simplify python streaming api (#72)`. Branch
`dev/friel/memory-safety-tests` starts at that exact commit.

The existing frontend branch was at
`456eec582a6958e40fffa301469570468d2a3f02`. Comparing the relevant files showed no
change to `.github/workflows/miri.yml`, `.config/nextest.toml`, or
`crates/jsonmodem/src/backend/std/value_zipper.rs`. The scanner difference changes
numeric accumulation, not the four unchecked UTF-8 conversions. Python buffer
code exists upstream, although PR #1 also modifies `lib.rs`. Conclusion: the
planned test infrastructure and upstream streaming tests do not require PR #1.

The original checkout had uncommitted README and performance-record changes and
an active security-audit plan. Those files were not modified by this setup.

## Observed coverage gaps


`.github/workflows/miri.yml` runs:

    cargo +nightly miri nextest run --workspace --profile default-miri --exclude jsonmodem-fuzz --exclude jsonmodem-py

`crates/jsonmodem/tests/jsonmodem_values/mod.rs` and
`crates/jsonmodem/tests/jsonmodem_buffers/mod.rs` disable their test modules under
Miri because snapshot rendering accesses the filesystem. Other values and
buffers regression cases remain enabled; do not describe all adapter tests as
excluded.

`crates/jsonmodem/src/tests/property_partition.rs` and
`crates/jsonmodem/src/tests/property_multivalue.rs` request ten cases under Miri,
10,000 in ordinary CI, and 1,000 locally unless fast mode is selected.
ValueZipper has no dedicated unit-test module at this base.

The previously inspected Miri job for PR #1 reported 181 passed and four skipped:
https://github.com/friel-openai/jsonmodem/actions/runs/32927577857/job/98053439599
That is historical evidence for PR #1, not a test run of this independent branch.
The excluded Python crate and compiled-out tests are not counted among the four
skipped tests.

## Initial unsafe-operation inventory


In `crates/jsonmodem/src/parser/scanner/mod.rs`, unchecked UTF-8 conversions are
at base lines 340, 605, 632, and 655. The required assumption is that each selected
byte range is valid UTF-8. Map the functions and enforcing callers before adding
test-only validation and split-input tests.

In `crates/jsonmodem/src/backend/std/value_zipper.rs`, unsafe reference creation
or pointer dereferences occur at base lines 62, 70, 91, 115, and 124. Review
`with_leaf_mut`, `with_leaf`, `align_path`, and `current_ptr` together with
`descend_one`. Test pointer validity when arrays or maps grow and old descendants
are discarded. Tests must respect, or explicitly test enforcement of, the
one-level depth transition assumption.

In `crates/jsonmodem-py/src/lib.rs`, inspect the Python object operations at base
lines 184, 316, 373, and 798 and all buffer operations near lines 3689-3834.
Name each reference ownership rule, successful acquisition/release pair, and
error cleanup rule. `with_buffer_text` and `with_readonly_byte_text` construct
slices from exporter-supplied pointers and lengths. Negative lengths and some
read-only/layout conditions are checked; these checks alone do not establish
allocation validity. This inventory identifies review work, not confirmed bugs.

## Tool assumptions


The [Miri documentation](https://github.com/rust-lang/miri) describes default
Stacked Borrows checks, optional Tree Borrows, execution seeds, and explicit
environment forwarding under isolation. It also explains that most foreign
function calls are unsupported and that a passing run is not proof of soundness.
Consulted 2026-08-26. Record the installed nightly before choosing final flags.

The [Rust sanitizer documentation](https://doc.rust-lang.org/unstable-book/compiler-flags/sanitizer.html)
describes native instrumentation. The extension build and compatible runtime
still need to be demonstrated. Do not label ordinary Python tests as sanitizer
coverage or assume CPython is instrumented because the Rust extension is.

## First planned attempt


Question: which safety assumptions have no direct executed test on upstream?
Method: finish the function-level inventory, run the existing focused scanner
tests, and capture actual Miri test names. No runtime code changes in this step.
Expected evidence: a named test or an explicit omission for every unsafe
operation in the three source files, plus baseline command results.
Decision rule: add tests for missing cases before considering production edits;
preserve a failing input if a check finds a defect.

Next action: complete the inventory and run
`cargo test -p jsonmodem --lib parser::scanner::tests` from this worktree.

## Rust baseline and direct tests


The unmodified scanner suite passed 27 tests and the unmodified Python suite
passed 27 tests. The initial six new Rust unit tests passed normally. All three
new ValueZipper tests also passed under Miri's default reference model. Toolchain:
`rustc 1.100.0-nightly (e7769602a 2026-08-24)`, LLVM 23.1.0. Miri and rust-src were
installed for that existing nightly toolchain.

No production defect was demonstrated by those direct tests. Four test/Miri-only
UTF-8 assertions were added before the scanner's unchecked conversions. A
should-panic test passes invalid bytes to the private ASCII append helper and
confirms failure before unchecked conversion. Release builds without Miri do not
include those assertions.

The new integration test required an explicit Cargo test target because this
crate disables automatic test discovery. It has now been registered; compiling
a file without registering its test target would not count as coverage.

## Native memory checker experiment


Question: can the Rust extension and Python entry point share the exact same
AddressSanitizer runtime? The installed Rust nightly supplies its static runtime,
not a matching Clang shared library. Build a small test-only Rust executable
with AddressSanitizer that calls CPython's `Py_BytesMain`, then load the extension
built with the same nightly and sanitizer flags. Use a separate installed wheel
and virtual environment, not an editable build that would replace the regular
extension in the source tree. CPython itself remains uninstrumented.

Decision rule: retain this arrangement only if a separately loaded, deliberately
bad Rust test library produces an AddressSanitizer error in a subprocess and the
real extension imports and runs normally. Keep deliberate bad code in the test
tooling only, never the production extension. Record failures without claiming
instrumentation coverage until this check works.

Result: the launcher detected the deliberate heap-buffer-overflow and the
instrumented extension passed the then-current 46 Python tests. A second run
also verified an `__asan_init` reference in the installed extension and passed
46 tests. Four more tests have since been added for byte mutations, buffer
layouts, retained exporter ownership, and failed export. Final rerun pending.

CPython and the prebuilt Rust standard library are not instrumented. Leak
detection is explicitly disabled for CPython shutdown allocations. The checked
properties include actual access checks in the extension and explicit buffer
release assertions; no general leak-freedom claim is made.

## Function-level inventory and enforcement


Scanner `finish`, `switch_to_owned_prefix_if_needed`, and
`copy_prefix_to_scratch`: input comes from a Rust string, and the anchor/cursor
must be at character boundaries. `memory_safety_prefix_copy_operations` forces
each copy with ASCII and two-, three-, and four-byte characters. Each unchecked
conversion now has an active test/Miri assertion. `push_ascii_to_scratch` relies
on callers selecting ASCII; `memory_safety_owned_ascii_and_raw_captures` and the
intentional assertion-failure test exercise both storage variants and rejection.

ValueZipper `with_leaf_mut` and `with_leaf`: the raw pointer was just obtained
from the live leaf; borrowing the separate path vector cannot move that leaf.
Returned references borrow the zipper. `align_path` has three raw dereferences:
descent from the current node, descent after discarding a sibling pointer, and
returning the current pointer. The direct array/map/replacement tests exercise
all three. `take_root` clears cached pointers before moving the root. The
integration tests exercise these operations through actual parser sequences.

Python `build_view_event`, `build_path_tuple`, `build_path_tuple_for_event`, and
`PyPathView::tuple_range_object`: each tuple starts private and empty; indices
are bounded by its size. `PyTuple_SetItem` takes ownership of one reference per
slot. Failure decrements the partly built tuple. Successful pointers are
converted to an owned PyO3 reference once. Nested retained events, path slicing,
`as_tuple`, and byte-view tests exercise successful construction and ownership.
OOM failure at each individual allocation is not injected; those branches were
reviewed, not executed deliberately.

Python `supports_buffer_protocol`, `with_buffer_text`, and
`with_readonly_byte_text`: GetBuffer receives a live Python object under the
interpreter lock and a correctly initialized C-layout descriptor. Error clearing
occurs with that lock held after failed acquisition. `PyBufferGuard::drop`
releases successful exports with non-null owners. Slice construction requires a
live readable allocation of the reported nonnegative length, and a buffer guard
outliving the slice. The exporter contract supplies allocation validity; metadata
checks cannot prove it. Tests cover empty buffers without dereferencing null,
valid storage, invalid UTF-8, writable/read-only restrictions, failed acquisition,
and matched releases. A returned memoryview retains an independent export after
the temporary guard is released. Native exporters that violate the CPython
contract remain outside tested guarantees. This paragraph describes the initial
review; the fixes below replace mutable borrows with snapshots and give unknown
read-only exporters snapshot-backed payloads.

`docs/memory-safety-testing.md` provides the durable user-facing inventory.

## Test cost and validation


The first exhaustive split-input test combined several features into long
documents and requested partial snapshots after every feed. The Miri run was
stopped before completion. It is not passing evidence. The test now uses short
documents for each feature and only final snapshots for comparisons. A separate
test checks partial snapshots. This keeps every valid split position while
avoiding redundant copying. Generated inputs still use 32 deterministic cases;
each grows an object with a nested array, and direct tests separately exercise
64-element arrays and 64-key maps.

`.agent/check.sh` passed build, Rust tests, Clippy, documentation, and the Miri-cfg
Clippy pass, then initially stopped because actionlint was not on PATH. Running
with `$HOME/go/bin` on PATH passed the entire script. This is ordinary test and
lint evidence, not Miri execution. The six new unit tests and four integration
tests also passed in release mode before the corpus was shortened. Final source
validation remains pending.

## Confirmed Python exporter reacquisition defect


Independent review identified a callback between UTF-8 validation and parsing:
`with_readonly_byte_text` acquires the input once to obtain text, then calls
`PyMemoryView::from(data)` to obtain payload storage. Python 3.12 buffer exporters
can return different storage or mutate their storage during that second call.
The earlier input classification also acquires an export, making the unsafe
reacquisition the third Python callback in a normal single-input feed.

The reviewer reproduced mutation to invalid UTF-8 in an isolated sanitizer
process. ASan did not report it: it checks allocation access, not UTF-8 validity.
A non-UB regression is being added before the fix: return immutable
`b'["first"]'` for the first two acquisitions and `b'["second"]'` for the third.
Current parsing yields a string payload `b'secon'`, combining a range from the
first export with storage from the second. Expected result after the fix is
`b'first'` from one retained export.

Next action: run this regression against the baseline extension, then ensure
parsing and returned memoryviews share the exact same acquired storage. Review
whether GC callbacks can mutate other accepted backing storage during parsing
before deciding whether additional snapshots are required.

The safe regression failed on the baseline extension exactly as expected:
`b'secon' != b'first'`. Test-infrastructure commit `7883dad` retains this failing
regression before any production fix.

The reviewer also reproduced synchronous GC mutation on Python 3.9.25. A
`gc.callbacks` function changed one ASCII byte only when reading
`parser.is_finished` raised PyO3's mutable-borrow error, proving the callback ran
inside `feed`. The parsed last string changed from `abc` to `abz`. The primary
agent independently reproduced the safe ASCII case with
`target/memory-baseline-py39/bin/python scripts/gc_buffer_regression.py`: nine
callbacks ran inside feed and the unchanged-text assertion failed. No such
callback ran inside feed in the reviewer's 3.12/3.13 tests. The regression is a
subprocess so global GC settings and any interpreter fault remain isolated.

The fix snapshots mutable or unverifiable ordinary buffer input before Python
allocations can run callbacks. Exact bytes-backed memoryviews remain borrowed,
as does the existing bytes fast case. Byte-view parsing first acquires the
retained memoryview, then inspects that exact export. Unknown read-only exporters
are copied to immutable bytes before parsing; their payloads retain that copy.
This preserves acceptance of valid exporters without promising no-copy access to
unverifiable storage. Direct mutable memoryviews remain rejected in byte-view mode.

## Buffer-fix performance experiment


Question: how much do immutable-owner checking and required snapshots cost for
chunked streaming input? Baseline: a release wheel built from the production
code at `7883dad`, installed separately in `target/memory-benchmark-baseline`.
Candidate: this worktree's ordinary release extension. Use the public
`make_array_strings(1024)` workload and event loop from
`benchmarks/bench_jiter_chunked.py`, with 512-byte chunks. Compare bytes,
bytearray, bytes-backed memoryviews, and byte-view mode with bytes and a Python
read-only exporter. Run both interpreters alternately for seven pairs, recording
time per complete stream. Use Memray native allocation tracking separately for
100 streams; record allocation counts and peak tracked bytes. No orjson result
is needed for this safety-only comparison.

Decision rule: bytes must retain its no-copy behavior; measure any regression
and reduce avoidable copies or callback work without removing required ownership.
Do not interpret shared-host timings as a release performance guarantee. Keep
generated timing/allocation artifacts outside tracked files. Next action: run
the paired baseline/candidate experiment after regression tests pass.

## Final measurements


The first measurement found avoidable allocations from repeatedly constructing
the Python attribute name `obj`. The fix now interns that name and reads a
byte-view owner's attribute only once. This removed those per-chunk allocations
without weakening the ownership checks.

The reproducible comparison is now
`crates/jsonmodem-py/benchmarks/bench_buffer_inputs.py`. Command:

    .venv/bin/python crates/jsonmodem-py/benchmarks/bench_buffer_inputs.py --baseline-python target/memory-benchmark-baseline/bin/python --candidate-python .venv/bin/python

The baseline release wheel contains production code from `7883dad`; the candidate
contains the buffer fixes and interned attribute name committed in
`2e61d8fabc0930bed8323e10124b1e197a099280`. Both used CPython 3.12.13,
Rust 1.94.1, and Memray 1.20.0 on the same shared Linux x86_64 host, without CPU
pinning. Seven paired timing measurements alternate execution order. Each is
the median of three measurements of 200 streams. Each stream contains 1,024
strings, 7,169 input bytes, 15 chunks, and 1,034 emitted events. All event counts
matched. Memray runs are separate from timing, with 100 streams after ten warmups.

| Input/mode | Baseline us/stream | Fixed us/stream | Median paired fixed/baseline | Paired ratio range |
| --- | ---: | ---: | ---: | --- |
| bytes, ordinary events | 365.25 | 354.69 | 0.970 | 0.955-1.024 |
| bytearray, ordinary events | 366.36 | 365.86 | 0.986 | 0.960-1.054 |
| bytes-backed memoryview, ordinary events | 366.70 | 358.04 | 0.981 | 0.904-0.994 |
| bytes, byte-view events | 535.55 | 532.71 | 1.001 | 0.938-1.021 |
| Python exporter, byte-view events | 544.51 | 551.24 | 1.003 | 0.961-1.054 |

Ratios near one indicate similar timings, not proof of zero overhead. Variation
on this shared host does not support a general speedup claim. The bytes fast
case was not changed by the ownership fix.

| Input/mode | Baseline allocations/stream | Fixed allocations/stream | Baseline peak tracked bytes | Fixed peak tracked bytes |
| --- | ---: | ---: | ---: | ---: |
| bytes, ordinary events | 2921.46 | 2921.46 | 11164 | 11164 |
| bytearray, ordinary events | 2921.07 | 2936.07 | 8644 | 9084 |
| bytes-backed memoryview, ordinary events | 2921.07 | 2921.07 | 8644 | 8644 |
| bytes, byte-view events | 5144.07 | 5144.07 | 2902027 | 2902027 |
| Python exporter, byte-view events | 5339.07 | 5339.07 | 2902515 | 2904596 |

These counts use native and Python allocator tracing and exclude free/unmap
records. Bytearray input adds exactly one snapshot allocation per chunk. The
Python exporter needs a snapshot but avoids reacquiring another export, leaving
the measured allocation count unchanged. Peak tracked memory is not RSS.
No claim about orjson performance follows from this safety-fix comparison.

## Final validation


`cargo +nightly miri nextest run --workspace --profile default-miri --exclude
jsonmodem-fuzz --exclude jsonmodem-py` with an explicitly forwarded 32-case setting
passed 188 tests, with four ignored debug helpers, in 242.313 seconds. Snapshot
tests compiled out under Miri and excluded crates are additional omissions.

`bash .agent/check-miri.sh targeted` passed all six configurations: Stacked
Borrows and Tree Borrows, each with execution seeds 0, 1, and 2. Every configuration
ran six unit tests and four integration tests, including 32 generated cases.
Unit tests took about 8.5 seconds; integration tests took about 98.5 seconds.
These results validate the final Rust test behavior; subsequent source edits
were limited to Python buffer handling, comments, and equivalent formatting.

The ordinary Rust check script, release-mode safety tests, Python build/tests,
and Python Clippy check passed. The default check script still does not run Miri
unless requested; the actual Miri runs above provide that evidence separately.

Native checks passed the required deliberate heap-buffer-overflow detection and
then verified the installed extension's sanitizer symbol. Python 3.9.25 passed
47 tests, skipping five Python-defined-exporter cases that require 3.12. Its GC
regression exercised callbacks inside feed. The final Python 3.13.14 rerun passed
52 tests. Both interpreter runs include the final attribute-name allocation
change. Python 3.9 skips only the five tests requiring Python 3.12 buffer methods.

An independent source review found the two Python defects, then reviewed the
fixes and found both closed. It found no additional defect in the launcher,
instrumentation verification, or Rust tests. The source-review conclusion is
separate from actual test results and does not remove the documented limitations.

Final source commit: `2e61d8fabc0930bed8323e10124b1e197a099280`. The original PR's
commits are not ancestors of this branch. No new PR or hosted CI run was
requested. The workflow definitions passed actionlint; their commands were
executed locally as recorded above. Next action: publication only if requested.
