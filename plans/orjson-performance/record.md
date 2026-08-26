# Performance and security evidence

These results describe the initial performance work. Later changes and tests
are in the [compatibility record](../orjson-compatibility/record.md) and
[speedup record](../orjson-speedups/record.md).

## Result at 887f0ee

CPython 3.12.13, orjson 3.11.9, AMD EPYC 7763, Linux x86_64, CPU 0.
Release build with thin LTO and one codegen unit. Each library was measured
11 times. Each measurement timed many calls, using the same call count for both
libraries. The benchmark increased that count until the slower library's batch
took at least 0.1 seconds. The libraries alternated running first.

For each pair of measurements, the benchmark divided jsonmodem's time by
orjson's time. The table reports the median ratio: the middle value after sorting
the 11 ratios. Below 1.0 means jsonmodem took less time; 2.0 means twice as long.
The time columns give median nanoseconds per call (ns). Dividing those two
columns can differ from the reported ratio because the medians are calculated
separately. Artifact: /tmp/jsonmodem-final-887f0ee.json.

| Operation | Workload | jsonmodem ns | orjson ns | Ratio |
| --- | --- | ---: | ---: | ---: |
| loads | small | 550 | 438 | 1.26x |
| dumps | small | 327 | 169 | 1.93x |
| loads | medium | 424,718 | 242,186 | 1.75x |
| dumps | medium | 156,457 | 88,987 | 1.76x |
| loads | integers | 300,805 | 194,322 | 1.54x |
| dumps | integers | 117,160 | 46,411 | 2.52x |
| loads | floats | 527,947 | 283,973 | 1.86x |
| dumps | floats | 450,777 | 302,339 | 1.49x |
| loads | strings | 49,233 | 36,929 | 1.33x |
| dumps | strings | 23,359 | 12,920 | 1.80x |
| loads | escaped | 290,963 | 144,318 | 2.02x |
| dumps | escaped | 87,449 | 41,424 | 2.08x |
| loads | long_string | 39,071 | 71,188 | 0.55x |
| dumps | long_string | 18,580 | 10,269 | 1.79x |

Both original workloads meet the <=2x acceptance criterion. Integer-array dumps
and escaped-string operations do not. The Python fallback for sorted dictionaries,
default callbacks, datetime/dataclass/NumPy values, and Fragment is not covered by
this performance claim. Float output is compared semantically; byte formatting
can differ. No runtime calls to orjson are used.

Reproduction from the repository root:

    source .venv/bin/activate
    maturin develop --uv -m crates/jsonmodem-py/Cargo.toml --release
    python crates/jsonmodem-py/benchmarks/bench_orjson_compat.py --seconds 0.1 --output /tmp/jsonmodem-results.json

Local validation: .agent/check.sh, .agent/check-py.sh, and Python binding Clippy
passed. The final local suite has 100 passing Python tests. All 21 checks passed
for 887f0ee, including CPython 3.9/3.13, Miri, fuzzing, and all benchmark jobs.
Final-head CI is tracked in friel-openai/jsonmodem PR #1.

## 2026-08-25: baseline inspection

Starting commit: e2978b1. CPython 3.12.13, orjson 3.11.9, Linux x86_64.
No runtime dependency on orjson is permitted. Inputs are generated locally,
with no private datasets or private project references.

cProfile on 100 medium dumps calls: 0.666 seconds total, 0.585 seconds in
_prepare and 0.078 seconds in the standard-library encoder. These measurements
show where the program spends time under cProfile; they are not unprofiled
call times.

The binding has abi3-py39 enabled. Local PyO3 source string.rs shows to_cow
allocates under that limited ABI. A per-interpreter build can use the public
PyUnicode_AsUTF8AndSize API and retains Python 3.9 support with separate wheels.

## 2026-08-25: streaming regressions before fixes

Command: .venv/bin/python -m pytest -q crates/jsonmodem-py/tests/test_streaming_security.py

Result: 13 failed, 4 passed. Both exposed streaming APIs abort on 20,000 nested
arrays under a 256 MiB RLIMIT_AS subprocess limit. Valid root numbers fail at
finish; incomplete containers ending in numbers can be accepted. Integer tokens
become floats and 1e400 becomes infinity. Tests limit time and memory so failure
cannot exhaust the development machine.

