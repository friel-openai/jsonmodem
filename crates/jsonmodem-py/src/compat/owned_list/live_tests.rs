//! Model valid list storage; CPython layout and reference counts need native
//! tests.

use std::{cell::UnsafeCell, ffi::c_void, mem::MaybeUninit, rc::Rc};

use super::append_live;

/// Model the adapter's immediate reference transfer after a successful write.
/// The caller must supply the complete append_live storage contract.
unsafe fn append_owner(
    items: *mut *mut c_void,
    size: *mut isize,
    allocated: isize,
    value: Rc<u64>,
) -> Option<Rc<u64>> {
    let pointer = Rc::as_ptr(&value).cast_mut().cast();
    // SAFETY: storage is supplied by the caller; value owns a live object.
    let appended = unsafe { append_live(items, size, allocated, pointer) };
    if appended {
        let _ = Rc::into_raw(value);
        None
    } else {
        Some(value)
    }
}

/// Release the initialized prefix, each slot owning one Rc<u64> reference.
/// The caller must supply 0 <= *size <= items.len() and one transferred
/// Rc<u64> reference in each prefix slot.
unsafe fn clear_owners(items: &mut [MaybeUninit<*mut c_void>], size: &mut isize) {
    let count = std::mem::replace(size, 0) as usize;
    for item in &mut items[..count] {
        // SAFETY: the caller supplies one transferred owner per prefix slot.
        drop(unsafe { Rc::from_raw(item.assume_init().cast::<u64>()) });
    }
}

#[test]
fn empty_and_sorting_lists_retain_the_owner() {
    for allocated in [0, -1] {
        let mut size = 0;
        let owner = Rc::new(41);
        // SAFETY: the empty and sorting states have a valid size and no items.
        let retained =
            unsafe { append_owner(std::ptr::null_mut(), &mut size, allocated, owner.clone()) }
                .expect("no spare storage");
        assert!(Rc::ptr_eq(&owner, &retained));
        assert_eq!(size, 0);
        assert_eq!(Rc::strong_count(&owner), 2);
        drop(retained);
        assert_eq!(Rc::strong_count(&owner), 1);
    }
}

#[test]
fn full_storage_keeps_its_prefix_and_new_owner() {
    let existing = Rc::new(11_u64);
    let pointer = Rc::into_raw(existing.clone()).cast_mut().cast();
    let mut slots = [MaybeUninit::new(pointer)];
    let mut size = 1;
    let next = Rc::new(22);
    // SAFETY: the complete one-slot allocation owns an initialized prefix.
    let retained = unsafe { append_owner(slots.as_mut_ptr().cast(), &mut size, 1, next.clone()) }
        .expect("full storage");
    assert!(Rc::ptr_eq(&retained, &next));
    assert_eq!(size, 1);
    assert_eq!(unsafe { slots[0].assume_init() }, pointer);
    assert_eq!(Rc::strong_count(&existing), 2);
    assert_eq!(Rc::strong_count(&next), 2);
    // SAFETY: the sole initialized slot still owns its original reference.
    unsafe { clear_owners(&mut slots, &mut size) };
    assert_eq!(Rc::strong_count(&existing), 1);
}

#[test]
fn first_and_last_spare_slots_are_initialized() {
    let owners = [11, 22, 33, 44].map(Rc::new);
    let mut slots = [MaybeUninit::<*mut c_void>::uninit(); 4];
    let mut size = 0;
    for (index, owner) in owners.iter().enumerate() {
        // SAFETY: prior slots own their references; the next slot is in bounds
        // and uninitialized. All owners outlive the modeled list.
        let retained =
            unsafe { append_owner(slots.as_mut_ptr().cast(), &mut size, 4, owner.clone()) };
        assert!(retained.is_none());
        assert_eq!(size, index as isize + 1);
        for (slot, owner) in slots.iter().zip(&owners).take(index + 1) {
            let pointer = unsafe { slot.assume_init() }.cast::<u64>();
            assert_eq!(pointer, Rc::as_ptr(owner).cast_mut());
            assert_eq!(unsafe { pointer.read() }, **owner);
            assert_eq!(Rc::strong_count(owner), 2);
        }
    }
    // SAFETY: every slot now owns one transferred Rc reference.
    unsafe { clear_owners(&mut slots, &mut size) };
    assert_eq!(size, 0);
    assert!(owners.iter().all(|owner| Rc::strong_count(owner) == 1));
}

