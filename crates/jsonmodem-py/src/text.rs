use pyo3::{
    exceptions::{PySystemError, PyUnicodeError},
    prelude::*,
    types::PyString,
};

/// Borrow validated UTF-8 while retaining the Python string that owns it.
#[inline]
pub(crate) fn string_text<'value>(value: &'value Bound<'_, PyString>) -> PyResult<&'value str> {
    #[cfg(all(
        Py_3_12,
        not(any(Py_3_14, PyPy, GraalPy, Py_LIMITED_API, Py_GIL_DISABLED)),
        not(py_sys_config = "Py_TRACE_REFS"),
        target_os = "linux",
        target_arch = "x86_64",
        target_pointer_width = "64",
        target_endian = "little",
    ))]
    if let Some(text) = compact_ascii_text(value) {
        return Ok(text);
    }

    let mut length: pyo3::ffi::Py_ssize_t = 0;
    // SAFETY: value retains a Unicode object and the GIL during the call. The
    // API returns a cache owned by that immutable object, or a Python error.
    let pointer = unsafe { pyo3::ffi::PyUnicode_AsUTF8AndSize(value.as_ptr(), &mut length) };
    if pointer.is_null() {
        return Err(PyErr::fetch(value.py()));
    }
    let length = usize::try_from(length)
        .map_err(|_| PySystemError::new_err("Python returned a negative UTF-8 length"))?;
    // SAFETY: the successful API call provides length initialized bytes at a
    // non-null pointer. Py_ssize_t bounds the length by isize::MAX, and value
    // keeps the immutable cache alive for the returned borrow. A codec handler
    // may supply invalid UTF-8, so these bytes are not yet a Rust str.
    let bytes = unsafe { std::slice::from_raw_parts(pointer.cast::<u8>(), length) };
    std::str::from_utf8(bytes).map_err(|_| PyUnicodeError::new_err("str is not valid UTF-8"))
}

/// Borrow existing ASCII storage without invoking a codec or creating a cache.
#[cfg(all(
    Py_3_12,
    not(any(Py_3_14, PyPy, GraalPy, Py_LIMITED_API, Py_GIL_DISABLED)),
    not(py_sys_config = "Py_TRACE_REFS"),
    target_os = "linux",
    target_arch = "x86_64",
    target_pointer_width = "64",
    target_endian = "little",
))]
#[inline]
pub(crate) fn compact_ascii_text<'value>(
    value: &'value Bound<'_, PyString>,
) -> Option<&'value str> {
    if value.is_exact_instance_of::<PyString>() {
        // SAFETY: value owns an exact CPython str while the GIL is held. In the
        // selected ABI, compact ASCII has initialized, immutable ASCII data of
        // GET_LENGTH bytes. PyO3 computes its address for that ABI, including
        // empty strings. The returned view cannot outlive the owning reference.
        unsafe {
            let pointer = value.as_ptr();
            if pyo3::ffi::PyUnicode_IS_COMPACT_ASCII(pointer) != 0 {
                if let Ok(length) = usize::try_from(pyo3::ffi::PyUnicode_GET_LENGTH(pointer)) {
                    let bytes = std::slice::from_raw_parts(
                        pyo3::ffi::PyUnicode_1BYTE_DATA(pointer),
                        length,
                    );
                    return Some(std::str::from_utf8_unchecked(bytes));
                }
            }
        }
    }
    None
}
