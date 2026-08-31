# Reproduce the Python performance workloads

These commands use scripts in this repository. Run them from the repository
root with a prepared CPython 3.12.13 environment and release builds of the
libraries. They reproduce the workloads and timing parameters, not the
unpublished result-auditing tools or historical build artifacts.

The reference is **orjson 3.11.9**. orjson 3.12.0 was not measured. Install
NumPy 2.5.2 for array cases, Memray 1.20.0 for allocation measurements, and
jiter 0.16.0 plus pyperf 2.10.0 for the incremental scripts that require them.
Do not use Python optimization mode: some runner correctness checks use
assertions.

Use the same interpreter build for all libraries. Choose an available CPU
and stop other heavy work during measurement. Linux commands below use
`taskset`; affinity does not isolate memory bandwidth, caches or CPU frequency.
For public runners, omit `--cpu` where affinity is unavailable. RSS requires
Linux `/proc`.

## Builds and local configuration

Original is PR #4's previously measured jsonmodem runtime at `b0f3190`.
Rebuilt is a fresh compilation of that runtime at `3279ba1`. Final is this
PR's optimized runtime at `b889f4c`. Compiling the old
source again produces another rebuild, not the original measured binary.
The result data records full revisions and binary hashes.

The measurements used Rust 1.94.1 and maturin 1.14.1. The workspace release
profile enables thin LTO, one codegen unit and line-table debug information.
No profile-guided compilation or `target-cpu=native` flag was used.

Prepare a standard GIL-enabled CPython 3.12.13 environment outside the
checkout. Set `PYTHON` to that environment's absolute executable path. Its
benchmark dependencies can be installed with:

```sh
"$PYTHON" -m pip install maturin==1.14.1 orjson==3.11.9 numpy==2.5.2 \
  memray==1.20.0 jiter==0.16.0 pyperf==2.10.0
```

Create separate worktrees from the public fork. The commands below use
absolute `REBUILT_SRC` and `FINAL_SRC` paths chosen by the reader:

```sh
git clone https://github.com/friel-openai/jsonmodem.git jsonmodem-source
git -C jsonmodem-source worktree add --detach "$REBUILT_SRC" \
  3279ba1cde1acfcdb341a167decee6044f6ffdea
git -C jsonmodem-source worktree add --detach "$FINAL_SRC" \
  b889f4cd0323b2f60729eb61c35429fbe611fd47
```

Set `RESULTS`, `REBUILT` and `FINAL` to new absolute directories outside
the checkouts. With Rust 1.94.1 installed, build and install each package:

```sh
cd "$REBUILT_SRC"
env -u RUSTFLAGS -u CARGO_ENCODED_RUSTFLAGS \
  RUSTUP_TOOLCHAIN=1.94.1 CARGO_TARGET_DIR="$RESULTS/target-rebuilt" \
  PYO3_PYTHON="$PYTHON" "$PYTHON" -m maturin build \
  --release --locked --interpreter "$PYTHON" \
  -m crates/jsonmodem-py/Cargo.toml --out "$RESULTS/wheels-rebuilt"
"$PYTHON" -m pip install --no-deps --target "$REBUILT" \
  "$RESULTS"/wheels-rebuilt/*.whl

cd "$FINAL_SRC"
env -u RUSTFLAGS -u CARGO_ENCODED_RUSTFLAGS \
  RUSTUP_TOOLCHAIN=1.94.1 CARGO_TARGET_DIR="$RESULTS/target-final" \
  PYO3_PYTHON="$PYTHON" "$PYTHON" -m maturin build \
  --release --locked --interpreter "$PYTHON" \
  -m crates/jsonmodem-py/Cargo.toml --out "$RESULTS/wheels-final"
"$PYTHON" -m pip install --no-deps --target "$FINAL" \
  "$RESULTS"/wheels-final/*.whl
```

Remove inherited `CARGO_PROFILE_RELEASE_*` overrides before building.
The reported native hashes identify the measured binaries; they do not
promise bit-identical compilation on another machine.

The original measured wheel is retained in the investigation artifacts but
is not published as a release download. Without that archived wheel, omit
Original from the library configuration and omit `--reference original`
from the public commands. Run the maintained and focused comparisons with
the rebuilt control only. Do not label a fresh compilation as the recorded
Original binary.

Set these shell variables to your local locations:

- `PYTHON`: the prepared CPython executable with orjson and required benchmark dependencies.
- `BENCH`: `crates/jsonmodem-py/benchmarks`.
- `CPU`: the logical CPU chosen for the measurements.
- `CORPUS`: the document download directory.
- `RESULTS`: a new, empty result directory outside the checkout.
- `LIBRARIES`: the JSON configuration file described below.
- `ORIGINAL`, `REBUILT`, `FINAL`: package roots, each containing an unpacked `jsonmodem` package and its extension.

