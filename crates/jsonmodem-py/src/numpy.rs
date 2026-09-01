//! NumPy formatting from checked immutable bytes, without borrowing NumPy
//! memory.

use chrono::{Datelike, NaiveDate, NaiveDateTime, Timelike};
use pyo3::{exceptions::PyTypeError, prelude::*, types::PyBytes};

fn datetime(value: i64, unit: &str) -> PyResult<NaiveDateTime> {
    let invalid = || PyTypeError::new_err("unrepresentable numpy.datetime64");
    let result = match unit {
        "Y" | "M" => {
            let (years, month) = if unit == "Y" {
                (value, 1)
            } else {
                (value.div_euclid(12), value.rem_euclid(12) as u32 + 1)
            };
            let year = years
                .checked_add(1970)
                .and_then(|n| i32::try_from(n).ok())
                .ok_or_else(invalid)?;
            NaiveDate::from_ymd_opt(year, month, 1)
                .and_then(|date| date.and_hms_opt(0, 0, 0))
                .ok_or_else(invalid)?
        }
        "W" | "D" | "h" | "m" | "s" | "ms" | "us" | "ns" => {
            let micros = match unit {
                "ns" => Some(value.div_euclid(1000)),
                "us" => Some(value),
                _ => value.checked_mul(match unit {
                    "ms" => 1000,
                    "s" => 1_000_000,
                    "m" => 60_000_000,
                    "h" => 3_600_000_000,
                    "D" => 86_400_000_000,
                    "W" => 604_800_000_000,
                    _ => unreachable!(),
                }),
            }
            .ok_or_else(invalid)?;
            chrono::DateTime::from_timestamp_micros(micros)
                .ok_or_else(invalid)?
                .naive_utc()
        }
        _ => {
            return Err(PyTypeError::new_err(format!(
                "unsupported numpy.datetime64 unit: {}",
                match unit {
                    "ps" => "picoseconds",
                    "fs" => "femtoseconds",
                    "as" => "attoseconds",
                    _ => "generic",
                }
            )));
        }
    };
    if !(0..=9999).contains(&result.year()) {
        return Err(invalid());
    }
    Ok(result)
}

/// Encode a checked value below 100 as two zero-padded ASCII digits.
#[inline]
fn two_digits(value: u32) -> [u8; 2] {
    const DIGIT_PAIRS: [[u8; 2]; 100] = [
        *b"00", *b"01", *b"02", *b"03", *b"04", *b"05", *b"06", *b"07", *b"08", *b"09", *b"10",
        *b"11", *b"12", *b"13", *b"14", *b"15", *b"16", *b"17", *b"18", *b"19", *b"20", *b"21",
        *b"22", *b"23", *b"24", *b"25", *b"26", *b"27", *b"28", *b"29", *b"30", *b"31", *b"32",
        *b"33", *b"34", *b"35", *b"36", *b"37", *b"38", *b"39", *b"40", *b"41", *b"42", *b"43",
        *b"44", *b"45", *b"46", *b"47", *b"48", *b"49", *b"50", *b"51", *b"52", *b"53", *b"54",
        *b"55", *b"56", *b"57", *b"58", *b"59", *b"60", *b"61", *b"62", *b"63", *b"64", *b"65",
        *b"66", *b"67", *b"68", *b"69", *b"70", *b"71", *b"72", *b"73", *b"74", *b"75", *b"76",
        *b"77", *b"78", *b"79", *b"80", *b"81", *b"82", *b"83", *b"84", *b"85", *b"86", *b"87",
        *b"88", *b"89", *b"90", *b"91", *b"92", *b"93", *b"94", *b"95", *b"96", *b"97", *b"98",
        *b"99",
    ];
    debug_assert!(value < 100);
    DIGIT_PAIRS[value as usize]
}

fn write_datetime(output: &mut Vec<u8>, value: i64, unit: &str, option: i32) -> PyResult<()> {
    let date = datetime(value, unit)?;
    let mut text = *b"\"0000-00-00T00:00:00.000000+00:00\"";
    let year = date.year() as u32;
    text[1..3].copy_from_slice(&two_digits(year / 100));
    text[3..5].copy_from_slice(&two_digits(year % 100));
    text[6..8].copy_from_slice(&two_digits(date.month()));
    text[9..11].copy_from_slice(&two_digits(date.day()));
    text[12..14].copy_from_slice(&two_digits(date.hour()));
    text[15..17].copy_from_slice(&two_digits(date.minute()));
    text[18..20].copy_from_slice(&two_digits(date.second()));
    let mut end = 20;
    // datetime() constructs epoch-based or midnight values, never leap seconds.
    let micros = date.nanosecond() / 1000;
    if micros != 0 && option & 8 == 0 {
        text[21..23].copy_from_slice(&two_digits(micros / 10_000));
        text[23..25].copy_from_slice(&two_digits(micros / 100 % 100));
        text[25..27].copy_from_slice(&two_digits(micros % 100));
        end = 27;
    }
    if option & 2 != 0 {
        if option & 128 != 0 {
            text[end] = b'Z';
            end += 1;
        } else {
            text[end..end + 6].copy_from_slice(b"+00:00");
            end += 6;
        }
    }
    text[end] = b'"';
    output.extend_from_slice(&text[..end + 1]);
    Ok(())
}

