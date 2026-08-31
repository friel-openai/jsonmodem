//! Scoped buffer exports with stable descriptors and owned or bytes-backed
//! data.

use std::{cell::Cell, marker::PhantomPinned, pin::pin};

use pyo3::{exceptions::PyTypeError, ffi, prelude::*, types::PyBytes};

/// A SIMPLE export which cannot move or escape its acquisition callback.
pub(crate) struct BufferExport<'py> {
    view: ffi::Py_buffer,
    // GetBuffer failure must not release a partially filled descriptor.
    acquired: Cell<bool>,
    // The export must be released before this Python attachment ends.
    _python: Python<'py>,
    // Exporters may keep pointers into the descriptor itself.
    _pinned: PhantomPinned,
}

/// Request the same contiguous-byte export used by the streaming API.
/// A refused request is cleared and returned as None, preserving input
/// dispatch.
pub(crate) fn with_export<T>(
    data: &Bound<'_, PyAny>,
    callback: impl FnOnce(&BufferExport<'_>) -> PyResult<T>,
) -> PyResult<Option<T>> {
    let mut export = pin!(BufferExport {
        view: ffi::Py_buffer::new(),
        acquired: Cell::new(false),
        _python: data.py(),
        _pinned: PhantomPinned,
    });
    // SAFETY: pin! fixes the descriptor's address before acquisition. This
    // projection only writes the descriptor; it never moves it. data is live,
    // Python is attached, and the callback cannot take ownership of the guard.
    let status = unsafe {
        ffi::PyObject_GetBuffer(
            data.as_ptr(),
            &mut export.as_mut().get_unchecked_mut().view,
            ffi::PyBUF_SIMPLE,
        )
    };
    if status != 0 {
        // SAFETY: GetBuffer failed while Python was attached. Input dispatch
        // historically discards that exception before trying another input form.
        unsafe { ffi::PyErr_Clear() };
        return Ok(None);
    }
    export.acquired.set(true);
    callback(&export).map(Some)
}

impl BufferExport<'_> {
    pub(crate) fn len(&self) -> isize {
        self.view.len
    }

    pub(crate) fn readonly(&self) -> bool {
        self.view.readonly != 0
    }

    pub(crate) fn itemsize(&self) -> isize {
        self.view.itemsize
    }

    fn length(&self, caller: &str) -> PyResult<usize> {
        usize::try_from(self.view.len).map_err(|_| {
            PyTypeError::new_err(format!("{caller} received a negative buffer length"))
        })
    }

    /// Derive the borrow from an immutable owner, not an exporter pointer.
    pub(crate) fn owner_bytes<'a>(
        &self,
        owner: &'a Bound<'_, PyBytes>,
        caller: &str,
    ) -> PyResult<&'a [u8]> {
        let length = self.length(caller)?;
        if length == 0 {
            return Ok(&[]);
        }
        let storage = owner.as_bytes();
        let range = (self.view.buf as usize)
            .checked_sub(storage.as_ptr() as usize)
            .and_then(|start| start.checked_add(length).map(|end| start..end));
        range
            .and_then(|range| storage.get(range))
            .ok_or_else(|| PyTypeError::new_err(format!("{caller} buffer exceeds its bytes owner")))
    }

    /// Copy before parser callbacks can mutate otherwise valid exporter
    /// storage.
    pub(crate) fn snapshot(&self, caller: &str) -> PyResult<Vec<u8>> {
        let length = self.length(caller)?;
        if length == 0 {
            return Ok(Vec::new());
        }
        if self.view.buf.is_null() {
            return Err(PyTypeError::new_err(format!(
                "{caller} received a null buffer"
            )));
        }
        let mut bytes = Vec::with_capacity(length);
        // SAFETY: the active SIMPLE export supplies length readable contiguous
        // bytes. The positive isize length fits Vec, and its fresh allocation
        // does not overlap the export. No Python call, GIL release, or external
        // Rust shared borrow occurs during the copy. Every byte is initialized
        // before set_len. Native exporters must still honor their storage contract.
        unsafe {
            std::ptr::copy_nonoverlapping(self.view.buf.cast::<u8>(), bytes.as_mut_ptr(), length);
            bytes.set_len(length);
        }
        Ok(bytes)
    }
}

impl Drop for BufferExport<'_> {
    fn drop(&mut self) {
        if self.acquired.get() {
            // SAFETY: this is the same pinned descriptor passed to GetBuffer.
            // Its owned export is released once, while Python is still attached.
            unsafe { ffi::PyBuffer_Release(&mut self.view) };
        }
    }
}
