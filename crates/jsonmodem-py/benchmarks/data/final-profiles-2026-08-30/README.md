# Final-build profiling data

These are diagnostic profiles of jsonmodem `b0f3190`, not another timing
comparison. The reference is orjson 3.11.9 on CPython 3.12.13. The selected
CPU controls use the unchanged PR #3 rebuild at `b7fe329`. See the
[profiling report](../../PERFORMANCE_PROFILING.md) for findings and limits.

- [cpu.json](cpu.json) contains source-qualified function counts from 18
  completed py-spy recordings, one failed diagnostic recording and one
  unstarted case. It preserves sampling errors, unresolved-frame counts,
  the earlier failed attachment and artifact hashes.
- [native-allocations.json](native-allocations.json) contains 36 completed
  Memray captures: three documents, loads and dumps, both libraries, and
  three fresh processes per combination. It preserves full allocation
  stack groups, request and byte counts, medians, profiler diagnostics and
  artifact hashes. The first failed attempt is described separately and
  excluded from those counts.
- [native-code.json](native-code.json) contains a read-only comparison of
  the saved native libraries: equal instruction ranges, changed addresses,
  checked call targets and earlier control observations. See the
  [native-code report](../../PERFORMANCE_NATIVE_CODE.md) for what this rules
  out and what remains untested. It contains no new timing measurements.

Each CPU sample and allocation stack can contain several functions. Function
counts overlap and must not be added. Allocation stack groups partition the
requests; their requested-byte sum includes the full size of each realloc.
Tracked peak memory uses Memray's reported high-water mark. None of these
fields measures process RSS or unprofiled elapsed time.

`final`, `rebuilt` and `orjson` identify the frozen builds in each file's
`builds` object. Source filenames use repository-relative or dependency names.
The exports omit machine paths, process IDs, command lines and document text.
Raw recordings are not included; hashes identify the reviewed originals.

The CPU counts come from Speedscope recordings made by py-spy 0.4.2 with a
requested rate of 19 Hz. Memray 1.20.0 uses `ALL_ALLOCATIONS`, native stacks
and Python allocator tracing. Each
allocation capture includes one call and result release after ten warmups.
The machine is shared; Python hash seeds are randomized under `-I -B`.

Verify these files from this directory with `sha256sum -c SHA256SUMS`.
