# Output-buffer experiments

Neither tested approach improved integer serialization. Both production
changes were removed. The encoder still uses `itoa` and appends its formatted
bytes to the existing output `Vec`. The patches below are saved experiments,
not part of the package build.

The baseline is [0f61cd5](https://github.com/friel-openai/jsonmodem/commit/0f61cd5d1e4b014357f66d68de2b3bc51feb6b11).
These experiments follow the small-output-copy finding in [PROFILE.md](PROFILE.md).
That profile identified where time was spent; it did not establish that another
buffer would reduce elapsed time.

## Candidates

- [Staging](output-staging.patch): collect small writes in a 512-byte array
  inside the encoder, then flush the array to the output Vec. Numbers and their
  separators share the array. Large writes bypass it after pending bytes are
  flushed. Indentation and cached-key copies also flush pending bytes.
- [Direct, two digits](output-direct.patch): count an integer's decimal digits,
  extend the output Vec with initialized bytes, then fill those bytes backwards
  using pairs of decimal digits. This removes the formatting-buffer copy but
  adds digit counting and output initialization.
- [Direct, four digits](output-direct4.patch): the same direct writer, processing
  four digits per division instead of two. This tests grouping closer to
  `itoa` 1.0.15 rather than attributing every difference to the removed copy.

All candidates use checked slice operations and add no handwritten `unsafe`
code. Each passed 513 binding tests and 71 [additional checks](test_output_buffers.py).
Those checks cover staging boundaries, powers of ten, signed and unsigned
limits, strict-integer errors, and 100,000 seeded random integers.

## Method

CPython 3.12.13, Rust 1.94.1, orjson 3.11.9, NumPy 2.5.2, AMD EPYC 7763,
release builds, CPU 0. No builds, tests or profilers ran during timing. This is
a shared host; all samples, including outliers, are retained.

Each comparison starts separate baseline and candidate processes using the
same Python interpreter and prebuilt packages. Seven process pairs alternate
which version runs first. Each process checks exact output against orjson,
then takes three measurements per library, alternating library order. A
measurement times many calls with identical counts, calibrated until the
slower library runs for at least 0.03 seconds. Process startup and input
construction are excluded. The JSON result includes individual samples,
package locations and reference-library versions.

Both libraries are called through a Python wrapper that supplies keyword
arguments. Its overhead matters for tiny inputs; do not compare these absolute
times directly with older benchmarks that call `dumps` without a wrapper.
Every operation here is complete-document `dumps`, not incremental parsing.

Short integer arrays contain -5,000 through 4,999. Full-width arrays contain
10,000 seeded values: signed integers from the full signed 64-bit range, or
unsigned integers from 2**63 through 2**64-1. The latter exercise unsigned
conversion after signed extraction fails. The tiny list is `[0, -1, 10, -100,
999]`; the scalar is `123456789`. Other inputs are defined in
[bench_output_buffers.py](bench_output_buffers.py). NumPy arrays have 25,000
rows of four consecutive whole numbers. The late callback input contains 100
strings of 256 bytes followed by an unsupported object, converted to `null`.

## First comparison

Ratios are candidate time divided by baseline time. A ratio of 1.25 means
25% longer. Each candidate has its own alternating baseline measurements.

| Workload | Staging | Direct, two digits | Direct, four digits |
| --- | ---: | ---: | ---: |
| small | 1.11 | 1.04 | 1.02 |
| medium | 1.15 | 1.05 | 1.03 |
| short integer array | 1.25 | 1.36 | 1.35 |
| float array | 1.08 | 1.00 | 1.00 |
| string array | 1.21 | 0.99 | 0.98 |
| escaped strings | 1.14 | 1.03 | 1.00 |
| long string | 1.03 | 0.96 | 1.00 |
| full-width signed integers | 1.16 | 1.33 | 1.30 |
| full-width unsigned integers | 1.06 | 1.09 | 1.07 |
| scalar integer | 1.10 | 1.09 | 1.09 |
| tiny integer list | 1.15 | 1.16 | 1.14 |
| indented integers | 1.63 | 1.36 | 1.34 |
| strict integers | 1.22 | 1.35 | 1.31 |
| sorted medium | 1.09 | 0.99 | 0.98 |
| integer keys | 1.13 | 1.02 | 1.02 |
| dataclasses | 1.01 | 1.02 | 1.02 |
| NumPy int64 | 0.99 | 1.00 | 1.00 |
| NumPy float32 | 1.00 | 1.00 | 1.00 |
| late default callback | 1.07 | 1.00 | 0.98 |

The unchanged NumPy formatter provides a useful comparison: its ratios stay
near 1.0. Small apparent gains in unrelated workloads do not justify slower
integer output. The four-digit run included a small-document ratio of 0.61
and a tiny-list ratio of 1.83; neither outlier was discarded.

## Repeated comparison

The repeats use eleven process pairs and at least 0.05 seconds per measurement,
with the same three measurements per library in each process. Ratios are
medians of individual comparisons, not quotients of separately reported
medians. Ranges below are the smallest and largest observed pair ratios,
not confidence intervals.

| Workload | Staging / baseline | Observed range | Direct four-digit / baseline | Observed range |
| --- | ---: | --- | ---: | --- |
| small | 1.125 | 1.050-1.146 | 1.011 | 0.984-1.044 |
| medium | 1.144 | 1.130-1.173 | 1.044 | 1.019-1.056 |
| short integer array | 1.186 | 1.134-1.253 | 1.309 | 1.291-1.355 |
| full-width signed integers | 1.167 | 1.148-1.191 | 1.309 | 1.276-1.342 |
| full-width unsigned integers | 1.031 | 0.906-1.318 | 1.069 | 1.048-1.100 |
| tiny integer list | 1.140 | 1.097-1.165 | 1.113 | 1.082-1.170 |
| indented integers | 1.642 | 1.525-2.332 | 1.319 | 1.301-1.360 |

The same repeats compared each build with orjson. The baseline column shows
its median ratio from each of the two repeat runs, ordered from smaller to
larger. It does not describe the spread of individual samples.

| Workload | Baseline / orjson | Staging / orjson | Direct four-digit / orjson |
| --- | ---: | ---: | ---: |
| small | 1.51-1.56 | 1.72 | 1.55 |
| medium | 1.82-1.83 | 2.09 | 1.89 |
| short integer array | 2.65-2.76 | 3.23 | 3.62 |
| full-width signed integers | 0.73-0.73 | 0.86 | 0.96 |
| full-width unsigned integers | 4.29-4.31 | 4.42 | 4.60 |
| tiny integer list | 1.13-1.13 | 1.28 | 1.27 |
| indented integers | 1.72-1.73 | 2.85 | 2.31 |

The baseline already beats orjson on these full-width signed integers. The
candidates reduce that advantage; neither creates it. The unsigned workload
also exposes a cost outside formatting: signed extraction fails before each
unsigned conversion. It is not evidence that unsigned decimal formatting
alone is four times slower.

## Decision

Keep neither candidate. Both runs show slower target workloads, including
tiny inputs. Staging adds copying and bookkeeping. Direct writing adds digit
counting and initialization, and its checked formatter differs from `itoa`.
These experiments measure their combined costs; they do not isolate how much
each operation contributes or prove every possible buffer design would lose.

No production encoder change or allocation reduction is retained. Streaming
and parsing are unchanged. Allocation profiling was not repeated for rejected
candidates; [PROFILE.md](PROFILE.md) retains the separate Memray comparison.

## Reproduction

Start in a clean worktree with the baseline encoder, activate its `.venv`, and
build in release mode. Save the package before changing the source:

```sh
source .venv/bin/activate
maturin develop --uv -m crates/jsonmodem-py/Cargo.toml --release
mkdir -p /tmp/output-baseline
cp -a crates/jsonmodem-py/python/jsonmodem /tmp/output-baseline/
git apply --unidiff-zero crates/jsonmodem-py/benchmarks/output-staging.patch
maturin develop --uv -m crates/jsonmodem-py/Cargo.toml --release
python -m pytest -q crates/jsonmodem-py/tests \
  crates/jsonmodem-py/benchmarks/test_output_buffers.py
mkdir -p /tmp/output-staging
cp -a crates/jsonmodem-py/python/jsonmodem /tmp/output-staging/
git apply --reverse --unidiff-zero crates/jsonmodem-py/benchmarks/output-staging.patch
python crates/jsonmodem-py/benchmarks/bench_output_buffers.py \
  --baseline-package /tmp/output-baseline --candidate-package /tmp/output-staging \
  --pairs 7 --seconds 0.03 --output /tmp/output-staging.json
```

Repeat with `output-direct.patch` and `output-direct4.patch`, saving each package
and result under a different name. Apply only one patch at a time. The patches
omit unchanged context lines, so `--unidiff-zero` is required.

For the longer repeats, use `--pairs 11 --seconds 0.05` and add:

```sh
--cases small medium integers integers_wide_signed integers_wide_unsigned \
  indent_integers integers_tiny
```

After reversing the final patch, rebuild the editable package so its extension
matches the restored source. These experiments do not change streaming code,
parser validation, integer limits, callbacks or buffer ownership rules.
