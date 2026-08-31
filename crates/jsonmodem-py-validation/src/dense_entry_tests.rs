//! Check the production reader without initializing padding or unused entries.

use std::{alloc::Layout, ffi::c_void, ptr::NonNull};

use crate::dense_entry::{EntryLookup, read_entry};

/// Own uninitialized bytes; tests initialize only each branch's required
/// fields.
struct KeyTable {
    pointer: NonNull<u8>,
    layout: Layout,
    // Byte offset of the modeled CPython header within the allocation.
    start: usize,
}

impl KeyTable {
    fn new(bytes: usize, start: usize) -> Self {
        assert!(bytes != 0 && start <= bytes);
        let layout = Layout::from_size_align(bytes, 8).expect("valid model layout");
        // SAFETY: this nonzero allocation is owned and deallocated exactly once.
        let pointer = NonNull::new(unsafe { std::alloc::alloc(layout) })
            .unwrap_or_else(|| std::alloc::handle_alloc_error(layout));
        Self {
            pointer,
            layout,
            start,
        }
    }

    fn pointer(&self) -> *mut u8 {
        self.pointer.as_ptr().wrapping_add(self.start)
    }

    fn write<T: Copy>(&mut self, offset: usize, value: T) {
        let offset = self.start.checked_add(offset).expect("field offset fits");
        let end = offset
            .checked_add(std::mem::size_of::<T>())
            .expect("field extent fits");
        assert!(end <= self.layout.size());
        let pointer = self.pointer.as_ptr().wrapping_add(offset).cast::<T>();
        assert!(pointer.is_aligned());
        // SAFETY: the field is aligned and inside this owned allocation. This
        // writes only T, leaving all other bytes uninitialized unless specified.
        unsafe { pointer.write(value) };
    }

    fn dense(&mut self, entries: isize, log2_index_bytes: u8) {
        self.write(10, 1_u8);
        self.write(24, entries);
        self.write(9, log2_index_bytes);
    }

    fn entry(&mut self, log2_index_bytes: u8, position: usize, key: &u64, value: &u64) {
        let indices = 1_usize
            .checked_shl(u32::from(log2_index_bytes))
            .expect("model index size fits");
        let offset = position
            .checked_mul(16)
            .and_then(|offset| offset.checked_add(32))
            .and_then(|offset| offset.checked_add(indices))
            .expect("model entry offset fits");
        self.write(offset, std::ptr::from_ref(key).cast_mut().cast::<c_void>());
        self.write(
            offset + 8,
            std::ptr::from_ref(value).cast_mut().cast::<c_void>(),
        );
    }
}

impl Drop for KeyTable {
    fn drop(&mut self) {
        // SAFETY: pointer and layout are unchanged from this owned allocation.
        unsafe { std::alloc::dealloc(self.pointer.as_ptr(), self.layout) };
    }
}

/// Check copied pointer values and their provenance while their owners live.
///
/// # Safety
///
/// actual must come from read_entry on fields initialized with pointers to the
/// supplied key/value owners. Reading the result also tests preserved
/// provenance.
unsafe fn check_entry(actual: EntryLookup, key: &u64, value: &u64) {
    let EntryLookup::Entry {
        key: actual_key,
        value: actual_value,
    } = actual
    else {
        panic!("expected copied entry, got {actual:?}");
    };
    assert_eq!(actual_key, std::ptr::from_ref(key).cast_mut().cast());
    assert_eq!(actual_value, std::ptr::from_ref(value).cast_mut().cast());
    // SAFETY: the initialized entry pointers borrow these still-live owners.
    unsafe {
        assert_eq!(actual_key.cast::<u64>().read(), *key);
        assert_eq!(actual_value.cast::<u64>().read(), *value);
    }
}

#[test]
fn empty_and_negative_states_require_no_storage() {
    let dangling = NonNull::<isize>::dangling().as_ptr().cast::<u8>();
    for keys in [std::ptr::null_mut(), dangling] {
        for used in [0, -1, isize::MIN] {
            // SAFETY: a nonpositive count returns before any field is read.
            assert_eq!(unsafe { read_entry(keys, used, 0) }, EntryLookup::Fallback);
        }
        for position in [-1, isize::MIN] {
            // SAFETY: a negative position also returns before any field read.
            assert_eq!(
                unsafe { read_entry(keys, 1, position) },
                EntryLookup::Fallback
            );
        }
    }
    // SAFETY: a null table pointer is rejected before dereferencing it.
    assert_eq!(
        unsafe { read_entry(std::ptr::null(), 1, 0) },
        EntryLookup::Fallback
    );
}