The public runner accepts this configuration. The three package directories
in this example are relative to the configuration file, not environment
variables expanded by JSON. Replace them with your prepared directories.
Omitting `python` uses the coordinator's interpreter.

```json
{
  "libraries": [
    {"name": "original", "module": "jsonmodem", "expected_version": "0.0.0-alpha.0", "pythonpath": ["packages/original"]},
    {"name": "rebuilt", "module": "jsonmodem", "expected_version": "0.0.0-alpha.0", "pythonpath": ["packages/rebuilt"]},
    {"name": "final", "module": "jsonmodem", "expected_version": "0.0.0-alpha.0", "pythonpath": ["packages/final"]},
    {"name": "orjson", "module": "orjson", "expected_version": "3.11.9"}
  ]
}
```

Expected versions are checked. Package versions alone do not distinguish
these jsonmodem builds: retain the runner's imported-file hashes and the
actual source revision. Use fresh output filenames; preserve failed runs
rather than overwriting them.

## Public documents

Fetch the pinned corpus and check all builds before timing:

```sh
"$PYTHON" "$BENCH/bench_public_corpus.py" fetch --directory "$CORPUS"
"$PYTHON" "$BENCH/bench_public_corpus.py" verify \
  --directory "$CORPUS" --libraries "$LIBRARIES" \
  --reference orjson --reference original --reference rebuilt \
  --output "$RESULTS/public-verified.json"
```

Measure all 18 documents and both complete-document operations. Eight fresh
processes per build each take three timing samples targeting 50 milliseconds
per sample, after three warmup calls:

```sh
"$PYTHON" "$BENCH/bench_public_corpus.py" run \
  --directory "$CORPUS" --libraries "$LIBRARIES" \
  --reference orjson --reference original --reference rebuilt \
  --operations loads dumps --cpu "$CPU" \
  --repeats 8 --samples 3 --seconds 0.05 --warmups 3 --timeout 1200 \
  --output "$RESULTS/public.json"
```

Measure allocations and RSS separately from latency:

```sh
"$PYTHON" "$BENCH/bench_public_memory.py" run \
  --directory "$CORPUS" --libraries "$LIBRARIES" \
  --reference orjson --reference original --reference rebuilt \
  --operations loads dumps --metrics memray rss --cpu "$CPU" \
  --repeats 3 --calls 1 --warmups 10 --rss-calls 10 \
  --memray-version 1.20.0 --timeout 600 \
  --profiles "$RESULTS/public-captures" --output "$RESULTS/public-memory.json"
```

This runs one tracked call after ten warmups for Memray, and ten calls without
warmup for RSS. Keep captures outside the checkout; they can contain local
filenames. The report's tracked peaks are Memray peaks, not RSS.

## Maintained complete-document suite

Run this block twice: first with `CONTROL="$ORIGINAL"` and
`CONTROL_NAME=original`, then with `CONTROL="$REBUILT"` and
`CONTROL_NAME=rebuilt`. Each command starts seven processes per build and
takes three timing samples per case, targeting 40 milliseconds per sample.
Every worker also measures orjson 3.11.9.

```sh
taskset -c "$CPU" "$PYTHON" "$BENCH/bench_output_buffers.py" \
  --baseline-package "$CONTROL" --candidate-package "$FINAL" \
  --pairs 7 --seconds 0.04 --output "$RESULTS/output-$CONTROL_NAME.json"
taskset -c "$CPU" "$PYTHON" "$BENCH/bench_frontend.py" \
  --baseline-package "$CONTROL" --candidate-package "$FINAL" \
  --pairs 7 --seconds 0.04 --output "$RESULTS/frontend-$CONTROL_NAME.json"
taskset -c "$CPU" "$PYTHON" "$BENCH/bench_numbers.py" \
  --baseline-package "$CONTROL" --candidate-package "$FINAL" \
  --operations loads dumps --pairs 7 --seconds 0.04 \
  --output "$RESULTS/numbers-$CONTROL_NAME.json"
taskset -c "$CPU" "$PYTHON" "$BENCH/bench_strings.py" \
  --baseline-package "$CONTROL" --candidate-package "$FINAL" \
  --operations loads dumps --inputs bytes bytearray memoryview array_view \
  --pairs 7 --seconds 0.04 --output "$RESULTS/strings-$CONTROL_NAME.json"
```

