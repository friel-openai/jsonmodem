//! Borrow dictionary entries only during non-reentrant validation and writes.

mod compact_int;

#[cfg(not(any(py_sys_config = "Py_DEBUG", py_sys_config = "Py_REF_DEBUG")))]
mod dense_entry;

#[cfg(test)]
mod tests;

use pyo3::{
    ffi,
    prelude::*,
    types::{PyDict, PyString},
};

use super::{Encoder, INDENT, OutputAllocationError, key_identity_bit};

/// Certify common keys without conversions, output, or temporary owners.
/// False requires the full owning validation; it does not mean a key is
/// invalid.
#[cfg(not(any(
    py_sys_config = "Py_DEBUG",
    py_sys_config = "Py_REF_DEBUG",
    py_sys_config = "Py_TRACE_REFS",
)))]
pub(super) fn primitive_keys_valid<const CHECKED: bool>(dict: &Bound<'_, PyDict>) -> bool {
    if CHECKED {
        return false;
    }
    let mut position = 0;
    let mut key = std::ptr::null_mut();
    loop {
        // SAFETY: dict owns the dictionary under the GIL. PyDict_Next accepts
        // a null value-output pointer, and both other outputs remain live.
        if unsafe { ffi::PyDict_Next(dict.as_ptr(), &mut position, &mut key, std::ptr::null_mut()) }
            == 0
        {
            return true;
        }
        // SAFETY: dict retains each key. Neither this loop nor entry_scalar
        // allocates, converts, decrements a reference, or reenters Python.
        // No borrowed text survives this test, and no pointer escapes.
        if unsafe { entry_scalar(key, dict) }.is_none() {
            return false;
        }
    }
}

/// An entry has either been written or promoted to two owning references.
pub(super) enum DictStep<'py> {
    Written,
    Owned(Bound<'py, PyAny>, Bound<'py, PyAny>),
    End,
}

/// An owned dictionary and PyO3's iteration state; no entry pointers persist.
pub(super) struct DictScalarCursor<'py> {
    dict: Bound<'py, PyDict>,
    // This is PyDict_Next's opaque position, not a count of emitted entries.
    position: ffi::Py_ssize_t,
    // A mutation sets the original size to -1, preserving PyO3's sticky panic.
    original_size: ffi::Py_ssize_t,
    remaining: ffi::Py_ssize_t,
}

impl<'py> DictScalarCursor<'py> {
    pub(super) fn new(dict: Bound<'py, PyDict>) -> Self {
        let size = dict.len() as ffi::Py_ssize_t;
        Self {
            dict,
            position: 0,
            original_size: size,
            remaining: size,
        }
    }

    /// Reacquire table storage on each call, before any Python reentry.
    #[inline(always)]
    fn lookup_entry(
        &mut self,
        current_size: ffi::Py_ssize_t,
    ) -> Option<(*mut ffi::PyObject, *mut ffi::PyObject)> {
        #[cfg(not(any(py_sys_config = "Py_DEBUG", py_sys_config = "Py_REF_DEBUG")))]
        if current_size > 0 && self.dict.is_exact_instance_of::<PyDict>() {
            let dict = self.dict.as_ptr().cast::<ffi::PyDictObject>();
            // SAFETY: the exact dictionary is retained under the GIL. This
            // field read neither reenters Python nor forms a table reference.
            if unsafe { std::ptr::addr_of!((*dict).ma_values).read() }.is_null() {
                // SAFETY: the same owner retains the current key table. Do not
                // save this pointer across an owned result or error handling.
                let keys = unsafe { std::ptr::addr_of!((*dict).ma_keys).read() }.cast::<u8>();
                // SAFETY: this module selects the reviewed full-API GIL layout,
                // with debug layouts excluded above. Valid CPython storage
                // supplies the initialized fields and entries read by the
                // helper; no callback, allocation, decref or GIL release can
                // mutate it during these checks and copied-pointer reads.
                match unsafe { dense_entry::read_entry(keys, current_size, self.position) } {
                    dense_entry::EntryLookup::Entry { key, value } => {
                        // The admitted position is below a positive isize count.
                        self.position += 1;
                        return Some((key.cast(), value.cast()));
                    }
                    dense_entry::EntryLookup::End => return None,
                    dense_entry::EntryLookup::Fallback => {}
                }
            }
        }
        let _ = current_size;
        let mut key = std::ptr::null_mut();
        let mut value = std::ptr::null_mut();
        // SAFETY: dict owns the dictionary under the GIL. Every declined
        // lookup leaves position untouched and these outputs initialized.
        if unsafe { ffi::PyDict_Next(self.dict.as_ptr(), &mut self.position, &mut key, &mut value) }
            == 0
        {
            None
        } else {
            Some((key, value))
        }
    }