#[test]
fn header_alignment_is_checked_before_fields() {
    let table = KeyTable::new(8, 0);
    for offset in 1..8 {
        let unaligned = table.pointer().wrapping_add(offset);
        // SAFETY: these misaligned pointers require no initialized fields.
        assert_eq!(
            unsafe { read_entry(unaligned, 1, 0) },
            EntryLookup::Fallback
        );
    }
}

#[test]
fn other_kinds_require_only_the_kind_byte() {
    for kind in [0_u8, 2, 3, 255] {
        let mut table = KeyTable::new(11, 0);
        table.write(10, kind);
        // SAFETY: only the initialized kind byte is read before this refusal.
        assert_eq!(
            unsafe { read_entry(table.pointer(), 1, 0) },
            EntryLookup::Fallback
        );
    }
}

#[test]
fn deleted_or_mismatched_counts_require_no_index_bytes() {
    for (entries, used) in [(0, 1), (-1, 1), (2, 1), (3, 2), (isize::MAX, 1)] {
        let mut table = KeyTable::new(32, 0);
        table.write(10, 1_u8);
        table.write(24, entries);
        // SAFETY: kind and count are initialized. The unequal count must stop
        // before the uninitialized index-size byte or nonexistent entries.
        assert_eq!(
            unsafe { read_entry(table.pointer(), used, 0) },
            EntryLookup::Fallback
        );
    }
}

#[test]
fn end_requires_neither_indices_nor_entries() {
    for entries in [1_isize, 2, 5] {
        let mut table = KeyTable::new(32, 0);
        table.write(10, 1_u8);
        table.write(24, entries);
        for position in [entries, entries + 1, isize::MAX] {
            // SAFETY: the dense count is initialized; an end position must not
            // read the uninitialized index-size byte or form an entry address.
            assert_eq!(
                unsafe { read_entry(table.pointer(), entries, position) },
                EntryLookup::End
            );
        }
    }
}

#[test]
fn first_and_last_entries_preserve_pointers_at_each_index_width() {
    let first_key = Box::new(11_u64);
    let first_value = Box::new(12_u64);
    let last_key = Box::new(21_u64);
    let last_value = Box::new(22_u64);
    // The index regions model 8 one-byte, 256 two-byte, and 65,536 four-byte
    // indices. Their contents and the header's log2_size byte stay uninitialized.
    for log2_index_bytes in [3_u8, 9, 18] {
        let indices = 1_usize << log2_index_bytes;
        for prefix in [0, 8, 64] {
            for suffix in [0, 9] {
                let mut table = KeyTable::new(prefix + 32 + indices + 5 * 16 + suffix, prefix);
                table.dense(5, log2_index_bytes);
                table.entry(log2_index_bytes, 0, &first_key, &first_value);
                table.entry(log2_index_bytes, 4, &last_key, &last_value);
                // SAFETY: these two selected entries are initialized, aligned
                // and owned. All middle entries, padding and spare bytes remain
                // uninitialized; the last entry ends the allocation at suffix 0.
                unsafe {
                    check_entry(read_entry(table.pointer(), 5, 0), &first_key, &first_value);
                    check_entry(read_entry(table.pointer(), 5, 4), &last_key, &last_value);
                }
            }
        }
    }
}

#[test]
fn index_size_shift_overflow_requires_no_entry_storage() {
    for log2_index_bytes in [64_u8, 65, 255] {
        let mut table = KeyTable::new(32, 0);
        table.dense(1, log2_index_bytes);
        // SAFETY: only the initialized header is reachable before shift rejection.
        assert_eq!(
            unsafe { read_entry(table.pointer(), 1, 0) },
            EntryLookup::Fallback
        );
    }
}

#[test]
fn entry_offset_overflow_requires_no_entry_storage() {
    let positions = [
        (3, isize::MAX - 1),                    // multiplying the position by 16
        (3, (usize::MAX / 16) as isize),        // adding the 32-byte header
        (4, ((usize::MAX - 32) / 16) as isize), // adding index bytes
        (3, ((usize::MAX - 32) / 16) as isize), // adding the entry extent
    ];
    for (log2_index_bytes, position) in positions {
        let mut table = KeyTable::new(32, 0);
        let entries = position + 1;
        table.dense(entries, log2_index_bytes);
        // SAFETY: the initialized header forces checked arithmetic to reject
        // before any entry access; no large allocation is modeled or read.
        assert_eq!(
            unsafe { read_entry(table.pointer(), entries, position) },
            EntryLookup::Fallback
        );
    }
}

