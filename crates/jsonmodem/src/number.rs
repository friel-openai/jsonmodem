//! Convert numbers without losing exponent cancellation in long decimals.

#![forbid(unsafe_code)]

use core::num::ParseFloatError;

// Rust's decimal parser stops accumulating an exponent after reaching 65536.
// Below this length, the coefficient cannot cancel a truncated exponent into
// the finite binary64 range. Longer inputs need normalization.
const MIN_LENGTH: usize = 64_512;

// A binary64 rounding midpoint is a * 2^e, with a < 2^54 and -1075 <= e <= 970.
// Its terminating decimal has at most 1075 significant digits. One more digit
// and a nonzero sticky tail preserve the input's relation to every midpoint.
const SIGNIFICANT_DIGITS: usize = 1076;

/// Convert a number to binary64, preserving exponent cancellation in long JSON
/// decimals.
///
/// This converts numbers rather than validating JSON syntax. Non-JSON float
/// spellings retain Rust's `f64::from_str` behavior. Overflow produces
/// infinity; callers that require finite numbers must check the result
/// separately.
///
/// # Errors
/// Returns [`ParseFloatError`] if Rust's float parser rejects the spelling.
#[inline]
pub fn parse_number_f64(text: &str) -> Result<f64, ParseFloatError> {
    if text.len() < MIN_LENGTH {
        text.parse()
    } else {
        normalize_decimal(text).map_or_else(|| text.parse(), Ok)
    }
}

/// Normalize a JSON decimal using bounded storage. Reject non-JSON spellings
/// so the caller can preserve Rust's parsing behavior for those inputs.
#[cold]
#[inline(never)]
fn normalize_decimal(text: &str) -> Option<f64> {
    let negative = text.starts_with('-');
    let unsigned = if negative { &text[1..] } else { text };
    let (coefficient, exponent) = match unsigned.find(['e', 'E']) {
        Some(index) => (&unsigned[..index], Some(&unsigned[index + 1..])),
        None => (unsigned, None),
    };
    let (integer, fraction) = match coefficient.split_once('.') {
        Some((integer, fraction)) if !fraction.is_empty() => (integer, fraction),
        Some(_) => return None,
        None => (coefficient, ""),
    };
    if integer.is_empty() || (integer.len() > 1 && integer.starts_with('0')) {
        return None;
    }

    // The coefficient's decimal-position adjustment is bounded by text.len().
    // Anything beyond this cap remains outside binary64 range after cancellation.
    let exponent = explicit_exponent(exponent, text.len())?;
    let mut output = [0_u8; SIGNIFICANT_DIGITS + 16];
    let mut length = usize::from(negative);
    if negative {
        output[0] = b'-';
    }
    let mut leading_zeros = 0_usize;
    let mut retained = 0;
    let mut sticky = false;
    for byte in integer.bytes().chain(fraction.bytes()) {
        if !byte.is_ascii_digit() {
            return None;
        }
        if retained == 0 && byte == b'0' {
            leading_zeros += 1;
        } else if retained < SIGNIFICANT_DIGITS {
            if retained == 1 {
                output[length] = b'.';
                length += 1;
            }
            output[length] = byte;
            length += 1;
            retained += 1;
        } else {
            sticky |= byte != b'0';
        }
    }
    if retained == 0 {
        return Some(if negative { -0.0 } else { 0.0 });
    }
    let exponent = exponent + integer.len() as i128 - leading_zeros as i128 - 1;
    if exponent < -324 {
        return Some(if negative { -0.0 } else { 0.0 });
    }
    if exponent > 308 {
        return Some(if negative {
            f64::NEG_INFINITY
        } else {
            f64::INFINITY
        });
    }
    if sticky {
        // Appending, rather than incrementing, cannot carry across a midpoint.
        output[length] = b'1';
        length += 1;
    }
    output[length] = b'e';
    length += 1;
    if exponent < 0 {
        output[length] = b'-';
        length += 1;
    }
    let magnitude = u16::try_from(exponent.unsigned_abs()).expect("exponent is in -324..=308");
    if magnitude >= 100 {
        output[length] = b'0' + u8::try_from(magnitude / 100).unwrap();
        length += 1;
    }
    if magnitude >= 10 {
        output[length] = b'0' + u8::try_from(magnitude / 10 % 10).unwrap();
        length += 1;
    }
    output[length] = b'0' + u8::try_from(magnitude % 10).unwrap();
    length += 1;
    let normalized = core::str::from_utf8(&output[..length]).expect("normalized decimal is ASCII");
    Some(
        normalized
            .parse()
            .expect("normalized decimal is a valid float"),
    )
}

