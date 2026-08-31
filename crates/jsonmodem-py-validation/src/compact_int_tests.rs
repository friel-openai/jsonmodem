//! Check the production compact-integer reader at allocation boundaries.

use std::{alloc::Layout, ptr::NonNull};

use crate::compact_int::read_compact;

fn read(tag: usize, digit: Option<u32>) -> Option<i64> {
    if let Some(digit) = digit {
        assert_eq!(tag >> 3, 1);
        assert!(matches!(tag & 3, 0 | 2));
        assert!((1..1 << 30).contains(&digit));
    }
    let bytes = if digit.is_some() { 12 } else { 8 };
    let layout = Layout::from_size_align(bytes, 8).unwrap();
    // SAFETY: the nonzero allocation is freed with the same layout below.
    let pointer = NonNull::new(unsafe { std::alloc::alloc(layout) })
        .unwrap_or_else(|| std::alloc::handle_alloc_error(layout));
    let tag_pointer = pointer.as_ptr().cast::<usize>();
    // SAFETY: the allocation contains an aligned tag and, for one-digit
    // values, exactly four initialized digit bytes. No padded reference is made.
    let result = unsafe {
        tag_pointer.write(tag);
        if let Some(digit) = digit {
            tag_pointer.add(1).cast::<u32>().write(digit);
        }
        read_compact(tag_pointer, true)
    };
    // SAFETY: the read returned a scalar, and the allocation is still owned here.
    unsafe { std::alloc::dealloc(pointer.as_ptr(), layout) };
    result
}

#[test]
fn zero_requires_no_digit_storage() {
    for tag in [1, 5] {
        assert_eq!(read(tag, None), Some(0));
    }
}

#[test]
fn one_digit_ends_at_byte_twelve() {
    for flag in [0, 4] {
        for magnitude in [1, 257, (1 << 30) - 1] {
            assert_eq!(read(8 | flag, Some(magnitude)), Some(i64::from(magnitude)));
            assert_eq!(
                read(10 | flag, Some(magnitude)),
                Some(-i64::from(magnitude))
            );
        }
    }
}

#[test]
fn wider_tags_require_only_the_tag() {
    for count in [2, 3, 4, 1024] {
        for flags in [0, 2, 4, 6] {
            assert_eq!(read((count << 3) | flags, None), None);
        }
    }
}

#[test]
fn unsupported_layout_requires_no_storage() {
    // SAFETY: a layout mismatch returns before reading either pointer.
    unsafe {
        assert_eq!(
            read_compact(NonNull::<usize>::dangling().as_ptr(), false),
            None
        );
        assert_eq!(read_compact(std::ptr::null(), false), None);
    }
}