    pub(super) fn next<const CHECKED: bool>(
        &mut self,
        encoder: &mut Encoder<CHECKED>,
        count: &mut usize,
        depth: usize,
    ) -> PyResult<DictStep<'py>> {
        // Encoder::value selects this cursor only for ordinary Vec output.
        // Fail before borrowing an entry if a checked caller is added later.
        assert!(!CHECKED);
        let current_size = self.dict.len() as ffi::Py_ssize_t;
        if self.original_size != current_size {
            self.original_size = -1;
            panic!("dictionary changed size during iteration");
        }
        if self.remaining == -1 {
            self.original_size = -1;
            panic!("dictionary keys changed during iteration");
        }
        let Some((key, value)) = self.lookup_entry(current_size) else {
            return Ok(DictStep::End);
        };
        self.remaining -= 1;

        // SAFETY: a successful lookup returns non-null entries owned by
        // dict. No Python allocation, conversion, error, callback, decref or
        // GIL release occurs until this helper finishes all borrowed reads.
        // Its writers allocate only Rust Vec storage. Do not substitute a
        // Python-bytes writer here. A rejected entry has changed no output.
        let written = unsafe { try_write_entry(&self.dict, encoder, count, depth, key, value) };
        if let Some(Ok(())) = written {
            return Ok(DictStep::Written);
        }

        let py = self.dict.py();
        // SAFETY: the helper has not reentered Python or removed either dict
        // owner. Increment both references before any general processing.
        let (key, value) = unsafe {
            (
                Bound::from_borrowed_ptr(py, key),
                Bound::from_borrowed_ptr(py, value),
            )
        };
        match written {
            None => Ok(DictStep::Owned(key, value)),
            Some(Err(error)) => {
                // The ordinary loop drops its key after writing the colon and
                // space, before serializing the value or constructing its error.
                let error = if error.key_finished {
                    drop(key);
                    PyErr::from(error.error)
                } else {
                    let result = PyErr::from(error.error);
                    drop(key);
                    result
                };
                drop(value);
                Err(error)
            }
            Some(Ok(())) => unreachable!(),
        }
    }
}

/// Borrowed text and copied primitives need no Python conversion or destructor.
enum EntryScalar<'a> {
    Null,
    Boolean(bool),
    Text(&'a str),
    Integer(i64),
    Float(f64),
}

/// Preserve the original key-owner scope before constructing an output error.
struct EntryWriteError {
    error: OutputAllocationError,
    // True after the colon and optional indentation space have been written.
    key_finished: bool,
}

/// Read an exact compact ASCII entry without a conversion fallback.
///
/// # Safety
///
/// The dictionary must own pointer, and the caller must hold the GIL without
/// Python reentry or a reference decrement until the returned text is unused.
/// Its lifetime is bounded by the dictionary owner, but that owner alone does
/// not prevent reentrant dictionary mutation.
#[inline]
unsafe fn entry_ascii<'a>(
    pointer: *mut ffi::PyObject,
    _owner: &'a Bound<'_, PyDict>,
) -> Option<&'a str> {
    // SAFETY: the caller keeps the entry live under the GIL. The module is
    // restricted to the reviewed full-API CPython 3.12/3.13 layout. These
    // checks and reads cannot call Python or construct an exception.
    unsafe {
        if ffi::PyUnicode_CheckExact(pointer) == 0 || ffi::PyUnicode_IS_COMPACT_ASCII(pointer) == 0
        {
            return None;
        }
        let length = usize::try_from(ffi::PyUnicode_GET_LENGTH(pointer)).ok()?;
        let bytes = std::slice::from_raw_parts(ffi::PyUnicode_1BYTE_DATA(pointer), length);
        Some(std::str::from_utf8_unchecked(bytes))
    }
}

/// Copy a compact integer only after checking the actual digit offset/width.
///
/// # Safety
///
/// pointer must be a live exact CPython integer retained by the dictionary
/// under the GIL throughout this non-reentrant read.
#[inline(always)]
unsafe fn entry_integer(pointer: *mut ffi::PyObject) -> Option<i64> {
    /// The initialized prefix excludes digits and their possible trailing
    /// padding.
    #[repr(C)]
    struct IntegerPrefix {
        _header: ffi::PyObject,
        // CPython stores the digit count above the three sign/flag bits.
        tag: usize,
    }

    let expected_offset = isize::try_from(std::mem::size_of::<IntegerPrefix>()).ok()?;
    let integer_type = std::ptr::addr_of!(ffi::PyLong_Type);
    // SAFETY: the built-in type is live under the GIL. These metadata fields
    // give the first digit's offset and sizeof(digit), respectively.
    let layout_matches = unsafe {
        (*integer_type).tp_basicsize == expected_offset && (*integer_type).tp_itemsize == 4
    };
    let tag = pointer
        .cast::<u8>()
        .wrapping_add(std::mem::offset_of!(IntegerPrefix, tag))
        .cast::<usize>();
    // SAFETY: the selected ABI supplies an initialized tag. The helper first
    // checks layout_matches and reads a digit only for a nonzero one-digit
    // tag. The caller retains this immutable integer under the GIL.
    unsafe { compact_int::read_compact(tag, layout_matches) }
}