#[test]
fn stale_spare_pointer_is_overwritten_without_reading_it() {
    let stale = Box::into_raw(Box::new(91_u64));
    let mut slots = [MaybeUninit::new(stale.cast::<c_void>())];
    // SAFETY: release the only owner, leaving stale bytes in an unowned slot.
    drop(unsafe { Box::from_raw(stale) });
    let mut size = 0;
    let owner = Rc::new(72);
    // SAFETY: the spare slot is writable but its old contents are not live.
    let retained = unsafe { append_owner(slots.as_mut_ptr().cast(), &mut size, 1, owner.clone()) };
    assert!(retained.is_none());
    let pointer = unsafe { slots[0].assume_init() }.cast::<u64>();
    assert_eq!(pointer, Rc::as_ptr(&owner).cast_mut());
    assert_eq!(unsafe { pointer.read() }, 72);
    // SAFETY: the new slot owns the transferred reference, not the stale Box.
    unsafe { clear_owners(&mut slots, &mut size) };
    assert_eq!(Rc::strong_count(&owner), 1);
}

#[test]
fn repeated_pointer_owns_one_reference_per_slot() {
    let owner = Rc::new(63);
    let mut slots = [MaybeUninit::<*mut c_void>::uninit(); 8];
    let mut size = 0;
    for count in 1..=8 {
        // SAFETY: the next slot is spare; each clone supplies a distinct owner.
        let retained =
            unsafe { append_owner(slots.as_mut_ptr().cast(), &mut size, 8, owner.clone()) };
        assert!(retained.is_none());
        assert_eq!(size, count);
        assert_eq!(Rc::strong_count(&owner), count as usize + 1);
    }
    // SAFETY: all eight initialized slots own independent Rc references.
    unsafe { clear_owners(&mut slots, &mut size) };
    assert_eq!(Rc::strong_count(&owner), 1);
}

#[test]
fn replacement_storage_is_used_after_clear() {
    let first_owner = Rc::new(14);
    let mut first = Box::new([MaybeUninit::<*mut c_void>::uninit(); 2]);
    let mut size = 0;
    // SAFETY: first is live empty storage with two pointer slots.
    let retained =
        unsafe { append_owner(first.as_mut_ptr().cast(), &mut size, 2, first_owner.clone()) };
    assert!(retained.is_none());
    // SAFETY: clearing releases its sole initialized owner before freeing storage.
    unsafe { clear_owners(first.as_mut(), &mut size) };
    drop(first);
    let next_owner = Rc::new(28);
    let mut replacement = Box::new([MaybeUninit::<*mut c_void>::uninit(); 4]);
    // SAFETY: supply the replacement pointer and capacity, never the old pointer.
    let retained = unsafe {
        append_owner(
            replacement.as_mut_ptr().cast(),
            &mut size,
            4,
            next_owner.clone(),
        )
    };
    assert!(retained.is_none());
    assert_eq!(size, 1);
    assert_eq!(Rc::strong_count(&first_owner), 1);
    assert_eq!(Rc::strong_count(&next_owner), 2);
    // SAFETY: the replacement prefix owns one transferred reference.
    unsafe { clear_owners(replacement.as_mut(), &mut size) };
    assert_eq!(Rc::strong_count(&next_owner), 1);
}

#[test]
fn value_may_point_to_the_size_owner() {
    /// Model an interior-mutable object header which can itself be an item.
    struct Header {
        length: UnsafeCell<isize>,
        payload: u64,
    }
    let owner = Rc::new(Header {
        length: UnsafeCell::new(0),
        payload: 37,
    });
    let value = owner.clone();
    let pointer = Rc::as_ptr(&value).cast_mut();
    let size = owner.length.get();
    let mut slot = MaybeUninit::<*mut c_void>::uninit();
    // SAFETY: header size and slot do not overlap. The value points into the
    // header allocation; UnsafeCell permits its length to change through size.
    let appended = unsafe { append_live(slot.as_mut_ptr(), size, 1, pointer.cast()) };
    if appended {
        let _ = Rc::into_raw(value);
    }
    assert!(appended);
    assert_eq!(unsafe { size.read() }, 1);
    assert_eq!(unsafe { slot.assume_init() }, pointer.cast());
    assert_eq!(owner.payload, 37);
    assert_eq!(Rc::strong_count(&owner), 2);
    // SAFETY: remove the slot before releasing its transferred reference.
    unsafe {
        size.write(0);
        drop(Rc::from_raw(slot.assume_init().cast::<Header>()));
    }
    assert_eq!(Rc::strong_count(&owner), 1);
}