fn explicit_exponent(text: Option<&str>, input_length: usize) -> Option<i128> {
    let cap = input_length as i128 + 1024;
    let Some(text) = text else {
        return Some(0);
    };
    let (negative, digits) = match text.as_bytes().first() {
        Some(b'-') => (true, &text[1..]),
        Some(b'+') => (false, &text[1..]),
        _ => (false, text),
    };
    if digits.is_empty() {
        return None;
    }
    let mut value = 0_i128;
    for byte in digits.bytes() {
        if !byte.is_ascii_digit() {
            return None;
        }
        value = (value * 10 + i128::from(byte - b'0')).min(cap);
    }
    Some(if negative { -value } else { value })
}

#[cfg(test)]
mod tests {
    use alloc::{
        borrow::{Cow, ToOwned},
        format,
        string::{String, ToString},
        vec,
    };

    use super::*;
    use crate::{LexemeBackend, RawContext, StdBackend, context::EventCtx};

    fn bits(text: &str, expected: f64) {
        assert_eq!(
            normalize_decimal(text).unwrap().to_bits(),
            expected.to_bits(),
            "{text}"
        );
    }

    #[test]
    fn decimal_positions_and_cancellation() {
        bits("1", 1.0);
        bits("-1.25e+2", -125.0);
        bits("0.001e3", 1.0);
        bits("123456e-5", 1.234_56);
        bits(&format!("1{}e-2048", "0".repeat(2048)), 1.0);
        bits(&format!("0.{}1e2049", "0".repeat(2048)), 1.0);
    }

    #[test]
    fn unbounded_exponents_and_signed_zero() {
        for exponent in [
            "9223372036854775807",
            "9223372036854775808",
            "999999999999999999999999999999",
        ] {
            bits(&format!("1e{exponent}"), f64::INFINITY);
            bits(&format!("-1e{exponent}"), f64::NEG_INFINITY);
            bits(&format!("1e-{exponent}"), 0.0);
            bits(&format!("-1e-{exponent}"), -0.0);
            bits(&format!("0e{exponent}"), 0.0);
            bits(&format!("-0.0e-{exponent}"), -0.0);
        }
        bits("1.0e-9223372036854775808", 0.0);
        bits("1e00000000000000000000000000000000000000000001", 10.0);
        bits("-0", -0.0);
        for coefficient in ["0".to_owned(), format!("0.{}", "0".repeat(1076))] {
            for sign in ['+', '-'] {
                let text = format!("{coefficient}e{sign}{}", "9".repeat(100));
                bits(&text, 0.0);
                bits(&format!("-{text}"), -0.0);
            }
        }
    }

    #[test]
    fn ties_and_discarded_nonzero_digits() {
        let midpoint = "1.00000000000000011102230246251565404236316680908203125";
        bits(midpoint, 1.0);
        bits(&format!("{midpoint}{}", "0".repeat(2048)), 1.0);
        bits(
            &format!("{midpoint}{}1", "0".repeat(2048)),
            f64::from_bits(1.0_f64.to_bits() + 1),
        );
        bits(
            &format!("-{midpoint}{}1", "0".repeat(2048)),
            -f64::from_bits(1.0_f64.to_bits() + 1),
        );
    }

    #[test]
    fn finite_and_underflow_boundaries() {
        bits("1.7976931348623157e308", f64::MAX);
        bits("1.7976931348623159e308", f64::INFINITY);
        bits("2.2250738585072014e-308", f64::MIN_POSITIVE);
        bits(
            "2.2250738585072011e-308",
            f64::from_bits(0x000f_ffff_ffff_ffff),
        );
        bits("2.4703282292062327e-324", 0.0);
        bits("2.4703282292062328e-324", f64::from_bits(1));
        bits("1e-325", 0.0);
        bits("1e309", f64::INFINITY);
    }