/// Format checked snapshot bytes with one numeric formatter selected for the
/// call.
fn write_values<const N: usize>(
    data: &[u8],
    shape: &[usize],
    option: i32,
    depth: usize,
    mut item: impl FnMut(&mut Vec<u8>, [u8; N]) -> PyResult<()>,
) -> PyResult<Vec<u8>> {
    let mut output = Vec::with_capacity(data.len().min(65536));
    if shape.is_empty() {
        item(&mut output, data.try_into().expect("checked scalar size"))?;
    } else {
        let mut indices = vec![0usize];
        let mut offset = 0;
        output.push(b'[');
        while let Some(&index) = indices.last() {
            let axis = indices.len() - 1;
            if index == shape[axis] {
                indices.pop();
                if option & 1 != 0 && index != 0 {
                    output.push(b'\n');
                    output.resize(output.len() + 2 * (depth + indices.len()), b' ');
                }
                output.push(b']');
                continue;
            }
            if axis + 1 == shape.len() {
                for column in 0..shape[axis] {
                    if column != 0 {
                        output.push(b',');
                    }
                    if option & 1 != 0 {
                        output.push(b'\n');
                        output.resize(output.len() + 2 * (depth + indices.len()), b' ');
                    }
                    item(
                        &mut output,
                        data[offset..offset + N]
                            .try_into()
                            .expect("checked item size"),
                    )?;
                    offset += N;
                }
                *indices.last_mut().unwrap() = shape[axis];
                continue;
            }
            if index != 0 {
                output.push(b',');
            }
            if option & 1 != 0 {
                output.push(b'\n');
                output.resize(output.len() + 2 * (depth + indices.len()), b' ');
            }
            *indices.last_mut().unwrap() += 1;
            output.push(b'[');
            indices.push(0);
        }
    }
    Ok(output)
}

/// Format only a snapshot whose dimensions and byte length agree.
#[pyfunction]
#[allow(clippy::too_many_arguments)] // Independently checked snapshot fields at the Python boundary.
pub fn _numpy_dumps(
    py: Python<'_>,
    data: Bound<'_, PyBytes>,
    shape: Vec<usize>,
    kind: &str,
    itemsize: usize,
    unit: &str,
    option: i32,
    depth: usize,
) -> PyResult<PyObject> {
    if shape.len() > 64 || !matches!(itemsize, 1 | 2 | 4 | 8) || depth > 254 {
        return Err(PyTypeError::new_err("invalid numpy snapshot metadata"));
    }
    let count = shape
        .iter()
        .try_fold(1usize, |count, size| count.checked_mul(*size))
        .ok_or_else(|| PyTypeError::new_err("numpy shape exceeds addressable memory"))?;
    let bytes = data.as_bytes();
    if count.checked_mul(itemsize) != Some(bytes.len()) {
        return Err(PyTypeError::new_err(
            "numpy snapshot length does not match shape",
        ));
    }
    macro_rules! integer {
        ($type:ty) => {
            write_values::<{ size_of::<$type>() }>(bytes, &shape, option, depth, |out, raw| {
                out.extend_from_slice(
                    itoa::Buffer::new()
                        .format(<$type>::from_ne_bytes(raw))
                        .as_bytes(),
                );
                Ok(())
            })?
        };
    }
    macro_rules! float {
        ($size:literal, $decode:expr) => {
            write_values::<$size>(bytes, &shape, option, depth, |out, raw| {
                let value = ($decode)(raw);
                let mut buffer = zmij::Buffer::new();
                out.extend_from_slice(if value.is_finite() {
                    buffer.format_finite(value).as_bytes()
                } else {
                    b"null"
                });
                Ok(())
            })?
        };
    }
    let output = if count == 0 {
        write_values::<1>(bytes, &shape, option, depth, |_, _| {
            unreachable!("empty array")
        })?
    } else {
        match (kind, itemsize) {
            ("b", 1) => write_values::<1>(bytes, &shape, option, depth, |out, raw| {
                out.extend_from_slice(if raw[0] == 1 { b"true" } else { b"false" });
                Ok(())
            })?,
            ("i", 1) => integer!(i8),
            ("i", 2) => integer!(i16),
            ("i", 4) => integer!(i32),
            ("i", 8) => integer!(i64),
            ("u", 1) => integer!(u8),
            ("u", 2) => integer!(u16),
            ("u", 4) => integer!(u32),
            ("u", 8) => integer!(u64),
            ("f", 2) => float!(2, |raw| half::f16::from_bits(u16::from_ne_bytes(raw))
                .to_f32()),
            ("f", 4) => float!(4, f32::from_ne_bytes),
            ("f", 8) => float!(8, f64::from_ne_bytes),
            ("M", 8) => write_values::<8>(bytes, &shape, option, depth, |out, raw| {
                write_datetime(out, i64::from_ne_bytes(raw), unit, option)
            })?,
            _ => return Err(PyTypeError::new_err("unsupported datatype in numpy array")),
        }
    };
    Ok(crate::compat::bytes_from_vec(py, output)?.into_any())
}