#[test]
fn entry_extent_must_fit_isize_before_access() {
    for (log2_index_bytes, position) in [
        (63, 0_isize),
        (3, ((isize::MAX as usize - 40) / 16) as isize),
    ] {
        let mut table = KeyTable::new(32, 0);
        let entries = position + 1;
        table.dense(entries, log2_index_bytes);
        // SAFETY: these initialized headers describe extents above isize::MAX;
        // only the header may be read before the extent check rejects them.
        assert_eq!(
            unsafe { read_entry(table.pointer(), entries, position) },
            EntryLookup::Fallback
        );
    }
}

#[test]
fn entry_alignment_is_checked_before_access() {
    for log2_index_bytes in [0_u8, 1, 2] {
        let mut table = KeyTable::new(32, 0);
        table.dense(1, log2_index_bytes);
        // SAFETY: the initialized header yields a misaligned entry address,
        // which must be rejected before accessing nonexistent entry storage.
        assert_eq!(
            unsafe { read_entry(table.pointer(), 1, 0) },
            EntryLookup::Fallback
        );
    }
}

#[test]
fn null_key_does_not_require_value_storage() {
    let mut table = KeyTable::new(48, 0);
    table.dense(1, 3);
    table.write(40, std::ptr::null_mut::<c_void>());
    // SAFETY: the initialized null key is the last field in this allocation.
    // Its refusal must occur before any attempt to read the absent value.
    assert_eq!(
        unsafe { read_entry(table.pointer(), 1, 0) },
        EntryLookup::Fallback
    );
}

#[test]
fn null_value_selects_fallback() {
    let key = Box::new(31_u64);
    let mut table = KeyTable::new(56, 0);
    table.dense(1, 3);
    table.write(40, std::ptr::from_ref(&*key).cast_mut().cast::<c_void>());
    table.write(48, std::ptr::null_mut::<c_void>());
    // SAFETY: both selected pointer fields are initialized and the key is owned.
    assert_eq!(
        unsafe { read_entry(table.pointer(), 1, 0) },
        EntryLookup::Fallback
    );
}

#[test]
fn changed_headers_are_read_again() {
    let key = Box::new(41_u64);
    let old_value = Box::new(42_u64);
    let new_value = Box::new(43_u64);
    let mut table = KeyTable::new(56, 0);
    table.dense(1, 3);
    table.entry(3, 0, &key, &old_value);
    // SAFETY: the selected pair is initialized and both owners remain live.
    unsafe { check_entry(read_entry(table.pointer(), 1, 0), &key, &old_value) };
    table.write(10, 0_u8);
    // SAFETY: the changed kind is initialized and must reject before entry access.
    assert_eq!(
        unsafe { read_entry(table.pointer(), 1, 0) },
        EntryLookup::Fallback
    );
    table.write(10, 1_u8);
    table.write(24, 2_isize);
    // SAFETY: the changed count must reject before any entry access.
    assert_eq!(
        unsafe { read_entry(table.pointer(), 1, 0) },
        EntryLookup::Fallback
    );
    table.write(24, 1_isize);
    table.entry(3, 0, &key, &new_value);
    // SAFETY: the newly selected pair is initialized and its owners remain live.
    unsafe { check_entry(read_entry(table.pointer(), 1, 0), &key, &new_value) };
}

#[test]
fn replacement_allocation_preserves_copied_pointer_provenance() {
    let old_key = Box::new(51_u64);
    let old_value = Box::new(52_u64);
    let new_key = Box::new(61_u64);
    let new_value = Box::new(62_u64);
    let mut old_table = KeyTable::new(72, 0);
    old_table.dense(2, 3);
    old_table.entry(3, 0, &old_key, &old_value);
    // SAFETY: only the first entry is selected, initialized and owned here.
    let copied = unsafe { read_entry(old_table.pointer(), 2, 0) };
    let mut new_table = KeyTable::new(72, 0);
    new_table.dense(2, 3);
    new_table.entry(3, 1, &new_key, &new_value);
    assert_ne!(old_table.pointer(), new_table.pointer());
    drop(old_table);
    // SAFETY: copied contains object pointers, not pointers into the freed
    // table. Their owners remain live. The replacement has an initialized last
    // entry at the resumed position; its first entry stays uninitialized.
    unsafe {
        check_entry(copied, &old_key, &old_value);
        check_entry(read_entry(new_table.pointer(), 2, 1), &new_key, &new_value);
    }
}
