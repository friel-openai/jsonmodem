//! Append using the storage guarantees of a live CPython list.

use std::ffi::c_void;

/// Initialize a spare slot and publish its length, or leave a full list
/// unchanged.
///
/// # Safety
///
/// size must point to a live, aligned, writable isize containing a nonnegative
/// length. Capacity allocated counts pointer slots. Either allocated is -1,
/// length is zero and items is null (the sorting state), or allocated is
/// nonnegative and length <= allocated. Positive capacity requires aligned,
/// writable item storage for allocated pointers, with a total byte extent no
/// greater than isize::MAX. That storage must not overlap size. The length
/// prefix owns initialized object references; spare slots own no references
/// and may contain uninitialized or stale bytes.
///
/// value must be a live, non-null object pointer with one caller-owned
/// reference. Its pointee may contain size, as when a list contains itself;
/// only the pointer is copied. All metadata must describe the same current
/// storage after the last possible callback. Storage must remain live and
/// exclusively accessible during publication. Python callers must hold the GIL
/// and must not call Python, allocate or drop an owner between obtaining this
/// metadata and completing the ownership transfer.
/// After success the caller must transfer that owner immediately, without a
/// callback, destructor, allocation or possible unwind. Refusal retains it.
#[inline]
pub(super) unsafe fn append_live(
    items: *mut *mut c_void,
    size: *mut isize,
    allocated: isize,
    value: *mut c_void,
) -> bool {
    // SAFETY: the live-list contract supplies initialized size storage even
    // when an empty, full or sorting list has no spare slot.
    let length = unsafe { size.read() };
    if allocated > length {
        // SAFETY: current capacity proves the slot and increment are in bounds.
        // Publish length only after initializing the slot; never read old bytes.
        unsafe {
            items.add(length as usize).write(value);
            size.write(length + 1);
        }
        true
    } else {
        false
    }
}

#[cfg(test)]
#[path = "live_tests.rs"]
mod tests;
