"""Summarize full Memray captures without importing Memray in timing/RSS workers."""


def summarize_allocations(profile):
    """Count allocation requests, including zero-size requests and full realloc sizes."""
    import memray

    allocating = {
        memray.AllocatorType.PYMALLOC_MALLOC,
        memray.AllocatorType.PYMALLOC_CALLOC,
        memray.AllocatorType.PYMALLOC_REALLOC,
        memray.AllocatorType.MALLOC,
        memray.AllocatorType.REALLOC,
        memray.AllocatorType.CALLOC,
        memray.AllocatorType.POSIX_MEMALIGN,
        memray.AllocatorType.ALIGNED_ALLOC,
        memray.AllocatorType.MEMALIGN,
        memray.AllocatorType.VALLOC,
        memray.AllocatorType.PVALLOC,
        memray.AllocatorType.MMAP,
    }
    # MUNMAP carries a length; size alone cannot distinguish it from MMAP.
    freeing = {
        memray.AllocatorType.PYMALLOC_FREE,
        memray.AllocatorType.FREE,
        memray.AllocatorType.MUNMAP,
    }
    with memray.FileReader(profile) as reader:
        metadata = reader.metadata
        if metadata.file_format != memray.FileFormat.ALL_ALLOCATIONS:
            raise ValueError("allocation totals require a full Memray allocation capture")
        requests = allocated = 0
        for record in reader.get_allocation_records():
            if record.allocator in allocating:
                requests += record.n_allocations
                allocated += record.size
            elif record.allocator not in freeing:
                raise ValueError(f"unrecognized Memray allocator: {record.allocator}")
        return {
            "allocation_requests": requests,
            "total_allocated_bytes": allocated,
            "peak_live_bytes": metadata.peak_memory,
            "python_allocator": metadata.python_allocator,
            "trace_python_allocators": metadata.trace_python_allocators,
            "native_traces": metadata.has_native_traces,
            "file_format": metadata.file_format.name,
        }
