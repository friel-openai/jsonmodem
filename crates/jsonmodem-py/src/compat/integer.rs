//! Copy CPython integer digits without retaining a reference to their storage.

/// The signed or unsigned category used by the existing integer formatter.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(super) enum Integer {
    Signed(i64),
    Unsigned(u64),
}

/// Copy a supported integer after the caller verifies the interpreter layout.
///
/// # Safety
///
/// If `layout_matches` is true, `tag` must be aligned and point to an
/// initialized CPython 3.12/3.13 count/sign tag. A positive or negative tag
/// with one, two, or three digits must be followed by that many initialized,
/// aligned u32 digits in the same allocation. Each digit must be below 2^30.
/// The allocation must remain live and immutable throughout the read. Other
/// tags require no digit storage. If `layout_matches` is false, no memory
/// behind `tag` is read.
#[inline(always)]
pub(super) unsafe fn read_integer(tag: *const usize, layout_matches: bool) -> Option<Integer> {
    if !layout_matches {
        return None;
    }
    // SAFETY: the caller guarantees the tag's alignment, initialization and owner.
    let value = unsafe { tag.read() };
    let count = value >> 3;
    let sign = value & 3;
    if (count, sign) == (0, 1) {
        return Some(Integer::Signed(0));
    }
    if !matches!((count, sign), (1..=3, 0 | 2)) {
        return None;
    }
    // SAFETY: these nonzero tags guarantee the following initialized digits.
    let digits = unsafe { tag.add(1).cast::<u32>() };
    let magnitude = match count {
        1 => {
            // SAFETY: a one-digit tag guarantees exactly these four bytes.
            u64::from(unsafe { digits.read() })
        }
        2 => {
            // SAFETY: a two-digit tag guarantees both four-byte reads.
            let low = unsafe { digits.read() };
            let high = unsafe { digits.add(1).read() };
            u64::from(low) | (u64::from(high) << 30)
        }
        3 => {
            // SAFETY: a three-digit tag guarantees each individual u32 read.
            let high = unsafe { digits.add(2).read() };
            if high >= 16 {
                return None;
            }
            let low = unsafe { digits.read() };
            let middle = unsafe { digits.add(1).read() };
            u64::from(low) | (u64::from(middle) << 30) | (u64::from(high) << 60)
        }
        _ => return None,
    };
    if sign == 2 {
        if magnitude == 1_u64 << 63 {
            return Some(Integer::Signed(i64::MIN));
        }
        // The converted magnitude is nonnegative, so its negation cannot overflow.
        Some(Integer::Signed(-i64::try_from(magnitude).ok()?))
    } else if let Ok(integer) = i64::try_from(magnitude) {
        Some(Integer::Signed(integer))
    } else {
        Some(Integer::Unsigned(magnitude))
    }
}
