//! Python strings from classified scanner text and ASCII error documents.

#[cfg(test)]
mod tests;

use jsonmodem::document::DecodedString;
use pyo3::{exceptions::PyMemoryError, prelude::*, types::PyString};

/// ASCII text with at least two bytes, so allocation cannot return a shared
/// empty or single-character Python string.
struct AsciiText<'a>(&'a str);

impl<'a> AsciiText<'a> {
    #[inline]
    fn from_decoded(decoded: &'a DecodedString<'_, '_>) -> Option<Self> {
        let text = decoded.as_str();
        (decoded.is_ascii() && text.len() > 1).then_some(Self(text))
    }

    fn from_error_document(text: &'a str) -> Option<Self> {
        (text.len() >= 1024 && text.is_ascii()).then_some(Self(text))
    }
}

/// Delay error-document allocation until PyO3 converts the second call
/// argument.
pub(crate) struct ErrorDocument<'a>(pub(crate) &'a str);

impl<'py> IntoPyObject<'py> for ErrorDocument<'_> {
    type Target = PyString;
    type Output = Bound<'py, Self::Target>;
    type Error = PyErr;

    fn into_pyobject(self, py: Python<'py>) -> PyResult<Self::Output> {
        if let Some(text) = AsciiText::from_error_document(self.0) {
            return new_ascii_string(py, text);
        }
        Ok(PyString::new(py, self.0))
    }
}

#[inline(always)]
pub(super) fn new<'py>(
    py: Python<'py>,
    decoded: &DecodedString<'_, '_>,
) -> PyResult<Bound<'py, PyString>> {
    if let Some(text) = AsciiText::from_decoded(decoded) {
        new_ascii_string(py, text)
    } else {
        Ok(PyString::new(py, decoded.as_str()))
    }
}

#[inline(never)]
fn new_ascii_string<'py>(py: Python<'py>, text: AsciiText<'_>) -> PyResult<Bound<'py, PyString>> {
    let text = text.0;
    let length = pyo3::ffi::Py_ssize_t::try_from(text.len())
        .map_err(|_| PyMemoryError::new_err("decoded string is too large"))?;
    // SAFETY: The size is positive and fits Py_ssize_t. Failure is checked
    // before data access; success immediately has one owning reference.
    let value = unsafe { Bound::from_owned_ptr_or_err(py, pyo3::ffi::PyUnicode_New(length, 127))? };
    // SAFETY: AsciiText guarantees one code point per source byte.
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
