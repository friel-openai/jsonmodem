//! Exact positions of JSON escape bytes in one checked input block.

/// Bit i is set exactly when byte i needs escaping in a JSON string.
#[inline]
pub(super) fn mask(block: &[u8; 16]) -> u16 {
    #[cfg(all(target_arch = "x86_64", target_feature = "sse2"))]
    {
        use std::arch::x86_64::{
            _mm_cmpeq_epi8, _mm_loadu_si128, _mm_max_epu8, _mm_movemask_epi8, _mm_or_si128,
            _mm_set1_epi8,
        };

        // SAFETY: block supplies exactly 16 initialized bytes. loadu needs no
        // alignment, and this branch is compiled only with SSE2 available.
        unsafe {
            let bytes = _mm_loadu_si128(block.as_ptr().cast());
            let control_limit = _mm_set1_epi8(0x1f);
            let controls = _mm_cmpeq_epi8(_mm_max_epu8(bytes, control_limit), control_limit);
            let quotes = _mm_cmpeq_epi8(bytes, _mm_set1_epi8(b'"' as i8));
            let slashes = _mm_cmpeq_epi8(bytes, _mm_set1_epi8(b'\\' as i8));
            _mm_movemask_epi8(_mm_or_si128(controls, _mm_or_si128(quotes, slashes))) as u16
        }
    }
    #[cfg(not(all(target_arch = "x86_64", target_feature = "sse2")))]
    {
        portable(block)
    }
}

#[cfg(any(test, not(all(target_arch = "x86_64", target_feature = "sse2"))))]
fn portable(block: &[u8; 16]) -> u16 {
    block.iter().enumerate().fold(0, |mask, (index, &byte)| {
        mask | (u16::from(byte < 0x20 || matches!(byte, b'"' | b'\\')) << index)
    })
}

#[cfg(test)]
mod tests {
    use super::{mask, portable};

    #[test]
    fn every_byte_at_every_position() {
        eprintln!(
            "escape mask: architecture={}, SSE2={}",
            std::env::consts::ARCH,
            cfg!(target_feature = "sse2"),
        );
        for position in 0..16 {
            for byte in 0..=u8::MAX {
                let mut block = [b'x'; 16];
                block[position] = byte;
                let expected = if byte < 0x20 || matches!(byte, b'"' | b'\\') {
                    1 << position
                } else {
                    0
                };
                assert_eq!(mask(&block), expected, "byte {byte}, position {position}");
                assert_eq!(portable(&block), expected);
            }
        }
    }

    #[test]
    fn all_high_bytes_are_plain() {
        for byte in 0x80..=u8::MAX {
            assert_eq!(mask(&[byte; 16]), 0);
        }
    }

    #[test]
    fn adjacent_and_separated_flags_are_exact() {
        for first in 0..16 {
            for second in 0..16 {
                let mut block = [0xff; 16];
                block[first] = b'"';
                block[second] = b'\n';
                assert_eq!(mask(&block), (1 << first) | (1 << second));
            }
        }
        assert_eq!(mask(&[0; 16]), u16::MAX);
        assert_eq!(mask(b"\n.\n.\n.\n.\n.\n.\n.\n."), 0x5555);
    }

    #[test]
    fn unaligned_blocks_and_mixed_bytes() {
        let mut storage = [0_u8; 33];
        for start in 0..16 {
            for rotation in 0..16 {
                for (index, value) in storage.iter_mut().enumerate() {
                    *value =
                        [b'\n', b'x', 0xff, b'\\', 0x7f, 0x80, b'"', 0x1f][(index + rotation) % 8];
                }
                let block = storage[start..start + 16].try_into().unwrap();
                assert_eq!(mask(block), portable(block));
            }
        }
    }
}
