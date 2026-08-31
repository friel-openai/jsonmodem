//! Exercise the production digit reads on exact-size owned allocations.

use std::{alloc::Layout, ptr::NonNull};

use crate::integer::{Integer, read_integer};

const TAG_OFFSET: usize = 16;
const DIGIT_OFFSET: usize = 24;

/// Storage for the modeled tag and initialized digits, without padded
/// references.
struct IntegerAllocation {
    pointer: NonNull<u8>,
    layout: Layout,
}

impl IntegerAllocation {
    fn new(bytes: usize, tag: usize, digits: &[u32]) -> Self {
        let required = digits
            .len()
            .checked_mul(std::mem::size_of::<u32>())
            .and_then(|size| DIGIT_OFFSET.checked_add(size))
            .expect("model size fits usize");
        assert!(required <= bytes);
        if matches!((tag >> 3, tag & 3), (1..=3, 0 | 2)) {
            assert_eq!(digits.len(), tag >> 3);
            assert!(digits.iter().all(|digit| *digit < 1 << 30));
        }
        let layout = Layout::from_size_align(bytes, 8).expect("valid model layout");
        // SAFETY: layout is nonzero and valid, and this owner frees it once.
        let pointer = NonNull::new(unsafe { std::alloc::alloc(layout) })
            .unwrap_or_else(|| std::alloc::handle_alloc_error(layout));
        let allocation = Self { pointer, layout };
        // SAFETY: bytes 16..24 are aligned and within the checked allocation.
        unsafe { allocation.tag().write(tag) };
        for (index, digit) in digits.iter().enumerate() {
            // SAFETY: the checked required size includes each aligned u32.
            unsafe {
                allocation
                    .tag()
                    .add(1)
                    .cast::<u32>()
                    .add(index)
                    .write(*digit)
            };
        }
        allocation
    }

    fn tag(&self) -> *mut usize {
        self.pointer.as_ptr().wrapping_add(TAG_OFFSET).cast()
    }

    fn read(&self) -> Option<Integer> {
        // SAFETY: new initializes the tag and every required bounded digit.
        // This owner remains live, and no operation mutates it during the read.
        unsafe { read_integer(self.tag(), true) }
    }
}

impl Drop for IntegerAllocation {
    fn drop(&mut self) {
        // SAFETY: pointer and layout are unchanged from the owned allocation.
        unsafe { std::alloc::dealloc(self.pointer.as_ptr(), self.layout) };
    }
}

fn check(bytes: usize, tag: usize, digits: &[u32], expected: Option<Integer>) {
    assert_eq!(IntegerAllocation::new(bytes, tag, digits).read(), expected);
}

#[test]
fn zero_needs_neither_initialized_nor_readable_digit_storage() {
    for tag in [1, 5] {
        check(28, tag, &[], Some(Integer::Signed(0)));
        check(24, tag, &[], Some(Integer::Signed(0)));
    }
}

#[test]
fn one_digit_ends_at_byte_28() {
    for flag in [0, 4] {
        for magnitude in [1_u32, 257, (1 << 30) - 1] {
            check(
                28,
                8 | flag,
                &[magnitude],
                Some(Integer::Signed(i64::from(magnitude))),
            );
            check(
                28,
                10 | flag,
                &[magnitude],
                Some(Integer::Signed(-i64::from(magnitude))),
            );
        }
    }
}

#[test]
fn two_digits_end_at_byte_32() {
    for flag in [0, 4] {
        for (digits, expected) in [
            ([0, 1], 1_073_741_824_i64),
            ([1, 1], 1_073_741_825),
            ([(1 << 30) - 1, 1], 2_147_483_647),
            ([0, 1 << 23], 9_007_199_254_740_992),
            ([1, 1 << 23], 9_007_199_254_740_993),
            ([(1 << 30) - 1, (1 << 30) - 1], 1_152_921_504_606_846_975),
        ] {
            check(32, 16 | flag, &digits, Some(Integer::Signed(expected)));
            check(32, 18 | flag, &digits, Some(Integer::Signed(-expected)));
        }
    }
}

#[test]
fn three_digits_end_at_byte_36() {
    let mask = (1 << 30) - 1;
    for flag in [0, 4] {
        check(
            36,
            24 | flag,
            &[0, 0, 1],
            Some(Integer::Signed(1_152_921_504_606_846_976)),
        );
        check(
            36,
            26 | flag,
            &[0, 0, 1],
            Some(Integer::Signed(-1_152_921_504_606_846_976)),
        );
        check(
            36,
            24 | flag,
            &[mask, mask, 7],
            Some(Integer::Signed(i64::MAX)),
        );
        check(
            36,
            26 | flag,
            &[mask, mask, 7],
            Some(Integer::Signed(-i64::MAX)),
        );
        check(
            36,
            24 | flag,
            &[0, 0, 8],
            Some(Integer::Unsigned(9_223_372_036_854_775_808)),
        );
        check(36, 26 | flag, &[0, 0, 8], Some(Integer::Signed(i64::MIN)));
        check(
            36,
            24 | flag,
            &[1, 0, 8],
            Some(Integer::Unsigned(9_223_372_036_854_775_809)),
        );
        check(
            36,
            24 | flag,
            &[mask, mask, 15],
            Some(Integer::Unsigned(u64::MAX)),
        );
    }
}

#[test]
fn negative_overflow_selects_fallback() {
    for flag in [0, 4] {
        for digits in [
            [1, 0, 8],
            [0, 1, 8],
            [0, 0, 9],
            [(1 << 30) - 1, (1 << 30) - 1, 15],
        ] {
            check(36, 26 | flag, &digits, None);
        }
    }
}

#[test]
fn third_digit_is_bounded_before_shifting() {
    for sign in [0, 2] {
        for high in [16, 17, 255, 1 << 29, (1 << 30) - 1] {
            check(36, 24 | sign, &[0, 0, high], None);
            check(36, 24 | sign, &[(1 << 30) - 1, (1 << 30) - 1, high], None);
        }
    }
}

#[test]
fn unsupported_tags_require_only_the_tag() {
    for tag in [
        0,
        2,
        3,
        4,
        6,
        7,
        9,
        11,
        13,
        15,
        17,
        19,
        25,
        27,
        32,
        34,
        40,
        42,
        usize::MAX,
    ] {
        check(24, tag, &[], None);
    }
}

#[test]
fn unsupported_layout_requires_no_storage() {
    // SAFETY: false selects fallback before any access, without an allocation.
    assert_eq!(
        unsafe { read_integer(NonNull::<usize>::dangling().as_ptr(), false) },
        None
    );
    // SAFETY: the same early return does not read a null pointer either.
    assert_eq!(unsafe { read_integer(std::ptr::null(), false) }, None);
}
