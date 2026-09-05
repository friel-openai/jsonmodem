//! String classification restricted to one initialized, in-bounds block.

/// Bit i marks a quote, backslash, control byte, or an optionally non-ASCII
/// byte.
#[inline]
pub(crate) fn mask<const ASCII_ONLY: bool>(block: &[u8; 16]) -> u16 {
    #[cfg(all(feature = "simd", target_arch = "x86_64", target_feature = "sse2"))]
    {
        native::mask::<ASCII_ONLY>(block)
    }
    #[cfg(not(all(feature = "simd", target_arch = "x86_64", target_feature = "sse2")))]
    {
        portable::<ASCII_ONLY>(block)
    }
}

#[cfg(any(
    test,
    not(all(feature = "simd", target_arch = "x86_64", target_feature = "sse2"))
))]
fn portable<const ASCII_ONLY: bool>(block: &[u8; 16]) -> u16 {
    block.iter().enumerate().fold(0, |mask, (index, &byte)| {
        mask | (u16::from(
            byte < 0x20 || matches!(byte, b'"' | b'\\') || (ASCII_ONLY && !byte.is_ascii()),
        ) << index)
    })
}

#[cfg(all(feature = "simd", target_arch = "x86_64", target_feature = "sse2"))]
#[allow(unsafe_code)]
mod native {
    use core::arch::x86_64::{
        _mm_cmpeq_epi8, _mm_loadu_si128, _mm_max_epu8, _mm_movemask_epi8, _mm_or_si128,
        _mm_set1_epi8,
    };

    #[inline]
    pub(super) fn mask<const ASCII_ONLY: bool>(block: &[u8; 16]) -> u16 {
        // SAFETY: the reference supplies 16 initialized bytes. The unaligned
        // load reads only those bytes. SSE2 is a compile-time requirement;
        // no pointer or reference escapes, and no memory is written.
        unsafe {
            let bytes = _mm_loadu_si128(block.as_ptr().cast());
            let limit = _mm_set1_epi8(0x1f);
            let controls = _mm_cmpeq_epi8(_mm_max_epu8(bytes, limit), limit);
            let quotes = _mm_cmpeq_epi8(bytes, _mm_set1_epi8(0x22));
            let slashes = _mm_cmpeq_epi8(bytes, _mm_set1_epi8(0x5c));
            let special = _mm_or_si128(controls, _mm_or_si128(quotes, slashes));
            let flags = _mm_movemask_epi8(if ASCII_ONLY {
                _mm_or_si128(special, bytes)
            } else {
                special
            });
            u16::try_from(flags).expect("SSE2 mask has sixteen bits")
        }
    }
}

#[cfg(test)]
mod tests {
    use alloc::vec;

    use super::{mask, portable};

    #[test]
    fn every_byte_and_lane() {
        std::eprintln!(
            "string block SIMD={}",
            cfg!(all(
                feature = "simd",
                target_arch = "x86_64",
                target_feature = "sse2"
            ))
        );
        for lane in 0..16 {
            for byte in 0..=u8::MAX {
                let mut block = [b'x'; 16];
                block[lane] = byte;
                assert_eq!(mask::<false>(&block), portable::<false>(&block));
                assert_eq!(mask::<true>(&block), portable::<true>(&block));
            }
        }
    }

    #[test]
    fn exact_bits_after_adjacent_special_bytes() {
        for pair in [*b"\"#", *b"\\]", [0x1f, b' '], [0x80, 0xff]] {
            for lane in 0..15 {
                let mut block = [b'x'; 16];
                block[lane..lane + 2].copy_from_slice(&pair);
                assert_eq!(mask::<false>(&block), portable::<false>(&block));
                assert_eq!(mask::<true>(&block), portable::<true>(&block));
            }
        }
    }

    #[test]
    fn allocation_end_at_every_alignment() {
        for offset in 0..16 {
            let mut allocation = vec![b'x'; offset + 16].into_boxed_slice();
            for (index, byte) in allocation[offset..].iter_mut().enumerate() {
                *byte = [b'"', b'\\', b'\n', 0x80, 0xff, b'x'][index % 6];
            }
            let block = allocation[offset..].try_into().unwrap();
            assert_eq!(mask::<false>(block), portable::<false>(block));
            assert_eq!(mask::<true>(block), portable::<true>(block));
        }
    }

    #[test]
    fn uniform_blocks_and_all_flag_pairs() {
        for byte in 0..=u8::MAX {
            let block = [byte; 16];
            assert_eq!(mask::<false>(&block), portable::<false>(&block));
            assert_eq!(mask::<true>(&block), portable::<true>(&block));
        }
        for first in 0..16 {
            for second in 0..16 {
                let mut block = [0xff; 16];
                block[first] = b'"';
                block[second] = b'\n';
                assert_eq!(mask::<false>(&block), (1 << first) | (1 << second));
            }
        }
    }
}
