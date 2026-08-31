//! Read one entry from the reviewed CPython 3.12/3.13 dense Unicode-key layout.

use std::ffi::c_void;

const DK_LOG2_INDEX_BYTES_OFFSET: usize = 9;
const DK_KIND_OFFSET: usize = 10;
const DK_NENTRIES_OFFSET: usize = 24;
const DK_INDICES_OFFSET: usize = 32;
const ENTRY_BYTES: usize = 16;

/// Copied object pointers carry no owners and no references to table storage.
#[derive(Debug, PartialEq, Eq)]
pub(super) enum EntryLookup {
    Fallback,
    End,
    Entry {
        key: *mut c_void,
        value: *mut c_void,
    },
}

/// Read one dense entry without changing CPython's iteration position.
///
/// # Safety
///
/// The caller must select the reviewed 64-bit CPython layout and retain its
/// allocation without mutation during this read. Nonpositive `used`, negative
/// positions, null table pointers and misaligned headers require no storage.
/// Otherwise byte 10 must be initialized. Kind 1 also requires an initialized
/// isize at byte 24. If that count equals `used` and `position` precedes it,
/// byte 9 must be initialized. Arithmetic and alignment admission then require
/// an initialized key pointer in the selected entry; a non-null key requires
/// the following initialized value pointer. All reached fields must lie in
/// the same allocation as `keys`. Other bytes may remain uninitialized.
///
/// The arithmetic checks do not establish allocation bounds. This function
/// never dereferences the copied object pointers; its caller must keep their
/// owners alive before using them or allowing Python reentry.
#[inline(always)]
pub(super) unsafe fn read_entry(keys: *const u8, used: isize, position: isize) -> EntryLookup {
    if used <= 0 || position < 0 || keys.is_null() || !keys.cast::<isize>().is_aligned() {
        return EntryLookup::Fallback;
    }
    // SAFETY: the caller supplies the kind byte after these early refusals.
    if unsafe { keys.add(DK_KIND_OFFSET).read() } != 1 {
        return EntryLookup::Fallback;
    }
    // SAFETY: the caller supplies this initialized field for kind 1. Header
    // alignment also aligns its byte-24 offset. No header padding is read.
    let entries = unsafe { keys.add(DK_NENTRIES_OFFSET).cast::<isize>().read() };
    if entries != used {
        return EntryLookup::Fallback;
    }
    if position >= entries {
        return EntryLookup::End;
    }
    // SAFETY: an in-range dense entry requires this initialized index-size byte.
    let log2_index_bytes = unsafe { keys.add(DK_LOG2_INDEX_BYTES_OFFSET).read() };
    let Some(index_bytes) = 1_usize.checked_shl(u32::from(log2_index_bytes)) else {
        return EntryLookup::Fallback;
    };
    let Some(offset) = (position as usize)
        .checked_mul(ENTRY_BYTES)
        .and_then(|offset| offset.checked_add(DK_INDICES_OFFSET))
        .and_then(|offset| offset.checked_add(index_bytes))
    else {
        return EntryLookup::Fallback;
    };
    if !offset
        .checked_add(ENTRY_BYTES)
        .is_some_and(|end| end <= isize::MAX as usize)
    {
        return EntryLookup::Fallback;
    }
    // wrapping_add preserves provenance and permits the alignment rejection
    // before requiring the entry itself to be within the allocation.
    let entry = keys.wrapping_add(offset).cast::<*mut c_void>();
    if !entry.is_aligned() {
        return EntryLookup::Fallback;
    }
    // SAFETY: the caller supplies this initialized, aligned key pointer once
    // the kind, density, position and arithmetic checks have admitted it.
    let key = unsafe { entry.read() };
    if key.is_null() {
        return EntryLookup::Fallback;
    }
    // SAFETY: a non-null key requires this initialized adjacent pointer. The
    // checked extent includes both fields without reading any unused entry.
    let value = unsafe { entry.add(1).read() };
    if value.is_null() {
        EntryLookup::Fallback
    } else {
        EntryLookup::Entry { key, value }
    }
}
