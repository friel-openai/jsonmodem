//! Miri positive control: deliberately omit the selected value-pointer field.

#[cfg(all(
    miri,
    target_os = "linux",
    target_arch = "x86_64",
    target_pointer_width = "64",
    target_endian = "little",
))]
#[path = "../../jsonmodem-py/src/compat/borrowed_dict/dense_entry.rs"]
mod dense_entry;

#[cfg(all(
    miri,
    target_os = "linux",
    target_arch = "x86_64",
    target_pointer_width = "64",
    target_endian = "little",
))]
fn main() {
    let mut storage = Box::<[usize; 6]>::new_uninit();
    let keys = storage.as_mut_ptr().cast::<u8>();
    let mut key = 7_u64;
    // SAFETY: these aligned fields fit the 48-byte Rust allocation. All other
    // bytes stay uninitialized. The non-null key has its own live Rust owner.
    unsafe {
        keys.add(10).write(1_u8);
        keys.add(24).cast::<isize>().write(1);
        keys.add(9).write(3_u8);
        keys.add(40)
            .cast::<*mut std::ffi::c_void>()
            .write(std::ptr::from_mut(&mut key).cast());
    }
    // Deliberately violates read_entry's contract: the non-null key requires
    // a value pointer at byte 48, immediately beyond this allocation. A Miri
    // out-of-bounds report is required; an assertion failure alone is not proof.
    let result = unsafe { dense_entry::read_entry(keys, 1, 0) };
    assert!(matches!(result, dense_entry::EntryLookup::Entry { .. }));
}

#[cfg(not(all(
    miri,
    target_os = "linux",
    target_arch = "x86_64",
    target_pointer_width = "64",
    target_endian = "little",
)))]
fn main() {
    eprintln!("Run this deliberate overread only with cargo miri run on Linux x86-64.");
    std::process::exit(2);
}