Together these retain all 171 cases. The scripts print some ratios for
diagnostics; the report uses absolute case medians. For aggregate comparisons,
divide each case median by its own orjson case median, then take the
equal-weight geometric mean. Do not use the scripts' older `over_orjson`
summary field: it takes a median of process ratios, which is a different
calculation. Do not pool the original and rebuilt comparisons.

## Date/time and NumPy

Keep the same two separate `CONTROL` selections. Both commands use eight
processes per build and three samples targeting 40 milliseconds per case:

```sh
taskset -c "$CPU" "$PYTHON" "$BENCH/bench_datetime.py" \
  --baseline-package "$CONTROL" --candidate-package "$FINAL" \
  --pairs 8 --seconds 0.04 --output "$RESULTS/datetime-$CONTROL_NAME.json"
taskset -c "$CPU" "$PYTHON" "$BENCH/bench_numpy_dates.py" \
  --baseline-package "$CONTROL" --candidate-package "$FINAL" \
  --pairs 8 --seconds 0.04 --output "$RESULTS/numpy-$CONTROL_NAME.json"
```

Retain all 43 date/time cases, but exclude `time_16`, `time_1024` and
`dates_under_dict` from comparisons requiring identical orjson output bytes.
For time fractions with five-digit microsecond values, orjson 3.11.9 omits
a leading zero. jsonmodem retains the padding from `datetime.time.isoformat()`.
The runner checks both expected outputs; it does not count different bytes
as an equivalent result.
The date/time mean uses the remaining 40 cases. All 28 NumPy cases enter
their separate mean.

These two public scripts expose latency and correctness checks, not the
per-case Memray and RSS measurements in the report. The latter use their
fixture generators with the public memory helpers; an equivalent public
command-line coordinator is not supplied here.

## Malformed inputs

The rejection runner generates all 39 cases; it needs no corpus download.
Run latency and allocations separately:

```sh
"$PYTHON" "$BENCH/bench_rejections.py" run \
  --libraries "$LIBRARIES" --cpu "$CPU" --metrics latency \
  --repeats 8 --samples 3 --seconds 0.04 --latency-warmups 3 \
  --output "$RESULTS/rejection-latency.json"
"$PYTHON" "$BENCH/bench_rejections.py" run \
  --libraries "$LIBRARIES" --cpu "$CPU" --metrics memray \
  --repeats 3 --memray-warmups 10 --memray-calls 1 --memray-version 1.20.0 \
  --profiles "$RESULTS/rejection-captures" \
  --output "$RESULTS/rejection-memory.json"
```

These measurements include exception handling. There is no rejection
geometric mean or rejected-byte throughput, and no rejection RSS measurement.

## Incremental APIs

For each previous-build selection, run numeric streams separately from
complete-document parsing:

```sh
taskset -c "$CPU" "$PYTHON" "$BENCH/bench_stream_numbers.py" \
  --baseline-package "$CONTROL" --candidate-package "$FINAL" \
  --pairs 7 --seconds 0.04 --chunk-target 512 \
  --output "$RESULTS/stream-numbers-$CONTROL_NAME.json"
```

Event and byte-view event modes materialize events. The two cumulative-prefix
modes materialize every array prefix and compare jsonmodem with jiter 0.16.0.
jiter's measurement includes constructing contiguous prefix bytes.

The string-buffer script instead takes interpreter executables. Prepare
`CONTROL_PYTHON` and `FINAL_PYTHON` environments with the selected wheels and
the same CPython build and dependencies. Its seven process comparisons and
three batches of 200 streams are fixed by the runner:

```sh
taskset -c "$CPU" "$PYTHON" "$BENCH/bench_buffer_inputs.py" \
  --baseline-python "$CONTROL_PYTHON" --candidate-python "$FINAL_PYTHON" \
  --cases bytes byte_views_bytes byte_views_exporter \
  --string-length 4 --chunk-size 512 \
  > "$RESULTS/stream-strings-short-$CONTROL_NAME.json"
taskset -c "$CPU" "$PYTHON" "$BENCH/bench_buffer_inputs.py" \
  --baseline-python "$CONTROL_PYTHON" --candidate-python "$FINAL_PYTHON" \
  --cases bytes byte_views_bytes byte_views_exporter \
  --string-length 256 --chunk-size 4096 \
  > "$RESULTS/stream-strings-long-$CONTROL_NAME.json"
```

This script also performs a separate allocation measurement of 100 streams
after ten warmups. It deletes its captures and retains only reported
allocation counts and peaks. The peak covers the full capture, not one
stream. It does not record individual timing batches in its output.

## Other memory measurements

`bench_allocations.py --module jsonmodem --calls 1 --output FILE` measures
all 14 synthetic allocation cases in one process. Select a jsonmodem build
using its package directory in `PYTHONPATH`; use `--module orjson` for the
reference. Each case has ten warmups, then a garbage collection before
tracking. Do not select one workload at a time if reproducing the report's
shared process history.

