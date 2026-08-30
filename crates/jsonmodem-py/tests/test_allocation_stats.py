"""Allocation totals must distinguish allocation requests from deallocations."""

from enum import IntEnum
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmarks"))

import allocation_stats


class AllocatorType(IntEnum):
    """Memray's allocator identifiers, used without loading its native extension."""

    PYMALLOC_FREE = 1
    PYMALLOC_MALLOC = 2
    PYMALLOC_CALLOC = 3
    PYMALLOC_REALLOC = 4
    FREE = 5
    MALLOC = 6
    REALLOC = 7
    CALLOC = 8
    POSIX_MEMALIGN = 9
    ALIGNED_ALLOC = 10
    MEMALIGN = 11
    VALLOC = 12
    PVALLOC = 13
    MMAP = 14
    MUNMAP = 15


class FileFormat(IntEnum):
    """Only full captures contain the records needed for allocation totals."""

    ALL_ALLOCATIONS = 0
    AGGREGATED_ALLOCATIONS = 1


@pytest.fixture
def capture(monkeypatch):
    state = SimpleNamespace(
        records=[], closed=False, read=False,
        metadata=SimpleNamespace(
            file_format=FileFormat.ALL_ALLOCATIONS, peak_memory=12345,
            python_allocator="pymalloc", trace_python_allocators=True,
            has_native_traces=False, total_allocations=999,
        ),
    )

    class Reader:
        """A full capture with explicit close and record-read observations."""

        def __init__(self, profile):
            self.metadata = state.metadata

        def __enter__(self):
            return self

        def __exit__(self, *error):
            state.closed = True

        def get_allocation_records(self):
            state.read = True
            return iter(state.records)

    monkeypatch.setitem(sys.modules, "memray", SimpleNamespace(
        AllocatorType=AllocatorType, FileFormat=FileFormat, FileReader=Reader,
    ))
    return state


def record(allocator, size, count=1):
    return SimpleNamespace(allocator=allocator, size=size, n_allocations=count)


def test_counts_zero_requests_but_not_positive_size_deallocations(capture):
    capture.records = [
        record(AllocatorType.MALLOC, 0),
        record(AllocatorType.MMAP, 4096),
        record(AllocatorType.MUNMAP, 4096),
        record(AllocatorType.REALLOC, 64),
        record(AllocatorType.PYMALLOC_MALLOC, 48, 3),
        record(AllocatorType.FREE, 123),
        record(AllocatorType.PYMALLOC_FREE, 0),
    ]
    result = allocation_stats.summarize_allocations("unused.bin")
    assert result["allocation_requests"] == 6
    assert result["total_allocated_bytes"] == 4208
    assert result["peak_live_bytes"] == 12345
    assert result["python_allocator"] == "pymalloc"
    assert result["trace_python_allocators"] is True
    assert result["native_traces"] is False
    assert result["file_format"] == "ALL_ALLOCATIONS"
    assert capture.closed


@pytest.mark.parametrize("allocator", list(AllocatorType))
def test_every_allocator_kind(capture, allocator):
    freeing = allocator in (AllocatorType.FREE, AllocatorType.PYMALLOC_FREE, AllocatorType.MUNMAP)
    capture.records = [record(allocator, 16)]
    result = allocation_stats.summarize_allocations("unused.bin")
    assert result["allocation_requests"] == (0 if freeing else 1)
    assert result["total_allocated_bytes"] == (0 if freeing else 16)


def test_realloc_counts_the_new_requested_size_not_only_growth(capture):
    capture.records = [
        record(AllocatorType.MALLOC, 8), record(AllocatorType.REALLOC, 64),
        record(AllocatorType.FREE, 0),
    ]
    result = allocation_stats.summarize_allocations("unused.bin")
    assert result["allocation_requests"] == 2
    assert result["total_allocated_bytes"] == 72


def test_unknown_allocator_fails_instead_of_guessing(capture):
    capture.records = [record(999, 1)]
    with pytest.raises(ValueError, match="unrecognized Memray allocator"):
        allocation_stats.summarize_allocations("unused.bin")
    assert capture.closed


def test_aggregated_capture_cannot_supply_allocation_totals(capture):
    capture.metadata.file_format = FileFormat.AGGREGATED_ALLOCATIONS
    with pytest.raises(ValueError, match="require a full"):
        allocation_stats.summarize_allocations("unused.bin")
    assert not capture.read
    assert capture.closed


def test_import_does_not_load_memray():
    code = (
        "import sys\n"
        f"sys.path.insert(0, {str(Path(allocation_stats.__file__).parent)!r})\n"
        "import allocation_stats\n"
        "assert 'memray' not in sys.modules\n"
    )
    subprocess.run([sys.executable, "-c", code], check=True, capture_output=True, timeout=30)


def test_native_mmap_counts_and_peak_match_memray(tmp_path):
    if importlib.util.find_spec("memray") is None:
        pytest.skip("optional Memray is not installed")
    profile = tmp_path / "native.bin"
    code = (
        "import json, mmap, sys\n"
        "import memray\n"
        f"sys.path.insert(0, {str(Path(allocation_stats.__file__).parent)!r})\n"
        "from allocation_stats import summarize_allocations\n"
        f"profile = {str(profile)!r}\n"
        "with memray.Tracker(profile, trace_python_allocators=True):\n"
        "    region = mmap.mmap(-1, 1048576)\n"
        "    region[0] = 1\n"
        "    region.close()\n"
        "result = summarize_allocations(profile)\n"
        "with memray.FileReader(profile) as reader:\n"
        "    records = list(reader.get_allocation_records())\n"
        "    peak = sum(row.size for row in reader.get_high_watermark_allocation_records())\n"
        "freeing = {memray.AllocatorType.FREE, memray.AllocatorType.PYMALLOC_FREE, memray.AllocatorType.MUNMAP}\n"
        "assert any(row.allocator == memray.AllocatorType.MUNMAP and row.size == 1048576 for row in records)\n"
        "assert result['allocation_requests'] == sum(row.n_allocations for row in records if row.allocator not in freeing)\n"
        "assert result['total_allocated_bytes'] == sum(row.size for row in records if row.allocator not in freeing)\n"
        "assert result['peak_live_bytes'] == peak\n"
        "print(json.dumps(result))\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code], check=True, capture_output=True, text=True, timeout=30,
    )
    result = json.loads(completed.stdout)
    assert result["total_allocated_bytes"] >= 1048576
    assert result["peak_live_bytes"] >= 1048576
