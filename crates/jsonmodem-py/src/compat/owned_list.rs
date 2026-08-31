//! Transfer decoded values into existing list storage without an extra owner.

use pyo3::{prelude::*, types::PyList};

#[cfg(all(
    Py_3_12,
    not(any(Py_3_14, PyPy, GraalPy, Py_LIMITED_API, Py_GIL_DISABLED)),
    not(any(
        py_sys_config = "Py_DEBUG",
        py_sys_config = "Py_REF_DEBUG",
        py_sys_config = "Py_TRACE_REFS",
    )),
    target_os = "linux",
    target_arch = "x86_64",
    target_pointer_width = "64",
    target_endian = "little",
))]
mod live;

/// Append an owned decoded value; Python still handles allocation and growth.
#[inline]
pub(super) fn append(list: &Bound<'_, PyList>, value: PyObject) -> PyResult<()> {
    #[cfg(all(
        Py_3_12,
        not(any(Py_3_14, PyPy, GraalPy, Py_LIMITED_API, Py_GIL_DISABLED)),
        not(any(
            py_sys_config = "Py_DEBUG",
            py_sys_config = "Py_REF_DEBUG",
            py_sys_config = "Py_TRACE_REFS",
        )),
        target_os = "linux",
        target_arch = "x86_64",
        target_pointer_width = "64",
        target_endian = "little",
    ))]
    {
        let pointer = list.as_ptr().cast::<pyo3::ffi::PyListObject>();
        // SAFETY: list keeps a valid CPython header and its current storage live.
        // In this GIL-only ABI, CPython supplies aligned, byte-bounded capacity
        // and a nonnegative size, including sort's empty, allocated=-1 state.
        // value owns a live object. Read metadata after its construction, which
        // may run GC callbacks; no Python operation or owner drop intervenes
        // before publication and the immediate ownership transfer below.
        let appended = unsafe {
            live::append_live(
                (*pointer).ob_item.cast(),
                std::ptr::addr_of_mut!((*pointer).ob_base.ob_size),
                (*pointer).allocated,
                value.as_ptr().cast(),
            )
        };
        if appended {
            // into_ptr cannot fail, allocate or call Python. The slot now owns
            // this reference; do not run any operation before relinquishing it.
            let _ = value.into_ptr();
            return Ok(());
        }
    }
    list.append(value)
}

#[cfg(test)]
mod tests;

#[cfg(test)]
mod gc_tests;
