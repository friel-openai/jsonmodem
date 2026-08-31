//! Python construction from the reader's immutable string classification.

use jsonmodem::document::DecodedString;
use pyo3::{exceptions::PyMemoryError, prelude::*, types::PyString};

#[inline(always)]
pub(super) fn new<'py>(
    py: Python<'py>,
    decoded: &DecodedString<'_, '_>,
) -> PyResult<Bound<'py, PyString>> {
    let text = decoded.as_str();
    if decoded.is_ascii() && text.len() > 1 {
        // SAFETY: DecodedString binds the classification to immutable text.
        // The length guard preserves the original singleton constructors.
        unsafe { new_ascii_string(py, text) }
    } else {
        Ok(PyString::new(py, text))
    }
}

/// # Safety
/// `text` must be ASCII and contain more than one byte.
#[inline(never)]
unsafe fn new_ascii_string<'py>(py: Python<'py>, text: &str) -> PyResult<Bound<'py, PyString>> {
    let length = pyo3::ffi::Py_ssize_t::try_from(text.len())
        .map_err(|_| PyMemoryError::new_err("decoded string is too large"))?;
    // SAFETY: The size is positive and fits Py_ssize_t. Failure is checked
    // before data access; success immediately has one owning reference.
    let value = unsafe { Bound::from_owned_ptr_or_err(py, pyo3::ffi::PyUnicode_New(length, 127))? };
    // SAFETY: The caller's ASCII proof gives one code point per source byte.
    // PyUnicode_New returns fresh one-byte storage and initializes its final
    // NUL. The live source cannot overlap this private destination. Nothing
    // here allocates, calls Python or publishes the object before the copy.
    unsafe {
        std::ptr::copy_nonoverlapping(
            text.as_ptr(),
            pyo3::ffi::PyUnicode_DATA(value.as_ptr()).cast::<u8>(),
            text.len(),
        );
        Ok(value.downcast_into_unchecked())
    }
}