    #[test]
    fn direct_invalid_inputs_are_rejected() {
        for text in [
            "",
            "-",
            "+1",
            "01",
            "-01",
            ".1",
            "1.",
            "1..2",
            "1e",
            "1e+",
            "1e-",
            "1e2e3",
            "1e\u{00e9}",
            "NaN",
            "inf",
            "1  ",
        ] {
            assert!(normalize_decimal(text).is_none(), "{text}");
        }
        assert!(normalize_decimal("0e99999x").is_none());
        assert!(normalize_decimal(&format!("1{}x", "0".repeat(1140))).is_none());
    }

    #[test]
    fn dispatch_underflow_cancellation() {
        // 65,545 bytes: the old exponent parser retains -65536 rather than
        // -655360, which incorrectly cancels the integer's 65,536 zeros.
        let text = format!("1{}e-655360", "0".repeat(65_536));
        assert_eq!(text.len(), 65_545);
        assert_eq!(
            parse_number_f64(&text).unwrap().to_bits(),
            0.0_f64.to_bits()
        );
        assert_eq!(
            parse_number_f64(&format!("-{text}")).unwrap().to_bits(),
            (-0.0_f64).to_bits()
        );
    }

    #[test]
    fn dispatch_overflow_cancellation() {
        // 65,545 bytes: the coefficient's position is -65536, but the exact
        // explicit exponent is 655360. The result must overflow, not equal 1.
        let text = format!("0.{}1e655360", "0".repeat(65_535));
        assert_eq!(text.len(), 65_545);
        assert_eq!(
            parse_number_f64(&text).unwrap().to_bits(),
            f64::INFINITY.to_bits()
        );
        assert_eq!(
            parse_number_f64(&format!("-{text}")).unwrap().to_bits(),
            f64::NEG_INFINITY.to_bits()
        );
    }

    fn finite_cancellation_text() -> String {
        // 655,370 bytes: all 655,361 decimal places cancel exactly. Truncating
        // the exponent incorrectly underflows this value to zero.
        let text = format!("0.{}1e655361", "0".repeat(655_360));
        assert_eq!(text.len(), 655_370);
        text
    }

    // Each sign gets its own Miri timeout without shortening either input.
    #[test]
    fn dispatch_finite_cancellation_positive() {
        let text = finite_cancellation_text();
        assert_eq!(
            parse_number_f64(&text).unwrap().to_bits(),
            1.0_f64.to_bits()
        );
    }

    #[test]
    fn dispatch_finite_cancellation_negative() {
        let text = format!("-{}", finite_cancellation_text());
        assert_eq!(text.len(), 655_371);
        assert_eq!(
            parse_number_f64(&text).unwrap().to_bits(),
            (-1.0_f64).to_bits()
        );
    }

    #[test]
    fn conversion_preserves_rust_spellings_and_errors() {
        for text in [
            "", "-", "+1", "01", "-01", ".1", "1.", "NaN", "inf", "-inf", "1e", "1 ", "1x",
        ] {
            assert_eq!(
                parse_number_f64(text).map(f64::to_bits),
                text.parse::<f64>().map(f64::to_bits)
            );
        }
        for text in [
            format!("+0.{}1", "0".repeat(MIN_LENGTH)),
            format!("{}1e0", "0".repeat(MIN_LENGTH)),
            format!("1{}e", "0".repeat(MIN_LENGTH)),
            format!("0e{}x", "9".repeat(MIN_LENGTH)),
        ] {
            assert!(text.len() >= MIN_LENGTH);
            assert!(normalize_decimal(&text).is_none());
            assert_eq!(
                parse_number_f64(&text).map(f64::to_bits),
                text.parse::<f64>().map(f64::to_bits)
            );
        }
    }

    fn materializing_backends(text: &str, expected: f64) {
        let mut standard = StdBackend::new();
        let mut raw = RawContext;
        let results: [Result<f64, ParseFloatError>; 4] = [
            standard.new_number(text),
            standard.new_number_owned(text.into()),
            raw.new_number(text),
            raw.new_number_owned(text.into()),
        ];
        for result in results {
            assert_eq!(result.unwrap().to_bits(), expected.to_bits());
        }
    }

