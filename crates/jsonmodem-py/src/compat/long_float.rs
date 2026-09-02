//! Normalize exceptionally long decimals before binary64 conversion.

#![forbid(unsafe_code)]

use lexical_parse_float::{Error, FromLexical};

// lexical-parse-float 1.0.5 stops accumulating an exponent after reaching
// 0x10000000. Below this input length, the coefficient cannot cancel a
// truncated exponent into the finite binary64 range. Longer inputs need
// normalization.
pub(super) const MIN_LENGTH: usize = 0x10000000 - 1024;

// A binary64 rounding midpoint is a * 2^e, with a < 2^54 and -1075 <= e <= 970.
// Its terminating decimal has at most 1075 significant digits. One more digit
// and a nonzero sticky tail preserve the input's relation to every midpoint.
const SIGNIFICANT_DIGITS: usize = 1076;

/// Convert a decimal using bounded storage and an exponent that cannot
/// overflow. Normal decoding has already checked JSON grammar; checking it here
/// also keeps direct callers from silently normalizing an invalid
/// representation.
#[cold]
#[inline(never)]
pub(super) fn parse(text: &str) -> Result<f64, Error> {
    let negative = text.starts_with('-');
    let unsigned = if negative { &text[1..] } else { text };
    let (coefficient, exponent) = match unsigned.find(['e', 'E']) {
        Some(index) => (&unsigned[..index], Some(&unsigned[index + 1..])),
        None => (unsigned, None),
    };
    let (integer, fraction) = match coefficient.split_once('.') {
        Some((integer, fraction)) if !fraction.is_empty() => (integer, fraction),
        Some(_) => return Err(Error::InvalidDigit(0)),
        None => (coefficient, ""),
    };
    if integer.is_empty() || (integer.len() > 1 && integer.starts_with('0')) {
        return Err(Error::InvalidDigit(0));
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
            return Err(Error::InvalidDigit(0));
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
        return Ok(if negative { -0.0 } else { 0.0 });
    }
    let exponent = exponent + integer.len() as i128 - leading_zeros as i128 - 1;
    if exponent < -324 {
        return Ok(if negative { -0.0 } else { 0.0 });
    }
    if exponent > 308 {
        return Ok(if negative {
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
    let mut exponent_buffer = itoa::Buffer::new();
    let exponent = exponent_buffer.format(exponent);
    output[length..length + exponent.len()].copy_from_slice(exponent.as_bytes());
    length += exponent.len();
    f64::from_lexical(&output[..length])
}

fn explicit_exponent(text: Option<&str>, input_length: usize) -> Result<i128, Error> {
    let cap = input_length as i128 + 1024;
    let Some(text) = text else {
        return Ok(0);
    };
    let (negative, digits) = match text.as_bytes().first() {
        Some(b'-') => (true, &text[1..]),
        Some(b'+') => (false, &text[1..]),
        _ => (false, text),
    };
    if digits.is_empty() {
        return Err(Error::EmptyExponent(0));
    }
    let mut value = 0_i128;
    for byte in digits.bytes() {
        if !byte.is_ascii_digit() {
            return Err(Error::InvalidDigit(0));
        }
        value = (value * 10 + i128::from(byte - b'0')).min(cap);
    }
    Ok(if negative { -value } else { value })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn bits(text: &str, expected: f64) {
        assert_eq!(parse(text).unwrap().to_bits(), expected.to_bits(), "{text}");
    }

    #[test]
    fn decimal_positions_and_cancellation() {
        bits("1", 1.0);
        bits("-1.25e+2", -125.0);
        bits("0.001e3", 1.0);
        bits("123456e-5", 1.23456);
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
            assert!(parse(text).is_err(), "{text}");
        }
        assert!(parse("0e99999x").is_err());
        assert!(parse(&format!("1{}x", "0".repeat(1140))).is_err());
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
                *digit = b'0' + (value % 10) as u8;
                carry = value / 10;
            }
            if carry != 0 {
                digits.insert(0, b'0' + carry as u8);
            }
        }
        (String::from_utf8(digits).unwrap(), exponent.min(0))
    }

    fn adjacent_decimal(text: &str, delta: i8) -> String {
        let mut digits = text.as_bytes().to_vec();
        for digit in digits.iter_mut().rev() {
            let adjusted = (*digit - b'0') as i8 + delta;
            if (0..=9).contains(&adjusted) {
                *digit = b'0' + adjusted as u8;
                return String::from_utf8(digits).unwrap();
            }
            *digit = if delta < 0 { b'9' } else { b'0' };
        }
        panic!("test midpoint crosses a power of ten");
    }

    #[test]
    fn exact_midpoints_with_significant_and_discarded_tails() {
        // (a, e, lower result, upper result) for a * 2^e. Include both tie
        // directions and the changes in spacing at zero, normal values and 1.
        let boundaries: &[(u64, i32, u64, u64)] = &[
            (1, -1075, 0, 1),
            (3, -1075, 1, 2),
            (
                (1 << 53) - 1,
                -1075,
                0x000f_ffff_ffff_ffff,
                0x0010_0000_0000_0000,
            ),
            (
                (1 << 53) + 1,
                -1075,
                0x0010_0000_0000_0000,
                0x0010_0000_0000_0001,
            ),
            (
                (1 << 54) - 1,
                -1075,
                0x001f_ffff_ffff_ffff,
                0x0020_0000_0000_0000,
            ),
            (
                (1 << 54) - 1,
                -54,
                0x3fef_ffff_ffff_ffff,
                0x3ff0_0000_0000_0000,
            ),
            (
                (1 << 53) + 1,
                -53,
                0x3ff0_0000_0000_0000,
                0x3ff0_0000_0000_0001,
            ),
            (
                (1 << 53) + 3,
                -53,
                0x3ff0_0000_0000_0001,
                0x3ff0_0000_0000_0002,
            ),
            (
                (1 << 54) - 3,
                970,
                0x7fef_ffff_ffff_fffe,
                0x7fef_ffff_ffff_ffff,
            ),
            (
                (1 << 54) - 1,
                970,
                0x7fef_ffff_ffff_ffff,
                0x7ff0_0000_0000_0000,
            ),
        ];
        let mut checked = 0;
        for &(a, exponent, lower, upper) in boundaries {
            let (midpoint, exponent) = midpoint_decimal(a, exponent);
            assert!(midpoint.len() <= 1075);
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
                    let power = exponent - padding as i32;
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
                                power + (digits.len() - position) as i32
                            ));
                        }
                    }
                    if length == 0 || length == 1140 {
                        for leading in [1, 1076] {
                            let power = power + (digits.len() + leading) as i32;
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
        }
        assert_eq!(checked, 500);
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
            let length = i64::MAX as usize;
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
