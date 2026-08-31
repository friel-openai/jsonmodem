//! Miri positive control: deliberately overstate a live list's capacity.

#[cfg(all(miri, target_pointer_width = "64"))]
#[path = "../../jsonmodem-py/src/compat/owned_list/live.rs"]
mod live;

#[cfg(all(miri, target_pointer_width = "64"))]
fn main() {
    use std::{ffi::c_void, rc::Rc};

    let first = Rc::into_raw(Rc::new(11_u64)).cast_mut().cast::<c_void>();
    let mut slot = Box::new(first);
    let mut length = 1;
    let value = Rc::new(22_u64);
    let pointer = Rc::as_ptr(&value).cast_mut().cast::<c_void>();
    // The initialized prefix owns one reference. Deliberately claim a second
    // writable slot beyond this one-pointer allocation.
    let appended =
        unsafe { live::append_live(std::ptr::from_mut(slot.as_mut()), &mut length, 2, pointer) };
    if appended {
        let _ = Rc::into_raw(value);
    }
    assert!(appended);
}

#[cfg(not(all(miri, target_pointer_width = "64")))]
fn main() {
    eprintln!("Run this deliberate overwrite only with cargo miri run on a 64-bit target.");
    std::process::exit(2);
}
