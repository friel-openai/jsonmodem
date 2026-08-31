//! Exercise the production writer with uninitialized and stale spare slots.

use std::{ffi::c_void, mem::MaybeUninit, ptr::NonNull};

use crate::list_spare::append_spare;

fn dangling<T>() -> *mut T {
    NonNull::<T>::dangling().as_ptr()
}

#[test]
fn nonpositive_capacity_does_not_require_storage() {
    for capacity in [0, -1, isize::MIN] {
        // SAFETY: nonpositive capacity returns before any pointer is accessed.
        assert!(!unsafe { append_spare(dangling(), dangling(), capacity, dangling()) });
    }
}

#[test]
fn null_or_unaligned_size_requires_no_storage() {
    let mut bytes = [MaybeUninit::<u8>::uninit(); 16];
    // SAFETY: a null size is rejected before it can be read.
    assert!(!unsafe { append_spare(dangling(), std::ptr::null_mut(), 1, dangling()) });
    for index in 0..8 {
        let size = bytes
            .as_mut_ptr()
            .cast::<u8>()
            .wrapping_add(index)
            .cast::<isize>();
        if !size.is_aligned() {
            // SAFETY: unaligned metadata is rejected before it can be read.
            assert!(!unsafe { append_spare(dangling(), size, 1, dangling()) });
        }
    }
}

#[test]
fn negative_full_and_overfull_lengths_leave_metadata_unchanged() {
    for (length, capacity) in [(-1, 1), (1, 1), (2, 1), (isize::MAX, isize::MAX)] {
        let mut size = length;
        // SAFETY: only the initialized size is read before refusing the slot.
        assert!(!unsafe { append_spare(dangling(), &mut size, capacity, dangling()) });
        assert_eq!(size, length);
    }
}

#[test]
fn null_or_unaligned_items_leave_size_unchanged() {
    let mut size = 0;
    // SAFETY: null items cannot reach the write.
    assert!(!unsafe { append_spare(std::ptr::null_mut(), &mut size, 1, dangling()) });
    let mut bytes = [MaybeUninit::<u8>::uninit(); 16];
    for index in 0..8 {
        let items = bytes
            .as_mut_ptr()
            .cast::<u8>()
            .wrapping_add(index)
            .cast::<*mut c_void>();
        if !items.is_aligned() {
            // SAFETY: misaligned items cannot reach the write.
            assert!(!unsafe { append_spare(items, &mut size, 1, dangling()) });
            assert_eq!(size, 0);
        }
    }
}

#[test]
fn excessive_extent_requires_no_item_storage() {
    for length in [isize::MAX - 1, isize::MAX / 8] {
        let mut size = length;
        // SAFETY: the byte extent exceeds the pointer-offset limit. Only the
        // initialized size may be accessed, not the deliberately absent items.
        assert!(!unsafe { append_spare(dangling(), &mut size, isize::MAX, dangling()) });
        assert_eq!(size, length);
    }
}

#[test]
fn null_value_does_not_initialize_the_slot() {
    let mut slot = MaybeUninit::<*mut c_void>::uninit();
    let mut size = 0;
    // SAFETY: metadata and slot storage are valid; a null value must decline.
    assert!(!unsafe { append_spare(slot.as_mut_ptr(), &mut size, 1, std::ptr::null_mut()) });
    assert_eq!(size, 0);
}

#[test]
fn writes_uninitialized_first_and_last_slots_without_reading_them() {
    let owners = [11_u64, 22, 33, 44];
    let mut storage = [MaybeUninit::<*mut c_void>::uninit(); 4];
    let items = storage.as_mut_ptr().cast::<*mut c_void>();
    let mut size = 0;
    for index in 0..4 {
        let value = std::ptr::from_ref(&owners[index]).cast_mut().cast();
        // SAFETY: the next slot is writable, uninitialized and inside storage.
        // The pointed-to owner lives beyond the call, separately from metadata.
        assert!(unsafe { append_spare(items, &mut size, 4, value) });
        assert_eq!(size, index as isize + 1);
        for (position, owner) in owners.iter().enumerate().take(index + 1) {
            // SAFETY: the published prefix is initialized and retains pointers
            // to the live owners. Reading values checks pointer provenance.
            let pointer = unsafe { items.add(position).read() };
            assert_eq!(pointer, std::ptr::from_ref(owner).cast_mut().cast());
            assert_eq!(unsafe { pointer.cast::<u64>().read() }, *owner);
        }
    }
    let extra = std::ptr::from_ref(&owners[0]).cast_mut().cast();
    // SAFETY: full storage must be refused without changing the prefix.
    assert!(!unsafe { append_spare(items, &mut size, 4, extra) });
    assert_eq!(size, 4);
}

#[test]
fn overwrites_stale_spare_pointer_without_accessing_its_freed_owner() {
    let stale = Box::into_raw(Box::new(91_u64));
    let mut slot = stale.cast::<c_void>();
    // SAFETY: reconstruct and release the one owning Box, leaving stale bits
    // only in the non-owning spare slot. The writer must not access that owner.
    drop(unsafe { Box::from_raw(stale) });
    let mut owner = 72_u64;
    let value = std::ptr::from_mut(&mut owner).cast::<c_void>();
    let mut size = 0;
    // SAFETY: the pointer slot and size are live and separate from owner.
    assert!(unsafe { append_spare(&mut slot, &mut size, 1, value) });
    assert_eq!(size, 1);
    assert_eq!(slot, value);
    assert_eq!(unsafe { slot.cast::<u64>().read() }, 72);
}

#[test]
fn repeated_pointer_keeps_all_prior_slots_unchanged() {
    let mut owner = Box::new(63_u64);
    let value = std::ptr::from_mut(&mut *owner).cast::<c_void>();
    let mut slots = [MaybeUninit::<*mut c_void>::uninit(); 8];
    let items = slots.as_mut_ptr().cast::<*mut c_void>();
    let mut size = 0;
    for _ in 0..8 {
        // SAFETY: every next slot is uninitialized and in bounds. The same
        // opaque object pointer is valid for each independent caller owner.
        assert!(unsafe { append_spare(items, &mut size, 8, value) });
    }
    for index in 0..8 {
        assert_eq!(unsafe { items.add(index).read() }, value);
    }
    assert_eq!(*owner, 63);
}

#[test]
fn value_can_point_to_the_object_containing_size() {
    /// A modeled object header; the appended pointer refers to this object.
    #[repr(C)]
    struct Header {
        length: isize,
        payload: u64,
    }

    let mut owner = Box::new(Header {
        length: 0,
        payload: 37,
    });
    let header = std::ptr::from_mut(&mut *owner);
    let mut slot = MaybeUninit::<*mut c_void>::uninit();
    // SAFETY: header remains owned, and its length is separate from the writable
    // pointer slot. The stored object pointer may alias the header allocation.
    unsafe {
        let size = std::ptr::addr_of_mut!((*header).length);
        assert!(append_spare(slot.as_mut_ptr(), size, 1, header.cast()));
        assert_eq!(slot.assume_init(), header.cast());
    }
    assert_eq!(owner.length, 1);
    assert_eq!(owner.payload, 37);
}
