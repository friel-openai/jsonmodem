//! Exact date/time fields can be written without allocating Python strings.

use pyo3::prelude::*;
#[cfg(not(any(Py_LIMITED_API, Py_GIL_DISABLED, PyPy, GraalPy)))]
use pyo3::types::{
    PyDate, PyDateAccess, PyDateTime, PyDelta, PyDeltaAccess, PyTime, PyTimeAccess, PyTzInfo,
    PyTzInfoAccess,
};

use super::{Encoder, output};

#[cfg(not(any(Py_LIMITED_API, Py_GIL_DISABLED, PyPy, GraalPy)))]
pub(super) fn write(
    encoder: &mut Encoder<true, output::Output<'_>>,
    value: &Bound<'_, PyAny>,
) -> PyResult<bool> {
    const NAIVE_UTC: i32 = 2;
    const OMIT_MICROSECONDS: i32 = 8;
    const UTC_Z: i32 = 128;
    const PASSTHROUGH_DATETIME: i32 = 512;

    if encoder.option & PASSTHROUGH_DATETIME != 0 {
        return Ok(false);
    }
    // Initialize fallibly before PyO3's datetime type checks. If the C API is
    // unavailable, the existing Python helper can still serialize this value.
    let Ok(utc) = PyTzInfo::utc(value.py()) else {
        return Ok(false);
    };
    let mut formatted = FormattedDateTime::new();
    if value.is_exact_instance_of::<PyDateTime>() {
        let datetime = value.downcast::<PyDateTime>()?;
        let offset_seconds = match datetime.get_tzinfo() {
            Some(timezone) if timezone.is(utc) => Some(0),
            Some(timezone) if timezone.get_type().is(utc.get_type()) => {
                let offset =
                    timezone.call_method1(pyo3::intern!(value.py(), "utcoffset"), (datetime,))?;
                // A timedelta subclass can override the fields used by the
                // Python formatter. Keep that behavior instead of reading its
                // native fields. The builtin method returns its stored offset.
                if !offset.is_exact_instance_of::<PyDelta>() {
                    return Ok(false);
                }
                let offset = offset.downcast::<PyDelta>()?;
                Some(i64::from(offset.get_days()) * 86_400 + i64::from(offset.get_seconds()))
            }
            Some(_) => return Ok(false),
            None => (encoder.option & NAIVE_UTC != 0).then_some(0),
        };
        if !formatted.date(datetime) {
            return Ok(false);
        }
        formatted.push(b'T');
        if !formatted.time(datetime, encoder.option & OMIT_MICROSECONDS != 0) {
            return Ok(false);
        }
        if let Some(seconds) = offset_seconds {
            if seconds == 0 {
                if encoder.option & UTC_Z != 0 {
                    formatted.push(b'Z');
                } else {
                    formatted.bytes[formatted.len..formatted.len + 6].copy_from_slice(b"+00:00");
                    formatted.len += 6;
                }
            } else if !formatted.offset(seconds, encoder.option & UTC_Z != 0) {
                return Ok(false);
            }
        }
    } else if value.is_exact_instance_of::<PyDate>() {
        if !formatted.date(value.downcast::<PyDate>()?) {
            return Ok(false);
        }
    } else if value.is_exact_instance_of::<PyTime>() {
        let time = value.downcast::<PyTime>()?;
        if time.get_tzinfo().is_some()
            || !formatted.time(time, encoder.option & OMIT_MICROSECONDS != 0)
        {
            return Ok(false);
        }
    } else {
        return Ok(false);
    }
    formatted.push(b'"');
    encoder.extend(&formatted.bytes[..formatted.len])?;
    Ok(true)
}

#[cfg(any(Py_LIMITED_API, Py_GIL_DISABLED, PyPy, GraalPy))]
pub(super) fn write(
    _: &mut Encoder<true, output::Output<'_>>,
    _: &Bound<'_, PyAny>,
) -> PyResult<bool> {
    Ok(false)
}

/// Quotes, ordinary date/time fields, six fractional digits, and a UTC offset
/// fit in 34 initialized bytes. No character produced here needs JSON escaping.
#[cfg(not(any(Py_LIMITED_API, Py_GIL_DISABLED, PyPy, GraalPy)))]
struct FormattedDateTime {
    bytes: [u8; 34],
    len: usize,
}

#[cfg(not(any(Py_LIMITED_API, Py_GIL_DISABLED, PyPy, GraalPy)))]
impl FormattedDateTime {
    fn new() -> Self {
        let mut bytes = [0; 34];
        bytes[0] = b'"';
        Self { bytes, len: 1 }
    }

    fn push(&mut self, byte: u8) {
        self.bytes[self.len] = byte;
        self.len += 1;
    }

    fn two_digits(&mut self, value: u8) {
        self.bytes[self.len] = b'0' + value / 10;
        self.bytes[self.len + 1] = b'0' + value % 10;
        self.len += 2;
    }

    fn date(&mut self, value: &impl PyDateAccess) -> bool {
        let (year, month, day) = (value.get_year(), value.get_month(), value.get_day());
        // Pickle-state constructors accept fields outside normal constructor
        // ranges. Preserve their Python formatting instead of truncating them.
        if !(1..=9999).contains(&year) || !(1..=12).contains(&month) || !(1..=31).contains(&day) {
            return false;
        }
        self.two_digits((year / 100) as u8);
        self.two_digits((year % 100) as u8);
        self.push(b'-');
        self.two_digits(month);
        self.push(b'-');
        self.two_digits(day);
        true
    }

    fn time(&mut self, value: &impl PyTimeAccess, omit_microseconds: bool) -> bool {
        let (hour, minute, second, microsecond) = (
            value.get_hour(),
            value.get_minute(),
            value.get_second(),
            value.get_microsecond(),
        );
        if hour > 23 || minute > 59 || second > 59 || microsecond > 999_999 {
            return false;
        }
        self.two_digits(hour);
        self.push(b':');
        self.two_digits(minute);
        self.push(b':');
        self.two_digits(second);
        if microsecond != 0 && !omit_microseconds {
            self.push(b'.');
            self.two_digits((microsecond / 10_000) as u8);
            self.two_digits((microsecond / 100 % 100) as u8);
            self.two_digits((microsecond % 100) as u8);
        }
        true
    }

    fn offset(&mut self, seconds: i64, utc_z: bool) -> bool {
        // Ignoring offset microseconds can produce -86400 for a valid offset
        // just above -24 hours. Rounding can then produce either sign of 24:00.
        if !(-86_400..86_400).contains(&seconds) {
            return false;
        }
        let minutes = (seconds.unsigned_abs() + 30) / 60;
        if minutes == 0 && utc_z {
            self.push(b'Z');
        } else {
            self.push(if seconds < 0 { b'-' } else { b'+' });
            self.two_digits((minutes / 60) as u8);
            self.push(b':');
            self.two_digits((minutes % 60) as u8);
        }
        true
    }
}