/// Classify without invoking any object's methods or creating a Python error.
///
/// # Safety
///
/// owner must retain pointer under the GIL. No reentry or decref is permitted
/// until all returned text is unused. No pointer or text may escape that
/// operation.
#[inline]
unsafe fn entry_scalar<'a>(
    pointer: *mut ffi::PyObject,
    owner: &'a Bound<'_, PyDict>,
) -> Option<EntryScalar<'a>> {
    // SAFETY: the caller retains the entry without reentry. Every check is an
    // exact built-in type or singleton comparison. The float getter reads its
    // initialized field; the string/integer helpers never convert or raise.
    unsafe {
        if ffi::Py_IsNone(pointer) != 0 {
            Some(EntryScalar::Null)
        } else if ffi::PyUnicode_CheckExact(pointer) != 0 {
            entry_ascii(pointer, owner).map(EntryScalar::Text)
        } else if ffi::PyBool_Check(pointer) != 0 {
            Some(EntryScalar::Boolean(ffi::Py_IsTrue(pointer) != 0))
        } else if ffi::PyLong_CheckExact(pointer) != 0 {
            entry_integer(pointer).map(EntryScalar::Integer)
        } else if ffi::PyFloat_CheckExact(pointer) != 0 {
            Some(EntryScalar::Float(ffi::PyFloat_AS_DOUBLE(pointer)))
        } else {
            None
        }
    }
}

/// Write an ASCII key using the original first-16 owning cache policy.
///
/// # Safety
///
/// owner must retain the exact string key and text must view that string.
/// The caller holds the GIL and excludes reentry/decrefs through the write.
unsafe fn write_key<const CHECKED: bool>(
    owner: &Bound<'_, PyDict>,
    encoder: &mut Encoder<CHECKED>,
    key: *mut ffi::PyObject,
    text: &str,
) -> Result<(), OutputAllocationError> {
    let cache = encoder.output.len() >= 1024;
    if cache
        && (CHECKED
            || encoder.keys.len() < 16
            || encoder.key_mask & key_identity_bit(key as usize) != 0)
    {
        if let Some((_, encoded)) = encoder.keys.iter().find(|(entry, _)| entry.as_ptr() == key) {
            let encoded = encoded.clone();
            encoder.output.extend_from_within(encoded);
            return Ok(());
        }
    }
    let start = encoder.output.len();
    encoder.string(text)?;
    if cache && encoder.keys.len() < 16 && text.len() <= 64 {
        // SAFETY: the exact string key is still owned by dict. This adds a
        // retained owner without conversion, allocation or a reference drop.
        let key = unsafe { Py::<PyString>::from_borrowed_ptr(owner.py(), key) };
        let identity = key.as_ptr() as usize;
        encoder.keys.push((key, start..encoder.output.len()));
        if !CHECKED {
            encoder.key_mask |= key_identity_bit(identity);
        }
    }
    Ok(())
}

/// Finish classification before changing output, entry count or key owners.
///
/// # Safety
///
/// owner must retain both entries under the GIL. CHECKED must be false, and
/// the encoder must use the Rust Vec writer, not Python allocation. No reentry
/// or decref is allowed until this function returns; only cached-key increfs
/// may change Python reference counts. No borrowed view escapes this function.
unsafe fn try_write_entry<const CHECKED: bool>(
    owner: &Bound<'_, PyDict>,
    encoder: &mut Encoder<CHECKED>,
    count: &mut usize,
    depth: usize,
    key: *mut ffi::PyObject,
    value: *mut ffi::PyObject,
) -> Option<Result<(), EntryWriteError>> {
    // SAFETY: the caller retains both entries, excludes reentry/decrefs and
    // consumes these views only within this function.
    let (text, scalar) = unsafe { (entry_ascii(key, owner)?, entry_scalar(value, owner)?) };
    let prefix = (|| {
        if *count != 0 {
            encoder.push(b',')?;
        }
        *count += 1;
        encoder.newline(depth)?;
        // SAFETY: text belongs to the exact key retained by owner; all output
        // and cache growth uses Rust storage, and cached keys remain owned.
        unsafe { write_key(owner, encoder, key, text) }?;
        encoder.push(b':')?;
        if encoder.option & INDENT != 0 {
            encoder.push(b' ')?;
        }
        Ok(())
    })();
    if let Err(error) = prefix {
        return Some(Err(EntryWriteError {
            error,
            key_finished: false,
        }));
    }
    let result = match scalar {
        EntryScalar::Null => encoder.extend(b"null"),
        EntryScalar::Boolean(value) => encoder.extend(if value { b"true" } else { b"false" }),
        EntryScalar::Text(text) => encoder.string(text),
        // Valid compact integers have magnitude below 2**30, within both
        // the ordinary integer range and OPT_STRICT_INTEGER's 53-bit range.
        EntryScalar::Integer(value) => encoder.extend(itoa::Buffer::new().format(value).as_bytes()),
        EntryScalar::Float(value) if value.is_finite() => {
            encoder.extend(zmij::Buffer::new().format_finite(value).as_bytes())
        }
        EntryScalar::Float(_) => encoder.extend(b"null"),
    };
    Some(result.map_err(|error| EntryWriteError {
        error,
        key_finished: true,
    }))
}
