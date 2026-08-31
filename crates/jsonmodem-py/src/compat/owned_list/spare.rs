//! Write one owned pointer into unused list storage, without reading the slot.

use std::ffi::c_void;

/// Return false without changing storage when no usable spare slot exists.
///
/// # Safety
///
/// When allocated is positive, a non-null, aligned size points to an
/// initialized, writable isize. When the checks admit a slot, items points to
/// writable storage containing that slot, separate from size. Both allocations
/// remain live and exclusively writable for this call. The slot does not own a
/// reference, even if it contains stale bytes. An admitted value is an owned
/// object pointer; it may refer to the object containing size, as when a list
/// contains itself. Only its pointer is copied, never its pointee. After
/// success the caller must transfer that owner without an intervening callback,
/// destructor, allocation or possible unwind. No other thread may read either
/// field during publication. This models only CPython GIL builds.
#[inline]
pub(super) unsafe fn append_spare(
    items: *mut *mut c_void,
    size: *mut isize,
    allocated: isize,
    value: *mut c_void,
) -> bool {
    if allocated <= 0 || size.is_null() || !size.is_aligned() {
        return false;
    }
    // SAFETY: the caller supplies initialized size storage after these checks.
    let length = unsafe { size.read() };
    if length < 0 || length >= allocated || items.is_null() || !items.is_aligned() {
        return false;
    }
    let Some(extent) = (length as usize + 1).checked_mul(size_of::<*mut c_void>()) else {
        return false;
    };
    if extent > isize::MAX as usize || value.is_null() {
        return false;
    }
    // SAFETY: this admitted slot is inside the caller's writable allocation.
    // Never read or release its prior bytes. allocated > length proves that
    // length + 1 fits isize; publishing the size follows the initialized slot.
    unsafe {
        items.add(length as usize).write(value);
        size.write(length + 1);
    }
    true
}
