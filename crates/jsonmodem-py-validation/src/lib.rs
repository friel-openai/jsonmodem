//! Tests Rust dependencies used by the Python bindings without linking Python.

#[cfg(test)]
mod tests {
    fn report_features() {
        #[cfg(any(target_arch = "x86", target_arch = "x86_64"))]
        eprintln!(
            "avx2={} sse4.2={} avx512f={} avx512bw={} avx512vbmi={} avx512vbmi2={}",
            std::is_x86_feature_detected!("avx2"),
            std::is_x86_feature_detected!("sse4.2"),
            std::is_x86_feature_detected!("avx512f"),
            std::is_x86_feature_detected!("avx512bw"),
            std::is_x86_feature_detected!("avx512vbmi"),
            std::is_x86_feature_detected!("avx512vbmi2"),
        );
        #[cfg(all(miri, any(target_arch = "x86", target_arch = "x86_64")))]
        {
            assert_eq!(
                std::is_x86_feature_detected!("avx2"),
                cfg!(target_feature = "avx2")
            );
            assert_eq!(
                std::is_x86_feature_detected!("sse4.2"),
                cfg!(target_feature = "sse4.2")
            );
            assert_eq!(
                std::is_x86_feature_detected!("avx512vbmi2"),
                cfg!(target_feature = "avx512vbmi2")
            );
        }
    }

    fn check(input: &[u8]) {
        match (
            simdutf8::compat::from_utf8(input),
            std::str::from_utf8(input),
        ) {
            (Ok(actual), Ok(expected)) => {
                assert_eq!(actual, expected);
                assert_eq!(actual.as_ptr(), input.as_ptr());
            }
            (Err(actual), Err(expected)) => {
                assert_eq!(actual.valid_up_to(), expected.valid_up_to(), "{input:02x?}");
                assert_eq!(actual.error_len(), expected.error_len(), "{input:02x?}");
            }
            (actual, expected) => panic!("mismatch: {actual:?} {expected:?}; {input:02x?}"),
        }
    }

    #[test]
    fn validates_non_ascii_allocation_tail() {
        report_features();
        let input = [0xc2, 0xa2].repeat(64).into_boxed_slice();
        assert_eq!(
            simdutf8::compat::from_utf8(&input).unwrap(),
            std::str::from_utf8(&input).unwrap()
        );
    }

    #[test]
    fn allocation_ends_and_all_64_alignments() {
        check(&[]);
        for pattern in [
            "A",
            "\u{00a2}",
            "\u{2603}",
            "\u{1f642}",
            "a\u{00a2}\u{2603}\u{1f642}",
        ] {
            let source = pattern.as_bytes().repeat(384 / pattern.len() + 1);
            for base in [0, 64, 128, 192, 256] {
                let mut allocation = vec![0; base + 64].into_boxed_slice();
                let mut seen = [false; 64];
                for offset in 0..64 {
                    let length = allocation.len() - offset;
                    allocation[offset..].copy_from_slice(&source[..length]);
                    let input = &allocation[offset..];
                    seen[input.as_ptr().addr() % 64] = true;
                    check(input);
                }
                assert!(seen.into_iter().all(|observed| observed));
            }
        }
    }

    #[test]
    fn every_byte_at_block_edges() {
        let mut input = vec![b'a'; 257].into_boxed_slice();
        for offset in [0, 1, 31, 32, 63, 64, 127, 128, 255, 256] {
            for byte in 0..=255 {
                input[offset] = byte;
                check(&input);
            }
            input[offset] = b'a';
        }
    }

    #[test]
    fn malformed_sequences_and_scalar_boundaries() {
        let sequences: &[&[u8]] = &[
            &[0xc0, 0x80],
            &[0xc1, 0xbf],
            &[0xe0, 0x80, 0x80],
            &[0xed, 0xa0, 0x80],
            &[0xf0, 0x80, 0x80, 0x80],
            &[0xf4, 0x90, 0x80, 0x80],
            &[0xf5, 0x80, 0x80, 0x80],
            &[0xf0, 0x90, 0x80],
            &[0xe0, 0xa0],
            &[0xc2],
            &[0x80],
        ];
        for offset in [0, 1, 31, 32, 63, 64, 127, 128] {
            for sequence in sequences {
                let mut input = vec![b'a'; offset];
                input.extend_from_slice(sequence);
                check(&input.clone().into_boxed_slice());
                input.extend_from_slice(&[b'a'; 64]);
                check(&input.into_boxed_slice());
            }
            for value in [
                0, 0x7f, 0x80, 0x7ff, 0x800, 0xd7ff, 0xe000, 0xffff, 0x10000, 0x10ffff,
            ] {
                let mut input = vec![b'a'; offset];
                let mut encoded = [0; 4];
                let text = char::from_u32(value).unwrap().encode_utf8(&mut encoded);
                input.extend_from_slice(text.as_bytes());
                check(&input.clone().into_boxed_slice());
                input.extend_from_slice(&[b'a'; 64]);
                check(&input.into_boxed_slice());
            }
        }
    }
}