    #[test]
    fn backends_convert_borrowed_and_owned_long_numbers() {
        let text = format!("1{}e-655360", "0".repeat(65_536));
        materializing_backends(&text, 0.0);
        materializing_backends(&format!("-{text}"), -0.0);
    }

    #[test]
    fn backends_preserve_overflow_policy() {
        let text = format!("0.{}1e655360", "0".repeat(65_535));
        materializing_backends(&text, f64::INFINITY);
        materializing_backends(&format!("-{text}"), f64::NEG_INFINITY);
        let mut lexeme = LexemeBackend;
        assert!(lexeme.new_number(&text).is_err());
        assert!(lexeme.new_number_owned(text).is_err());
    }

    #[test]
    fn lexeme_backend_preserves_large_integers() {
        // This integer exceeds finite binary64 range but needs no float check.
        let text = "9".repeat(400);
        let mut backend = LexemeBackend;
        let borrowed = backend.new_number(&text).unwrap();
        assert!(matches!(borrowed, Cow::Borrowed(_)));
        assert_eq!(borrowed.as_ref(), text);
        let owned = backend.new_number_owned(text.clone()).unwrap();
        assert!(matches!(owned, Cow::Owned(_)));
        assert_eq!(owned.as_ref(), text);
    }

    // Decimal integer arithmetic constructs the exact midpoint a * 2^e.
    // Expected results below are IEEE 754 bit patterns, not another parser.
    fn midpoint_decimal(a: u64, exponent: i32) -> (String, i32) {
        let mut digits = a.to_string().into_bytes();
        let factor = if exponent < 0 { 5_u16 } else { 2_u16 };
        for _ in 0..exponent.unsigned_abs() {
            let mut carry = 0_u16;
            for digit in digits.iter_mut().rev() {
                let value = u16::from(*digit - b'0') * factor + carry;
                *digit = b'0' + u8::try_from(value % 10).unwrap();
                carry = value / 10;
            }
            if carry != 0 {
                digits.insert(0, b'0' + u8::try_from(carry).unwrap());
            }
        }
        (String::from_utf8(digits).unwrap(), exponent.min(0))
    }

    fn adjacent_decimal(text: &str, delta: i8) -> String {
        let mut digits = text.as_bytes().to_vec();
        for digit in digits.iter_mut().rev() {
            let adjusted = i8::try_from(*digit - b'0').unwrap() + delta;
            if (0..=9).contains(&adjusted) {
                *digit = b'0' + u8::try_from(adjusted).unwrap();
                return String::from_utf8(digits).unwrap();
            }
            *digit = if delta < 0 { b'9' } else { b'0' };
        }
        panic!("test midpoint crosses a power of ten");
    }

    // Each boundary has 50 signed forms. Separate tests keep the work per
    // test bounded under Miri without dropping any midpoint comparisons.
    fn exact_midpoint(a: u64, exponent: i32, lower: u64, upper: u64) {
        let (midpoint, exponent) = midpoint_decimal(a, exponent);
        assert!(midpoint.len() <= 1075);
        let mut checked = 0;
        for length in [0_usize, 1076, 1077, 1140] {
            let deltas: &[i8] = match length {
                0 => &[0],
                1140 => &[-1, 0, 1],
                _ => &[-1, 1],
            };
            for &delta in deltas {
                let padding = length.saturating_sub(midpoint.len());
                let digits = format!("{midpoint}{}", "0".repeat(padding));
                let digits = adjacent_decimal(&digits, delta);
                let power = exponent - i32::try_from(padding).unwrap();
                let expected = match delta {
                    -1 => lower,
                    1 => upper,
                    _ => {
                        if lower & 1 == 0 {
                            lower
                        } else {
                            upper
                        }
                    }
                };
                let mut forms = vec![format!("{digits}e{power}")];
                if length == 1140 {
                    for position in [1, 19, 768] {
                        forms.push(format!(
                            "{}.{}e{}",
                            &digits[..position],
                            &digits[position..],
                            power + i32::try_from(digits.len() - position).unwrap()
                        ));
                    }
                }
                if length == 0 || length == 1140 {
                    for leading in [1, 1076] {
                        let power = power + i32::try_from(digits.len() + leading).unwrap();
                        let sign = if power < 0 { '-' } else { '+' };
                        forms.push(format!(
                            "0.{}{digits}E{sign}00000000{}",
                            "0".repeat(leading),
                            power.unsigned_abs()
                        ));
                    }
                }
                for text in forms {
                    bits(&text, f64::from_bits(expected));
                    bits(&format!("-{text}"), f64::from_bits(expected | (1 << 63)));
                    checked += 2;
                }
            }
        }
        assert_eq!(checked, 50);
    }

