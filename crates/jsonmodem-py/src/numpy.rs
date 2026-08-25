//! NumPy formatting from checked immutable bytes, without borrowing NumPy
//! memory.

use std::io::Write;

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

fn write_datetime(output: &mut Vec<u8>, value: i64, unit: &str, option: i32) -> PyResult<()> {
    let date = datetime(value, unit)?;
    write!(
        output,
        "\"{:04}-{:02}-{:02}T{:02}:{:02}:{:02}",
        date.year(),
        date.month(),
        date.day(),
        date.hour(),
        date.minute(),
        date.second()
    )
    .expect("Vec write");
    let micros = date.nanosecond() / 1000;
    if micros != 0 && option & 8 == 0 {
        write!(output, ".{micros:06}").expect("Vec write");
    }
    if option & 2 != 0 {
        output.extend_from_slice(if option & 128 != 0 { b"Z" } else { b"+00:00" });
    }
    output.push(b'"');
    Ok(())
}

fn item(output: &mut Vec<u8>, bytes: &[u8], kind: &str, unit: &str, option: i32) -> PyResult<()> {
    let mut integer = itoa::Buffer::new();
    let mut float = zmij::Buffer::new();
    match (kind, bytes.len()) {
        ("b", 1) => output.extend_from_slice(if bytes[0] == 1 { b"true" } else { b"false" }),
        ("i", size) => {
            let value = match size {
                1 => i64::from(i8::from_ne_bytes(bytes.try_into().unwrap())),
                2 => i64::from(i16::from_ne_bytes(bytes.try_into().unwrap())),
                4 => i64::from(i32::from_ne_bytes(bytes.try_into().unwrap())),
                8 => i64::from_ne_bytes(bytes.try_into().unwrap()),
                _ => return Err(PyTypeError::new_err("unsupported numpy integer size")),
            };
            output.extend_from_slice(integer.format(value).as_bytes());
        }
        ("u", size) => {
            let value = match size {
                1 => u64::from(bytes[0]),
                2 => u64::from(u16::from_ne_bytes(bytes.try_into().unwrap())),
                4 => u64::from(u32::from_ne_bytes(bytes.try_into().unwrap())),
                8 => u64::from_ne_bytes(bytes.try_into().unwrap()),
                _ => return Err(PyTypeError::new_err("unsupported numpy integer size")),
            };
            output.extend_from_slice(integer.format(value).as_bytes());
        }
        ("f", 2 | 4) => {
            let value = if bytes.len() == 2 {
                half::f16::from_bits(u16::from_ne_bytes(bytes.try_into().unwrap())).to_f32()
            } else {
                f32::from_ne_bytes(bytes.try_into().unwrap())
            };
            output.extend_from_slice(if value.is_finite() {
                float.format_finite(value).as_bytes()
            } else {
                b"null"
            });
        }
        ("f", 8) => {
            let value = f64::from_ne_bytes(bytes.try_into().unwrap());
            output.extend_from_slice(if value.is_finite() {
                float.format_finite(value).as_bytes()
            } else {
                b"null"
            });
        }
        ("M", 8) => write_datetime(
            output,
            i64::from_ne_bytes(bytes.try_into().unwrap()),
            unit,
            option,
        )?,
        _ => return Err(PyTypeError::new_err("unsupported datatype in numpy array")),
    }
    Ok(())
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
    if count.checked_mul(itemsize) != Some(data.as_bytes().len()) {
        return Err(PyTypeError::new_err(
            "numpy snapshot length does not match shape",
        ));
    }
    let mut output = Vec::with_capacity(data.as_bytes().len().min(65536));
    if shape.is_empty() {
        item(&mut output, data.as_bytes(), kind, unit, option)?;
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
            if index != 0 {
                output.push(b',');
            }
            if option & 1 != 0 {
                output.push(b'\n');
                output.resize(output.len() + 2 * (depth + indices.len()), b' ');
            }
            *indices.last_mut().unwrap() += 1;
            if axis + 1 == shape.len() {
                item(
                    &mut output,
                    &data.as_bytes()[offset..offset + itemsize],
                    kind,
                    unit,
                    option,
                )?;
                offset += itemsize;
            } else {
                output.push(b'[');
                indices.push(0);
            }
        }
    }
    Ok(PyBytes::new(py, &output).into_any().unbind())
}
