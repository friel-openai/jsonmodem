# Memory compared with orjson

These are complete-document `loads()` and `dumps()` measurements, not streaming
benchmarks. The inputs are synthetic. Lower memory use on one workload does not
establish lower memory use for other inputs or options.

Runtime source: jsonmodem commit `b145ac3` (also used by documentation commit
`b372ba6`). Environment: Linux x86-64, CPython 3.12.13, orjson 3.11.9,
NumPy 2.5.2, Memray 1.20.0. Timing results are in the
[compatibility record](../../../plans/orjson-compatibility/record.md).

## Memray: allocation events and peak live bytes

`bench_allocations.py` warms each operation ten times, then profiles 30 calls
with `trace_python_allocators=True`. Inputs are constructed before profiling;
each result is discarded. Events include the Python loop and call machinery.
Peak live bytes are the maximum simultaneous tracked allocation, not the sum
of allocations and not RSS. Do not divide peak bytes by the call count.
The large `late_default` case uses three measured calls instead of 30.

| Workload | jsonmodem events/call | orjson events/call | jsonmodem peak bytes | orjson peak bytes |
| --- | ---: | ---: | ---: | ---: |
| loads, 1,000 dictionaries | 4,528.1 | 4,498.1 | 289,852 | 928,870 |
| dumps, small dictionary | 4.2 | 3.2 | 388 | 1,129 |
| dumps, 1,000 dictionaries | 13.2 | 9.2 | 119,199 | 65,641 |
| sorted dumps, 1,000 dictionaries | 1,015.2 | 1,011.2 | 122,823 | 69,305 |
| dumps, 1,000 Fragments | 10.2 | 7.2 | 30,458 | 16,489 |
| dumps, 1,000 dataclasses | 47,867.3 | 8.2 | 63,261 | 32,873 |
| dumps, float32 array, 25,000 x 4 | 52.3 | 25,034.2 | 2,292,773 | 4,073,865 |
| dumps, late default callback | 84,928.7 | 18.7 | 42,672,883 | 33,555,105 |

jsonmodem uses fewer peak live bytes on these loads, small dumps, and NumPy
cases. It uses more on the other cases. Dataclass and late-callback allocation
counts remain much higher than orjson even after reducing temporary storage.
The late-callback input is 5,000 references to a 4 KiB string followed by an
unsupported object; its callback returns `None`.

From the repository root, with both libraries and Memray installed:

```bash
python crates/jsonmodem-py/benchmarks/bench_allocations.py --module jsonmodem --calls 30 --output /tmp/alloc-jsonmodem.json
python crates/jsonmodem-py/benchmarks/bench_allocations.py --module orjson --calls 30 --output /tmp/alloc-orjson.json
```

Use `--workload late_default --calls 3` for that row. The all-workload command
also includes `late_default`, with the selected call count. Choose unused output
names because Memray does not overwrite its binary profiles.

## RSS: whole-process resident memory

`bench_rss.py` starts five fresh processes per library and workload, alternating
library order and pinning a CPU where supported. Each worker imports only the
target JSON library, imports NumPy only for its array case, constructs its input,
then makes ten calls without warmup. Decoding fixtures are generated in another
process so their construction cannot raise the worker's memory high-water mark.
Memray is not loaded in these workers.

The table reports median pre-call `VmRSS` and final `VmHWM` from Linux
`/proc/self/status`, in MiB (1,048,576 bytes). Whole-process memory includes the
interpreter, imports, input, allocator retention, and serialization. A peak equal
to the pre-call RSS does not mean the operation allocated nothing. Subtracting
the baseline does not produce an operation-only allocation measurement.

| Workload | jsonmodem pre-call | jsonmodem peak | orjson pre-call | orjson peak |
| --- | ---: | ---: | ---: | ---: |
| loads, 1,000 dictionaries | 18.18 | 18.48 | 17.06 | 17.94 |
| loads, 100,000 dictionaries | 23.45 | 55.02 | 22.80 | 73.99 |
| dumps, 1,000 dictionaries | 18.10 | 18.42 | 17.62 | 17.62 |
| dumps, 1,000 Fragments | 17.34 | 17.34 | 17.02 | 17.02 |
| dumps, 1,000 dataclasses | 18.22 | 18.22 | 17.49 | 17.49 |
| dumps, float32 array, 25,000 x 4 | 32.83 | 35.09 | 32.23 | 35.77 |
| dumps, late default callback | 18.23 | 58.90 | 16.98 | 37.59 |

The largest within-run peak range was orjson's 100,000-dictionary decode:
70.53-74.42 MiB, compared with jsonmodem's 54.91-55.21 MiB. RSS and Memray
answer different questions: jsonmodem's medium decode has lower tracked live
allocations but higher whole-process RSS here.

```bash
python crates/jsonmodem-py/benchmarks/bench_rss.py --runs 5 --calls 10 --output /tmp/rss-comparison.json
```

The JSON output retains all samples, including startup, pre-call, first-call,
and final RSS readings. It also records `resource.ru_maxrss` for cross-checking;
the table uses `VmHWM` consistently.