    #[test]
    fn midpoint_zero_to_min_subnormal() {
        exact_midpoint(1, -1075, 0, 1);
    }

    #[test]
    fn midpoint_subnormal_tie_up() {
        exact_midpoint(3, -1075, 1, 2);
    }

    #[test]
    fn midpoint_max_subnormal_to_min_normal() {
        exact_midpoint(
            (1 << 53) - 1,
            -1075,
            0x000f_ffff_ffff_ffff,
            0x0010_0000_0000_0000,
        );
    }

    #[test]
    fn midpoint_min_normal_tie_down() {
        exact_midpoint(
            (1 << 53) + 1,
            -1075,
            0x0010_0000_0000_0000,
            0x0010_0000_0000_0001,
        );
    }

    #[test]
    fn midpoint_first_normal_spacing_change() {
        exact_midpoint(
            (1 << 54) - 1,
            -1075,
            0x001f_ffff_ffff_ffff,
            0x0020_0000_0000_0000,
        );
    }

    #[test]
    fn midpoint_below_one() {
        exact_midpoint(
            (1 << 54) - 1,
            -54,
            0x3fef_ffff_ffff_ffff,
            0x3ff0_0000_0000_0000,
        );
    }

    #[test]
    fn midpoint_above_one_tie_down() {
        exact_midpoint(
            (1 << 53) + 1,
            -53,
            0x3ff0_0000_0000_0000,
            0x3ff0_0000_0000_0001,
        );
    }

    #[test]
    fn midpoint_above_one_tie_up() {
        exact_midpoint(
            (1 << 53) + 3,
            -53,
            0x3ff0_0000_0000_0001,
            0x3ff0_0000_0000_0002,
        );
    }

    #[test]
    fn midpoint_below_max_finite() {
        exact_midpoint(
            (1 << 54) - 3,
            970,
            0x7fef_ffff_ffff_fffe,
            0x7fef_ffff_ffff_ffff,
        );
    }

    #[test]
    fn midpoint_max_finite_to_infinity() {
        exact_midpoint(
            (1 << 54) - 1,
            970,
            0x7fef_ffff_ffff_ffff,
            0x7ff0_0000_0000_0000,
        );
    }

    #[test]
    fn exponent_saturation_preserves_cancellation() {
        for magnitude in [5119_i128, 5120, 5121] {
            for negative in [false, true] {
                for padding in ["", "00000000000000000000"] {
                    let sign = if negative { "-" } else { "" };
                    let text = format!("{sign}{padding}{magnitude}");
                    let actual = explicit_exponent(Some(&text), 4096).unwrap();
                    let expected = if negative { -magnitude } else { magnitude };
                    for position in [-4032, 0, 4032] {
                        assert_eq!(actual + position < -324, expected + position < -324);
                        assert_eq!(actual + position > 308, expected + position > 308);
                    }
                }
            }
        }
        #[cfg(target_pointer_width = "64")]
        {
            let length = usize::try_from(i64::MAX).unwrap();
            assert_eq!(
                explicit_exponent(Some("9223372036854775808"), length).unwrap() - length as i128
                    + 100,
                101
            );
            assert_eq!(
                explicit_exponent(Some("-9223372036854775809"), length).unwrap() + length as i128
                    - 100,
                -102
            );
            assert_eq!(
                explicit_exponent(Some("999999999999999999999999999999"), usize::MAX).unwrap(),
                usize::MAX as i128 + 1024
            );
        }
    }
}
