//! Read CPython's compact integer tag without touching an unused zero digit.

/// Copy a compact scalar after the caller checks the interpreter layout.
///
/// # Safety
///
/// If `layout_matches` is true, `tag` must be aligned and point to an
/// initialized CPython 3.12/3.13 count/sign tag. A positive or negative
/// one-digit tag must be followed by four initialized, aligned digit bytes in
/// the same allocation. The allocation must remain live and immutable
/// throughout the read. When `layout_matches` is false, no memory behind `tag`
/// is read.
#[inline(always)]
pub(super) unsafe fn read_compact(tag: *const usize, layout_matches: bool) -> Option<i64> {
    if !layout_matches {
        return None;
    }
    // SAFETY: the caller guarantees the tag's alignment, initialization and owner.
    let value = unsafe { tag.read() };
    match (value >> 3, value & 3) {
        (0, 1) => Some(0),
        (1, sign @ (0 | 2)) => {
            // SAFETY: a nonzero one-digit tag guarantees these initialized bytes.
            // Do not make a reference to a padded struct containing this digit.
            let magnitude = i64::from(unsafe { tag.add(1).cast::<u32>().read() });
            Some(if sign == 2 { -magnitude } else { magnitude })
        }
        _ => None,
    }
}