## Next experiment: native complete-document frontend

First Rust implementation results, using the timing ratios defined above on
the same CPU: small loads 1.30x, small dumps 1.98x, medium loads 1.81x, medium
dumps 2.37x. With thin LTO and
one codegen unit: 1.13x, 1.62x, 1.53x, 2.10x respectively. The original
CPU-pinned baseline was 7.05x, 31.08x, 12.48x, 23.24x. All 26 existing frontend
tests pass. This does not yet meet the dumps target. Additional misses include
integer serialization, escaped-string parsing, and long-string serialization.
Artifacts: /tmp/jsonmodem-baseline.json, /tmp/jsonmodem-native-v1.json,
/tmp/jsonmodem-native-lto.json.

Question: Can eliminating input re-parsing, event/path objects, Python number
constructor calls for common numbers, and Python serialization preprocessing
bring the median time ratio to at most 2.0 relative to orjson?

Method: Release build in the checkout's .venv; CPU-pinned, alternating library
order; calibrated timing batches; save raw samples and metadata as JSON.
Compare small and medium first, then integer arrays, float arrays, short strings,
escaped Unicode, and a long string. Validate outputs before measuring. Track
both semantic and exact-byte equality. Do not include validation checks in
timed batches and do not disable validation inside either implementation.

Decision rule: Retain an implementation only if compatibility/security tests
pass. Continue profiling if either original workload exceeds 2.0. Additional
workload misses must remain visible. Generated artifacts: /tmp/jsonmodem-*.json.

Threat model: Untrusted JSON bytes and ordinary Python objects, including
subclasses and default callbacks. Arbitrary native buffer exporters are outside
the accepted input API; mutable built-in buffers must be copied before Rust
reads them. Streaming tests remain separate because a non-streaming implementation
does not establish safety of feed(). Miri of the core does not validate PyO3.

## 2026-08-25: native implementation, third measurement

Artifact: /tmp/jsonmodem-native-v3.json. Eleven measurements per library, CPU 0,
using the timing method above. Median loads/dumps ratios: small 1.03/1.52,
medium 1.73/1.83, integers 1.53/3.00, floats 1.99/1.50, strings 1.42/1.80,
escaped 2.04/2.21, long_string 0.56/1.88. The original targets pass; the broader
results do not support a universal 2x claim. Bounded identity-based encoded key
reuse reduced medium dumps from 2.14x to 1.83x. Owners remain retained.

Core tests: 168 passed after EOF, depth, and lexeme-number changes. Binding tests:
71 passed, two failures only in existing error-message expectations. Streaming
security regressions now reject deep input under 256 MiB, preserve integer types,
finalize numeric EOF, and reject external buffer owners.

Next experiment: specialize common scalar list serialization without unchecked
Python object access, and reduce scalar escape overhead. Retain changes only
with differential tests and a repeated pinned benchmark showing improvement.

## 2026-08-25: independent review and regressions

Review exercised 5,000 random trees and 50,000 random/malformed documents through
the Python extension against orjson. No semantic discrepancy occurred in those
cases. Review also found four targeted failures: native recursion on a 64 KiB
thread stack, repeated long-key path copies, multidimensional byte-view slicing,
and acceptance of 1.e2 in streaming parsing. A bytes-subclass exporter could also
bypass the initial buffer restriction. Exact-type checks now reject that subclass.

Native operations now use heap-backed stacks. OwnedPathComponent holds Arc<str>;
byte views require one dimension; DecimalPoint requires a fraction digit.
The checked-in regressions pass under 128 MiB for the 60,006-byte long-key input,
under 256 MiB for depth 20,000 rejection, and with 64 KiB thread stacks.
95 Python tests pass, including 5,000 generated documents/mutations and 10,000
arbitrary-byte cases. 171 core tests pass. Workspace/all-target Clippy passes.

Fifth measurement after iterative traversal: loads/dumps small 1.34/1.82,
medium 1.67/1.79. Additional ratios: integers 1.57/3.41, floats 1.91/1.60,
strings 1.40/2.07, escaped 1.95/2.06, long_string 0.51/2.09. The broad suite still
does not meet 2x for every operation. Artifact: /tmp/jsonmodem-native-v5.json.