`bench_rss.py --runs 3 --calls 10 --output FILE` starts fresh RSS workers for
all seven synthetic cases. Its public coordinator compares one installed
jsonmodem build with orjson. It does not reproduce the report's four-library
order. Its first post-call snapshot is after releasing the result.

The report's four-library synthetic memory order and date/NumPy memory
coordinator are not covered by these commands. Their measured observations
remain available in [data.json](data/final-2026-08-31/data.json).
Do not describe these shorter commands as an exact rerun of those stages.

All twelve synthetic allocation workers reported Memray 1.20.0's warnings
about correcting the `malloc` and `free` symbol addresses. Their diagnostics
and captures were retained, and allocation requests and bytes were recounted.
Only those exact warnings from the pinned profiler were accepted; a failed
capture or a different diagnostic was not accepted. Recounting recorded
allocations does not prove that every allocation was intercepted.

The public-document and rejection coordinators do not retain successful
child stderr. Empty coordinator stderr therefore does not establish that
every child was silent. The string-buffer runner deletes its allocation
captures, as noted above; its counters could not be independently recounted.

## Validation results and entry points

The measured runtime is `b889f4c`. Final release checks reported:

- Python 3.12: 13,860 API tests and six subtests passed, plus 71 benchmark
  fixture tests. No skips in these runs.
- Python 3.13: 13,860 API tests and six subtests passed, with no skips.
- Python 3.9: 10,785 tests passed and 1,484 skipped. The reference wheel is
  unavailable for this interpreter; optional-reference and interpreter-specific
  tests account for the skipped coverage.
- The upstream orjson suite: 1,630 passes and six skips on the reference;
  1,626 passes, the same six skips and four package-identity exclusions on
  jsonmodem. Both runs reported two warnings. No functional exclusion was added.
- Native Rust: 260 passes and four existing ignored tests. Separately linked
  binding executables passed all 56 tests on each of Python 3.12 and 3.13,
  including ownership, callback mutation and selected allocation failures.

AddressSanitizer checks reported 13,857 passes, six subtests and three skips
on each of Python 3.12 and 3.13; Python 3.9 reported 10,782 passes and 1,487
skips. The three additional skips are address-space-limit tests incompatible
with the sanitizer's virtual-memory reservation. Deliberate invalid reads
were detected before testing jsonmodem. The runs verified Python's malloc
allocator before and after tests and disabled leak detection. Instruction
review checked the actual instrumented reads, writes and string copies,
not just the presence of sanitizer symbols.

Miri reported 251 workspace passes and four existing ignored tests, plus
targeted runs under both Stacked Borrows and Tree Borrows with execution
seeds 0, 1 and 2. Both models also ran the strict pointer-helper checks and
detected the deliberate out-of-bounds list write. Miri ran at `cdf146f`;
its tested Rust sources are identical at `b889f4c`. The intervening UUID
exception fix is in the Python binding, which Miri does not execute. The
final native and Python tests do cover that fix.

These public commands are entry points, not a claim that every command below
produces every count above in a newly created environment:

```sh
bash .agent/check.sh
bash .agent/check-py.sh
bash .agent/check-miri.sh
bash .agent/check-py-memory.sh
```

`.agent/check-py.sh` activates the checkout's `.venv`; it does not use
`$PYTHON` or the packages installed under `$FINAL`. Prepare that separate
environment with the intended interpreter, maturin, pytest and optional test
dependencies, and make `uv` available. The script rebuilds jsonmodem and
generates documentation. The benchmark environment alone is not enough.

For the upstream compatibility tests, set `ORJSON_SRC` to a full orjson
checkout at `705515d77b28429d0b7c30c3d781abe52e8a1e5a`, including its `data/`
directory. Install its test dependencies, then explicitly select Final:

```sh
"$PYTHON" -m pip install 'pytest>=9.0' -r "$ORJSON_SRC/test/requirements.txt"
PYTHONPATH="$FINAL" "$PYTHON" "$BENCH/check_orjson_release.py" "$ORJSON_SRC"
```

Read [Memory-safety tests](../../../docs/memory-safety-testing.md) before the
sanitizer commands. Select the intended Python interpreter and install the
optional dependencies to reproduce their coverage. The default sanitizer
setup does not install orjson or NumPy. The Miri and sanitizer scripts do not
run the separately linked binding executables. Miri excludes the live Python
binding; AddressSanitizer does not instrument the installed CPython interpreter
or every native dependency. Valid native object and buffer storage remains
a requirement. Passing these tests is not a proof of equivalence or memory safety.
