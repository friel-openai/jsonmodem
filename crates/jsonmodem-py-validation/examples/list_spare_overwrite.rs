//! Miri positive control: deliberately lie about the writable list capacity.

#[cfg(all(miri, target_pointer_width = "64"))]
#[path = "../../jsonmodem-py/src/compat/owned_list/spare.rs"]
mod spare;

#[cfg(all(miri, target_pointer_width = "64"))]
fn main() {
    let mut slot = Box::new(std::mem::MaybeUninit::<*mut std::ffi::c_void>::uninit());
    let mut size = 1;
    let mut owner = 55_u64;
    // Deliberately violate the production writer's storage contract: capacity
    // claims two pointer slots, but the allocation contains only one.
    let appended = unsafe {
        spare::append_spare(
            slot.as_mut_ptr(),
            &mut size,
            2,
            std::ptr::from_mut(&mut owner).cast(),
        )
    };
    assert!(appended);
}

#[cfg(not(all(miri, target_pointer_width = "64")))]
fn main() {
    eprintln!("Run this deliberate overwrite only with cargo miri run on a 64-bit target.");
    std::process::exit(2);
}
